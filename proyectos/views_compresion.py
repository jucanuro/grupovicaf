"""Registro del ensayo de compresión de probetas desde el celular (HU-LIMS-14).

El técnico abre «Mis ensayos de compresión», elige la probeta por su código
de laboratorio (nunca ve el nombre del cliente), carga las cinco fotos con el
recorte de proporción fija y la marca como terminada. Sin las cinco fotos y
la fecha de ensayo no se puede terminar.
"""
import logging
from datetime import date

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.db.models import Count, Q
from django.http import FileResponse, Http404, HttpResponseForbidden, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_POST

from trabajadores.models import TrabajadorProfile
from trabajadores.permissions import permiso_requerido, trabajador_tiene_permiso, ve_todos_los_ensayos

from .fotos import FotoInvalida, procesar_foto
from .models import DetalleSolicitudEnsayo, EnsayoCompresion, FotoEnsayo

logger = logging.getLogger(__name__)

PERMISO_REGISTRAR = 'ensayos.registrar'

FILTRO_COMPRESION = (
    Q(norma__icontains='C39')
    | Q(servicio_cotizado__servicio__codigo_facturacion__iexact='EC001')
)


def _detalles_visibles(user):
    qs = DetalleSolicitudEnsayo.objects.filter(FILTRO_COMPRESION)
    if not ve_todos_los_ensayos(user):
        qs = qs.filter(tecnico_asignado__user=user)
    return qs


def _detalle_o_404(user, detalle_id):
    """La probeta si es de compresión y el usuario puede verla; si no, 404 (CA-20.2)."""
    return get_object_or_404(
        _detalles_visibles(user).select_related(
            'muestra', 'solicitud', 'tecnico_asignado', 'ensayo_compresion',
        ),
        pk=detalle_id,
    )


def _ensayo_de(detalle):
    try:
        return detalle.ensayo_compresion
    except EnsayoCompresion.DoesNotExist:
        return None


def _perfil(user):
    try:
        return user.trabajadorprofile
    except TrabajadorProfile.DoesNotExist:
        return None


def _fecha_minima(detalle):
    recepcion = detalle.solicitud.recepcion
    if recepcion and recepcion.fecha_recepcion:
        return timezone.localtime(recepcion.fecha_recepcion).date()
    return None


@login_required
@permiso_requerido(PERMISO_REGISTRAR)
def mis_ensayos_compresion(request):
    vista = request.GET.get('vista', 'pendientes')
    detalles = (
        _detalles_visibles(request.user)
        .select_related('muestra', 'solicitud', 'ensayo_compresion', 'tecnico_asignado')
        .annotate(n_fotos=Count('ensayo_compresion__fotos'))
        .order_by('fecha_entrega_programada', 'muestra__codigo_laboratorio')
    )
    terminado = Q(ensayo_compresion__estado=EnsayoCompresion.ESTADO_TERMINADO)
    detalles = detalles.filter(terminado) if vista == 'terminados' else detalles.exclude(terminado)

    return render(request, 'proyectos/compresion_lista.html', {
        'detalles': detalles[:200],
        'vista': vista,
        'total_fotos': len(FotoEnsayo.TIPOS),
        'hoy': timezone.localdate(),
    })


@login_required
@permiso_requerido(PERMISO_REGISTRAR)
def registrar_ensayo_compresion(request, detalle_id):
    detalle = _detalle_o_404(request.user, detalle_id)
    ensayo = _ensayo_de(detalle)
    ve_todos = ve_todos_los_ensayos(request.user)

    if request.method == 'POST':
        accion = request.POST.get('accion', 'guardar')
        url = reverse('proyectos:registrar_compresion', args=[detalle.pk])

        if accion == 'reabrir':
            if not ve_todos or ensayo is None:
                return HttpResponseForbidden("Solo el supervisor puede reabrir un ensayo terminado.")
            ensayo.estado = EnsayoCompresion.ESTADO_BORRADOR
            ensayo.terminado_en = None
            ensayo.save(update_fields=['estado', 'terminado_en', 'actualizado_en'])
            messages.success(request, "El ensayo volvió a quedar abierto para el técnico.")
            return redirect(url)

        if ensayo is not None and ensayo.terminado:
            messages.error(request, "Este ensayo ya está terminado; no se puede modificar.")
            return redirect(url)

        if ensayo is None:
            ensayo = EnsayoCompresion.objects.create(detalle=detalle)

        error = _aplicar_datos(request, detalle, ensayo)
        if error:
            messages.error(request, error)
            return redirect(url)

        if accion == 'terminar':
            faltan = ensayo.faltantes_para_terminar()
            if faltan:
                messages.error(request, "Para terminar falta " + ", ".join(faltan) + ".")
                return redirect(url)
            ensayo.estado = EnsayoCompresion.ESTADO_TERMINADO
            ensayo.terminado_en = timezone.now()
            ensayo.tecnico = _perfil(request.user)
            ensayo.save()
            messages.success(request, f"Probeta {detalle.muestra.codigo_laboratorio} terminada.")
            return redirect('proyectos:mis_ensayos_compresion')

        messages.success(request, "Datos guardados.")
        return redirect(url)

    fotos = {f.tipo: f for f in ensayo.fotos.all()} if ensayo else {}
    slots = [
        {
            'tipo': codigo,
            'etiqueta': etiqueta,
            'proporcion': FotoEnsayo.proporcion(codigo),
            'ancho': FotoEnsayo.PROPORCIONES[codigo][0],
            'alto': FotoEnsayo.PROPORCIONES[codigo][1],
            'foto': fotos.get(codigo),
        }
        for codigo, etiqueta in FotoEnsayo.TIPOS
    ]
    return render(request, 'proyectos/compresion_registro.html', {
        'detalle': detalle,
        'ensayo': ensayo,
        'slots': slots,
        'solo_lectura': bool(ensayo and ensayo.terminado),
        've_todos': ve_todos,
        'fecha_minima': _fecha_minima(detalle),
        'hoy': timezone.localdate(),
        'lado_maximo': FotoEnsayo.LADO_MAXIMO,
    })


