"""Editor del informe tipo Word (fase 2).

Flujo: resultados aprobados → borrador con el modelo de informe → edición con
autoguardado e historial → emisión con código, firma y QR → PDF en Celery →
envío al cliente desde la revisión.
"""
import json
from datetime import timedelta

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from trabajadores.permissions import permiso_requerido, trabajador_tiene_permiso

from .informe_compresion import lineas_resultados
from .informe_editor import (
    BLOQUES_CONVERTIBLES, MODO_PDF, MODO_WEB, PERMISO_EDITAR_DATOS, TIPOS_BLOQUE, DocumentoInvalido,
    bloques_disponibles, bloques_editados, bloques_faltantes, documento_inicial, html_de_bloques, html_informe,
    validar_contenido,
)
from .models import BorradorInforme, InformeFinal, SolicitudEnsayo, VersionInforme
from .tasks import generar_informe_editor
from .views_informe_compresion import PERMISO_APROBAR, _perfil

MAX_JSON = 2 * 1024 * 1024
MINUTOS_ENTRE_VERSIONES = 10


def _sin_aprobar(lineas):
    return [d.muestra.codigo_laboratorio for d in lineas
            if getattr(d, 'resultado', None) is None or not d.resultado.aprobado]


def borrador_de(solicitud, perfil=None):
    """El borrador de la solicitud; si no existe se crea desde el modelo de informe."""
    borrador, creado = BorradorInforme.objects.get_or_create(
        solicitud=solicitud,
        defaults={'contenido': documento_inicial(solicitud), 'actualizado_por': perfil},
    )
    if creado:
        VersionInforme.objects.create(
            borrador=borrador, numero=borrador.version, contenido=borrador.contenido,
            autor=perfil, nota='Creado desde el modelo de informe',
        )
    return borrador


def _guardar_version(borrador, perfil, nota=''):
    ultima = borrador.versiones.first()
    if (nota or ultima is None or ultima.autor_id != getattr(perfil, 'pk', None)
            or timezone.now() - ultima.creado_en > timedelta(minutes=MINUTOS_ENTRE_VERSIONES)):
        VersionInforme.objects.create(
            borrador=borrador, numero=borrador.version, contenido=borrador.contenido, autor=perfil, nota=nota,
        )


@login_required
@permiso_requerido(PERMISO_APROBAR)
def editor_informe(request, solicitud_id):
    solicitud = get_object_or_404(
        SolicitudEnsayo.objects.select_related('cotizacion__cliente', 'recepcion'), pk=solicitud_id,
    )
    lineas = list(lineas_resultados(solicitud))
    pendientes = _sin_aprobar(lineas)
    if not lineas or pendientes:
        messages.error(
            request,
            "El informe se redacta cuando todos los resultados están aprobados. Falta: "
            + (", ".join(pendientes) or "registrar ensayos") + ".",
        )
        return redirect('proyectos:revision_compresion', solicitud_id=solicitud.pk)
    borrador = borrador_de(solicitud, _perfil(request.user))
    informe = InformeFinal.objects.filter(solicitud=solicitud).first()
    return render(request, 'proyectos/informe_editor.html', {
        'solicitud': solicitud,
        'borrador': borrador,
        'informe': informe,
        'contenido': borrador.contenido,
        'bloques_html': html_de_bloques(solicitud),
        'bloques_menu': bloques_disponibles(solicitud, lineas),
        'faltan': bloques_faltantes(borrador.contenido, solicitud, lineas),
        'versiones': borrador.versiones.select_related('autor')[:15],
        'solo_lectura': borrador.emitido,
        'puede_editar_datos': trabajador_tiene_permiso(request.user, PERMISO_EDITAR_DATOS),
        'bloques_convertibles': list(BLOQUES_CONVERTIBLES),
    })


def _cambios_en_datos(anterior, nuevo):
    """(claves recién convertidas en texto, claves convertidas cuyo texto cambió)."""
    antes, ahora = bloques_editados(anterior), bloques_editados(nuevo)
    convertidos = [c for c in ahora if c not in antes]
    modificados = [c for c in ahora if c in antes and ahora[c] != antes[c]]
    return convertidos, modificados


