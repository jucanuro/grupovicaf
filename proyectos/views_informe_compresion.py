"""Revisión, emisión, Excel y envío del informe de compresión (HU-LIMS-15 a 20).

DP-LIMS-16 A: el técnico termina cada probeta y quien tiene
``informes.aprobar`` (Supervisor o Jefe de Laboratorio) revisa, devuelve con
observación o aprueba. Al aprobar se crea el InformeFinal de la solicitud
(DP-LIMS-14 A: uno por solicitud) y Celery arma el PDF. DP-LIMS-17 queda
pendiente: el QR sigue llevando a la página pública con solo datos.
"""
import json
from datetime import date

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Count, Max, Q
from django.http import FileResponse, Http404, HttpResponse, HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from trabajadores.models import TrabajadorProfile
from trabajadores.permissions import permiso_requerido, trabajador_tiene_permiso

from .informe_compresion import ensayos_para_excel, exportar_excel, lineas_resultados
from .plazos import estado_plazo, plazo_probeta
from .models import BorradorInforme, ResultadoEnsayo, InformeFinal, SolicitudEnsayo
from .tasks import enviar_informe_cliente, generar_informe_compresion, generar_informe_editor

PERMISO_APROBAR = 'informes.aprobar'
PERMISO_EXPORTAR = 'informes.exportar'


def _perfil(user):
    try:
        return user.trabajadorprofile
    except TrabajadorProfile.DoesNotExist:
        return None


@login_required
@permiso_requerido(PERMISO_APROBAR)
def revision_compresion_lista(request):
    from .models import DetalleSolicitudEnsayo
    conteos = (
        DetalleSolicitudEnsayo.objects.all()
        .values('solicitud')
        .annotate(
            total=Count('pk'),
            terminadas=Count('pk', filter=Q(resultado__estado__in=ResultadoEnsayo.ESTADOS_CERRADOS)),
            aprobadas=Count('pk', filter=Q(resultado__estado=ResultadoEnsayo.ESTADO_APROBADO)),
            con_resultado=Count('resultado'),
            ultima_fecha=Max('resultado__fecha_ensayo'),
        )
        .filter(con_resultado__gt=0)
    )
    por_solicitud = {c['solicitud']: c for c in conteos}
    solicitudes = list(
        SolicitudEnsayo.objects.filter(pk__in=por_solicitud.keys())
        .select_related('informe_final').order_by('-fecha_solicitud', '-pk')[:200]
    )
    for s in solicitudes:
        c = por_solicitud[s.pk]
        s.total, s.terminadas, s.aprobadas = c['total'], c['terminadas'], c['aprobadas']
        s.informe = getattr(s, 'informe_final', None) if hasattr(s, 'informe_final') else None
        s.emitido = bool(s.informe and s.informe.pdf_estado == InformeFinal.PDF_LISTO)
        s.por_emitir = s.aprobadas == s.total and not s.emitido
        s.plazo = plazo_probeta(c['ultima_fecha'])
        s.estado_plazo = estado_plazo(s.plazo, entregado=s.emitido)
    # Solo hay dos etapas aquí: lo que falta revisar y lo ya aprobado que falta firmar (emitir).
    # Lo emitido pasa a «Informes».
    por_revisar = [s for s in solicitudes if s.aprobadas < s.total]
    sin_firmar = [s for s in solicitudes if s.por_emitir]
    pedido = request.GET.get('vista', '')
    if pedido in ('sin_firmar', 'por_emitir'):
        filtro = 'sin_firmar'
    elif pedido == 'por_revisar':
        filtro = 'por_revisar'
    else:
        filtro = 'por_revisar'
    solicitudes = sin_firmar if filtro == 'sin_firmar' else por_revisar
    for s in solicitudes:
        s.avance = round(s.terminadas * 100 / s.total) if s.total else 0
    return render(request, 'proyectos/compresion_revision_lista.html', {
        'solicitudes': solicitudes,
        'vista': filtro,
        'n_por_revisar': len(por_revisar),
        'n_sin_firmar': len(sin_firmar),
        'puede_exportar': trabajador_tiene_permiso(request.user, PERMISO_EXPORTAR),
    })