def _aplicar_datos(request, detalle, ensayo):
    """Valida y guarda fecha de ensayo y observaciones. Devuelve un error o None."""
    texto_fecha = (request.POST.get('fecha_ensayo') or '').strip()
    fecha = None
    if texto_fecha:
        try:
            fecha = date.fromisoformat(texto_fecha)
        except ValueError:
            return "La fecha de ensayo no es válida."
        if fecha > timezone.localdate():
            return "La fecha de ensayo no puede ser futura."
        minima = _fecha_minima(detalle)
        if minima and fecha < minima:
            return f"La fecha de ensayo no puede ser anterior a la recepción ({minima:%d/%m/%Y})."
    ensayo.fecha_ensayo = fecha
    ensayo.observaciones = (request.POST.get('observaciones') or '').strip()
    ensayo.save(update_fields=['fecha_ensayo', 'observaciones', 'actualizado_en'])
    return None


@login_required
@require_POST
def subir_foto_compresion(request, detalle_id, tipo):
    if not trabajador_tiene_permiso(request.user, PERMISO_REGISTRAR):
        return JsonResponse({'ok': False, 'error': 'No tienes permiso para registrar ensayos.'}, status=403)
    if tipo not in FotoEnsayo.PROPORCIONES:
        raise Http404("Tipo de foto desconocido.")

    detalle = _detalle_o_404(request.user, detalle_id)
    archivo = request.FILES.get('foto')
    if not archivo:
        return JsonResponse({'ok': False, 'error': 'No llegó ninguna foto.'}, status=400)

    ensayo = _ensayo_de(detalle)
    if ensayo is not None and ensayo.terminado:
        return JsonResponse({'ok': False, 'error': 'El ensayo ya está terminado.'}, status=409)

    try:
        contenido = procesar_foto(archivo, FotoEnsayo.proporcion(tipo), FotoEnsayo.LADO_MAXIMO)
    except FotoInvalida as exc:
        return JsonResponse({'ok': False, 'error': str(exc)}, status=400)

    with transaction.atomic():
        if ensayo is None:
            ensayo, _ = EnsayoCompresion.objects.get_or_create(detalle=detalle)
        foto = FotoEnsayo.objects.select_for_update().filter(ensayo=ensayo, tipo=tipo).first()
        anterior = foto.imagen.name if foto and foto.imagen else None
        if foto is None:
            foto = FotoEnsayo(ensayo=ensayo, tipo=tipo)
        foto.subido_por = request.user
        foto.imagen.save('foto.jpg', contenido, save=False)
        foto.save()

    if anterior and anterior != foto.imagen.name:
        try:
            foto.imagen.storage.delete(anterior)
        except OSError:
            logger.warning("No se pudo borrar la foto reemplazada %s", anterior)

    return JsonResponse({
        'ok': True,
        'url': reverse('proyectos:foto_compresion', args=[foto.pk]) + f'?v={int(foto.subido_en.timestamp())}',
        'faltan': ensayo.faltantes_para_terminar(),
    })


@login_required
def foto_compresion(request, foto_id):
    """Sirve la foto desde la carpeta privada, solo a quien puede ver la probeta."""
    foto = get_object_or_404(FotoEnsayo.objects.select_related('ensayo__detalle'), pk=foto_id)
    puede = trabajador_tiene_permiso(request.user, PERMISO_REGISTRAR) or trabajador_tiene_permiso(
        request.user, 'informes.ver'
    )
    if not puede or not _detalles_visibles(request.user).filter(pk=foto.ensayo.detalle_id).exists():
        raise Http404("Foto no encontrada.")
    try:
        archivo = foto.imagen.open('rb')
    except FileNotFoundError:
        raise Http404("La foto ya no está disponible.")
    respuesta = FileResponse(archivo, content_type='image/jpeg')
    respuesta['Cache-Control'] = 'private, max-age=3600'
    return respuesta