def _nombre_bloque(clave, solicitud):
    tipo, _, ref = clave.partition(':')
    nombre = TIPOS_BLOQUE.get(tipo, tipo)
    if ref:
        detalle = solicitud.detalles.select_related('muestra').filter(pk=ref).first()
        if detalle:
            nombre += f" de {detalle.muestra.codigo_laboratorio}"
    return nombre


@login_required
@permiso_requerido(PERMISO_APROBAR)
@require_POST
def guardar_informe(request, solicitud_id):
    """Autoguardado. Si otra persona guardó antes, responde 409 y no pisa su trabajo."""
    if len(request.body) > MAX_JSON:
        return JsonResponse({'ok': False, 'error': 'El informe pesa demasiado.'}, status=413)
    try:
        datos = json.loads(request.body)
        version = int(datos.get('version'))
        contenido = validar_contenido(datos.get('contenido'))
    except (ValueError, TypeError, AttributeError, DocumentoInvalido) as exc:
        mensaje = str(exc) if isinstance(exc, DocumentoInvalido) else 'Datos no válidos.'
        return JsonResponse({'ok': False, 'error': mensaje}, status=400)

    perfil = _perfil(request.user)
    with transaction.atomic():
        borrador = get_object_or_404(
            BorradorInforme.objects.select_for_update().select_related('actualizado_por'),
            solicitud_id=solicitud_id,
        )
        if borrador.emitido:
            return JsonResponse({'ok': False, 'error': 'El informe ya fue emitido; no se puede modificar.'}, status=409)
        if borrador.version != version:
            quien = borrador.actualizado_por.nombre_completo if borrador.actualizado_por else 'otra persona'
            return JsonResponse({
                'ok': False, 'conflicto': True,
                'error': f"{quien} guardó cambios a las {timezone.localtime(borrador.actualizado_en):%H:%M}. "
                         "Recarga para ver su versión; lo tuyo sigue en esta pestaña.",
            }, status=409)
        convertidos, modificados = _cambios_en_datos(borrador.contenido, contenido)
        if (convertidos or modificados) and not trabajador_tiene_permiso(request.user, PERMISO_EDITAR_DATOS):
            return JsonResponse({
                'ok': False,
                'error': 'No tienes permiso para editar los datos del sistema. Pide a quien lo tenga que lo haga.',
            }, status=403)
        borrador.contenido = contenido
        borrador.version += 1
        borrador.actualizado_por = perfil
        borrador.save(update_fields=['contenido', 'version', 'actualizado_por', 'actualizado_en'])
        if convertidos:
            nota = "Convirtió en texto editable: " + ", ".join(
                _nombre_bloque(c, borrador.solicitud) for c in convertidos)
            _guardar_version(borrador, perfil, nota=nota[:120])
        else:
            _guardar_version(borrador, perfil)

    return JsonResponse({
        'ok': True,
        'version': borrador.version,
        'guardado_en': timezone.localtime(borrador.actualizado_en).strftime('%H:%M'),
        'faltan': bloques_faltantes(contenido, borrador.solicitud),
    })


@login_required
@permiso_requerido(PERMISO_APROBAR)
def vista_previa_informe(request, solicitud_id):
    borrador = get_object_or_404(BorradorInforme.objects.select_related('solicitud'), solicitud_id=solicitud_id)
    if borrador.emitido and borrador.html_emitido:
        informe = InformeFinal.objects.filter(solicitud_id=solicitud_id).first()
        html = html_informe(borrador, MODO_WEB, informe=informe, firmante=informe.responsable_firma if informe else None)
    else:
        html = html_informe(borrador, MODO_WEB)
    respuesta = HttpResponse(html)
    respuesta['X-Robots-Tag'] = 'noindex'
    return respuesta