@login_required
@permiso_requerido(PERMISO_APROBAR)
def revision_compresion(request, solicitud_id):
    solicitud = get_object_or_404(SolicitudEnsayo.objects.select_related('recepcion'), pk=solicitud_id)
    lineas = list(lineas_resultados(solicitud))
    if not lineas:
        raise Http404("La solicitud no tiene ensayos.")
    informe = InformeFinal.objects.filter(solicitud=solicitud).first()

    if request.method == 'POST':
        accion = request.POST.get('accion')
        if accion == 'devolver':
            return _devolver(request, solicitud, lineas)
        if accion == 'aprobar':
            return _aprobar(request, solicitud, lineas, informe)
        if accion == 'regenerar' and informe and informe.pdf_estado == InformeFinal.PDF_ERROR:
            InformeFinal.objects.filter(pk=informe.pk).update(pdf_estado=InformeFinal.PDF_GENERANDO, pdf_error='')
            if BorradorInforme.objects.filter(solicitud=solicitud, estado=BorradorInforme.ESTADO_EMITIDO).exists():
                generar_informe_editor.delay(informe.pk)
            else:
                generar_informe_compresion.delay(informe.pk)
            messages.success(request, "Se volvió a pedir el PDF.")
            return redirect('proyectos:revision_compresion', solicitud_id=solicitud.pk)
        if accion == 'enviar':
            return _enviar(request, solicitud, informe)
        return redirect('proyectos:revision_compresion', solicitud_id=solicitud.pk)

    filas = []
    for d in lineas:
        e = getattr(d, 'resultado', None)
        filas.append({
            'detalle': d, 'ensayo': e, 'fotos': list(e.fotos.all()) if e else [],
            # Trazabilidad: lo que se digitó mal y lo que quedó (CambioResultado).
            'cambios': list(e.cambios.select_related('usuario')) if e else [],
        })
    todas_terminadas = all(f['ensayo'] and f['ensayo'].terminado for f in filas)
    aprobadas = all(f['ensayo'] and f['ensayo'].aprobado for f in filas)
    return render(request, 'proyectos/compresion_revision.html', {
        'solicitud': solicitud,
        'filas': filas,
        'informe': informe,
        'todas_terminadas': todas_terminadas,
        'aprobadas': aprobadas,
        'total_cambios': sum(len(f['cambios']) for f in filas),
        'borrador': BorradorInforme.objects.filter(solicitud=solicitud).only('estado', 'actualizado_en').first(),
        'puede_exportar': trabajador_tiene_permiso(request.user, PERMISO_EXPORTAR),
        'correo_cliente': _correo_cliente(solicitud),
    })


def _leer_marcas(texto):
    """Marcas {clave: comentario} que mandó la pantalla de revisión; lo inválido se descarta."""
    try:
        datos = json.loads(texto or '{}')
    except ValueError:
        return {}
    if not isinstance(datos, dict):
        return {}
    return {str(k)[:80]: str(v or '')[:300] for k, v in list(datos.items())[:80]}


@login_required
@permiso_requerido(PERMISO_APROBAR)
def marcar_revision(request, detalle_id):
    """Guarda las marcas del revisor (campos o fotos incorrectos) sin devolver aún el ensayo."""
    from django.http import JsonResponse
    from .models import DetalleSolicitudEnsayo
    if request.method != 'POST':
        return JsonResponse({'ok': False}, status=405)
    detalle = get_object_or_404(DetalleSolicitudEnsayo.objects.select_related('resultado'), pk=detalle_id)
    ensayo = getattr(detalle, 'resultado', None)
    if ensayo is None or ensayo.estado != ResultadoEnsayo.ESTADO_TERMINADO:
        return JsonResponse({'ok': False, 'error': 'Solo se marca un ensayo terminado y aún no aprobado.'}, status=409)
    ensayo.marcas_revision = _leer_marcas(request.POST.get('marcas'))
    ensayo.save(update_fields=['marcas_revision', 'actualizado_en'])
    return JsonResponse({'ok': True, 'n': len(ensayo.marcas_revision)})


def _devolver(request, solicitud, lineas):
    detalle_id = request.POST.get('detalle_id')
    observacion = (request.POST.get('observacion') or '').strip()
    marcas = _leer_marcas(request.POST.get('marcas'))
    url = redirect('proyectos:revision_compresion', solicitud_id=solicitud.pk)
    detalle = next((d for d in lineas if str(d.pk) == detalle_id), None)
    ensayo = getattr(detalle, 'resultado', None) if detalle else None
    if ensayo is None or ensayo.estado != ResultadoEnsayo.ESTADO_TERMINADO:
        messages.error(request, "Solo se puede devolver un ensayo terminado y aún no aprobado.")
        return url
    perfil = _perfil(request.user)
    if perfil is not None and ensayo.tecnico_id == perfil.pk:
        messages.error(request, "No puedes revisar un ensayo que ejecutaste tú.")
        return url
    if not observacion and marcas:
        observacion = f"Corregir {len(marcas)} dato{'s' if len(marcas) != 1 else ''} marcado{'s' if len(marcas) != 1 else ''} en rojo."
    if not observacion:
        messages.error(request, "Marca lo que está mal o escribe la observación para el técnico.")
        return url
    ensayo.estado = ResultadoEnsayo.ESTADO_BORRADOR
    ensayo.terminado_en = None
    ensayo.observacion_revision = observacion[:2000]
    ensayo.marcas_revision = marcas
    ensayo.save(update_fields=['estado', 'terminado_en', 'observacion_revision', 'marcas_revision', 'actualizado_en'])
    solicitud.sincronizar_estado()
    messages.success(request, f"{detalle.muestra.codigo_laboratorio} devuelta al técnico.")
    return url