@login_required
@permiso_requerido(PERMISO_APROBAR)
@require_POST
def restaurar_version(request, solicitud_id, version_id):
    perfil = _perfil(request.user)
    with transaction.atomic():
        borrador = get_object_or_404(BorradorInforme.objects.select_for_update(), solicitud_id=solicitud_id)
        version = get_object_or_404(VersionInforme, pk=version_id, borrador=borrador)
        if borrador.emitido:
            messages.error(request, "El informe ya fue emitido; no se puede modificar.")
        else:
            _guardar_version(borrador, perfil, nota='Antes de restaurar')
            borrador.contenido = validar_contenido(version.contenido)
            borrador.version += 1
            borrador.actualizado_por = perfil
            borrador.save(update_fields=['contenido', 'version', 'actualizado_por', 'actualizado_en'])
            _guardar_version(borrador, perfil, nota=f"Restaurada la versión {version.numero}")
            messages.success(request, f"Se restauró la versión {version.numero}.")
    return redirect('proyectos:editor_informe', solicitud_id=solicitud_id)


@login_required
@permiso_requerido(PERMISO_APROBAR)
@require_POST
def emitir_informe(request, solicitud_id):
    """Firma y emite: código, QR, HTML congelado y PDF en segundo plano."""
    url_editor = redirect('proyectos:editor_informe', solicitud_id=solicitud_id)
    perfil = _perfil(request.user)
    if perfil is None:
        messages.error(request, "Tu usuario no tiene ficha de trabajador; no puede firmar el informe.")
        return url_editor

    with transaction.atomic():
        borrador = get_object_or_404(
            BorradorInforme.objects.select_for_update().select_related('solicitud'), solicitud_id=solicitud_id,
        )
        solicitud = borrador.solicitud
        if borrador.emitido:
            messages.error(request, "Este informe ya fue emitido.")
            return url_editor
        lineas = list(lineas_resultados(solicitud))
        pendientes = _sin_aprobar(lineas)
        if pendientes:
            messages.error(request, "Hay resultados sin aprobar: " + ", ".join(pendientes) + ".")
            return url_editor
        propios = [d.muestra.codigo_laboratorio for d in lineas if d.resultado.tecnico_id == perfil.pk]
        if propios:
            messages.error(request, "No puedes firmar un informe con ensayos que ejecutaste tú: "
                           + ", ".join(propios) + ".")
            return url_editor
        faltan = bloques_faltantes(borrador.contenido, solicitud, lineas)
        if faltan:
            messages.error(request, "Antes de emitir vuelve a insertar: " + ", ".join(faltan) + ".")
            return url_editor

        informe = InformeFinal.objects.select_for_update().filter(solicitud=solicitud).first()
        if informe and informe.pdf_estado == InformeFinal.PDF_LISTO:
            messages.error(request, f"La solicitud ya tiene el informe {informe.codigo_informe}.")
            return url_editor
        ahora = timezone.now()
        if informe is None:
            informe = InformeFinal(solicitud=solicitud)
        informe.responsable_firma = perfil
        informe.fecha_emision = ahora
        informe.pdf_estado = InformeFinal.PDF_GENERANDO
        informe.pdf_error = ''
        informe.save()

        borrador.html_emitido = html_informe(borrador, MODO_PDF, informe=informe, firmante=perfil)
        borrador.estado = BorradorInforme.ESTADO_EMITIDO
        borrador.actualizado_por = perfil
        borrador.save(update_fields=['html_emitido', 'estado', 'actualizado_por', 'actualizado_en'])
        _guardar_version(borrador, perfil, nota=f"Emitido como {informe.codigo_informe}")
        informe_id = informe.pk
        transaction.on_commit(lambda: generar_informe_editor.delay(informe_id))

    messages.success(request, f"Informe {informe.codigo_informe} emitido. El PDF se está generando.")
    return redirect('proyectos:revision_compresion', solicitud_id=solicitud.pk)


def hay_borrador_emitido(solicitud):
    return BorradorInforme.objects.filter(
        solicitud=solicitud, estado=BorradorInforme.ESTADO_EMITIDO,
    ).exists()