def _aprobar(request, solicitud, lineas, informe):
    url = redirect('proyectos:revision_compresion', solicitud_id=solicitud.pk)
    perfil = _perfil(request.user)
    if perfil is None:
        messages.error(request, "Tu usuario no tiene ficha de trabajador; no puede firmar el informe.")
        return url
    if informe and informe.pdf_estado == InformeFinal.PDF_LISTO:
        # CA-15.4 (informe de reemplazo con código nuevo) llega en una entrega posterior.
        messages.error(request, f"El informe {informe.codigo_informe} ya fue emitido.")
        return url
    ensayos = [getattr(d, 'resultado', None) for d in lineas]
    if any(e is None or not e.terminado for e in ensayos):
        messages.error(request, "Todos los ensayos de la solicitud deben estar terminados para aprobar.")
        return url
    propios = [d.muestra.codigo_laboratorio for d, e in zip(lineas, ensayos) if e.tecnico_id == perfil.pk]
    if propios:
        # Separación de funciones (ISO/IEC 17025): quien ejecuta no revisa su propio ensayo.
        messages.error(request, "No puedes aprobar ensayos que ejecutaste tú: " + ", ".join(propios) + ".")
        return url
    abiertas = {e.sesion for e in ensayos if e.sesion and e.sesion.abierta}
    if abiertas:
        tecnicos = ", ".join(sorted(str(s.tecnico.nombre_completo) for s in abiertas))
        messages.error(request, f"Falta cerrar la sesión de ensayo (temperatura y humedad finales) de: {tecnicos}.")
        return url

    # Todo informe pasa por el editor: aquí solo se aprueban los resultados.
    ResultadoEnsayo.objects.filter(pk__in=[e.pk for e in ensayos]).update(
        estado=ResultadoEnsayo.ESTADO_APROBADO, aprobado_por=perfil, aprobado_en=timezone.now(),
        observacion_revision='',
    )
    messages.success(request, "Resultados aprobados. Revisa el informe en el editor y emítelo.")
    return redirect('proyectos:editor_informe', solicitud_id=solicitud.pk)


def _correo_cliente(solicitud):
    cotizacion = solicitud.cotizacion
    return (cotizacion.correo_contacto or cotizacion.cliente.correo_contacto or '').strip()


def _enviar(request, solicitud, informe):
    url = redirect('proyectos:revision_compresion', solicitud_id=solicitud.pk)
    if informe is None or informe.pdf_estado != InformeFinal.PDF_LISTO:
        messages.error(request, "El informe aún no tiene PDF listo.")
        return url
    destinatario = _correo_cliente(solicitud)
    if not destinatario:
        messages.error(request, "El cliente no tiene correo de contacto registrado; no se envió.")
        return url
    enviar_informe_cliente.delay(informe.pk, destinatario)
    messages.success(request, f"El informe se está enviando a {destinatario}.")
    return url


@login_required
def pdf_informe_compresion(request, informe_id):
    """Ver el PDF generado (inline), para quien revisa o ve informes."""
    if not (trabajador_tiene_permiso(request.user, PERMISO_APROBAR)
            or trabajador_tiene_permiso(request.user, 'informes.ver')):
        return HttpResponseForbidden("No tienes permiso para ver informes.")
    informe = get_object_or_404(InformeFinal, pk=informe_id)
    if not informe.archivo_pdf:
        raise Http404("El PDF aún no está disponible.")
    return FileResponse(informe.archivo_pdf.open('rb'), content_type='application/pdf',
                        filename=f"Informe_{informe.codigo_informe}.pdf")


@login_required
@permiso_requerido(PERMISO_EXPORTAR)
def excel_compresion(request):
    solicitud = None
    if request.GET.get('solicitud'):
        solicitud = get_object_or_404(SolicitudEnsayo, pk=request.GET['solicitud'])
    try:
        desde = date.fromisoformat(request.GET['desde']) if request.GET.get('desde') else None
        hasta = date.fromisoformat(request.GET['hasta']) if request.GET.get('hasta') else None
    except ValueError:
        return HttpResponse("Fecha no válida.", status=400)
    contenido = exportar_excel(ensayos_para_excel(solicitud, desde, hasta))
    nombre = f"compresion_{solicitud.codigo_solicitud if solicitud else timezone.localdate():}.xlsx"
    respuesta = HttpResponse(
        contenido, content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
    )
    respuesta['Content-Disposition'] = f'attachment; filename="{nombre}"'
    return respuesta
