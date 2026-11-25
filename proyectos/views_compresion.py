"""Resultados de ensayo: el técnico registra cada línea asignada desde el celular.

Cada línea (muestra × ensayo) usa una plantilla: «compresion» (ASTM C39) o
«general» (resumen, hoja de cálculo y 2 fotos) para los ensayos sin formato
propio todavía. Al terminar la última línea la solicitud queda finalizada sola
(``SolicitudEnsayo.sincronizar_estado``).


- HU-LIMS-11: la recepción completa los datos FOR-004 de cada probeta
  (ID del cliente, elemento, f'c, fabricación, edad) en ``datos_probetas``.
- HU-LIMS-12/13: el técnico abre una sesión de ensayo (T/HR inicial y los seis
  equipos con calibración vigente), registra masa, diámetros, longitudes,
  carga y tipo de fractura de cada probeta, y cierra la sesión con T/HR final.
  Los cálculos salen de ``calculos_compresion`` y se guardan al terminar.
- HU-LIMS-14: las cinco fotos con recorte de proporción fija.

El técnico elige la probeta por su código de laboratorio y nunca ve el nombre
del cliente. Sin todos los datos, las cinco fotos y una sesión abierta del
mismo día no se puede terminar.
"""
import logging
from datetime import date, timedelta
from decimal import Decimal, InvalidOperation

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.db.models import Count, Q
from django.http import FileResponse, Http404, HttpResponseForbidden, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.http import url_has_allowed_host_and_scheme
from urllib.parse import urlencode
from django.views.decorators.http import require_POST

from trabajadores.models import TrabajadorProfile
from trabajadores.permissions import permiso_requerido, trabajador_tiene_permiso, ve_todos_los_ensayos

from .calculos_compresion import DatosInsuficientes
from .forms_compresion import AbrirSesionForm, CerrarSesionForm, DatosClienteProbetaForm, DatosProbetaForm, EquipoForm
from . import programa, trazabilidad
from .fotos import FotoInvalida, procesar_foto
from .models import (
    DetalleSolicitudEnsayo, ResultadoEnsayo, Equipo, FotoEnsayo, InformeFinal, MuestraDetalle,
    RecepcionMuestra, SesionEnsayo, SolicitudEnsayo,
)

logger = logging.getLogger(__name__)

PERMISO_REGISTRAR = 'ensayos.registrar'
PERMISO_DATOS_PROBETA = 'muestras.editar'
PERMISO_EQUIPOS_VER = 'equipos.ver'
PERMISO_EQUIPOS_EDITAR = 'equipos.editar'

# Rangos de captura razonables (mm, g, kN): evitan un 1020 por 102,0.
RANGOS_MEDIDAS = {
    'masa_g': (Decimal('100'), Decimal('50000')),
    'd1': (Decimal('20'), Decimal('400')),
    'd2': (Decimal('20'), Decimal('400')),
    'l1': (Decimal('20'), Decimal('800')),
    'l2': (Decimal('20'), Decimal('800')),
    'l3': (Decimal('20'), Decimal('800')),
    'carga_kn': (Decimal('0.1'), Decimal('5000')),
}

FILTRO_COMPRESION = (
    Q(norma__icontains='C39')
    | Q(servicio_cotizado__servicio__codigo_facturacion__iexact='EC001')
)


def _detalles_visibles(user):
    qs = DetalleSolicitudEnsayo.objects.all()
    if not ve_todos_los_ensayos(user):
        qs = qs.filter(tecnico_asignado__user=user)
    return qs


def _detalle_o_404(user, detalle_id):
    """La línea si el usuario puede verla; si no, 404 (CA-20.2)."""
    return get_object_or_404(
        _detalles_visibles(user).select_related(
            'muestra', 'solicitud', 'tecnico_asignado', 'resultado', 'servicio_cotizado__servicio',
        ),
        pk=detalle_id,
    )


def _ensayo_de(detalle):
    try:
        return detalle.resultado
    except ResultadoEnsayo.DoesNotExist:
        return None


def _perfil(user):
    try:
        return user.trabajadorprofile
    except TrabajadorProfile.DoesNotExist:
        return None


def _ejecutor(user, detalle):
    """Técnico a cuyo nombre queda la línea.

    El técnico asignado registra lo suyo. Quien ve todos los ensayos (supervisor,
    o quien pasa a limpio el formato en papel) registra a nombre del técnico
    asignado: la sesión y «Ejecutado por» son del técnico, no de quien escribe.
    """
    propio = _perfil(user)
    asignado = detalle.tecnico_asignado
    if asignado and asignado.user_id != user.pk and ve_todos_los_ensayos(user):
        return asignado
    return propio


def _perfil_elegido(request, valor):
    """El técnico que pide ``?tecnico=`` (solo quien ve todo); si no, el propio."""
    propio = _perfil(request.user)
    if valor and ve_todos_los_ensayos(request.user):
        try:
            return TrabajadorProfile.objects.get(pk=int(valor))
        except (ValueError, TrabajadorProfile.DoesNotExist):
            raise Http404("Técnico no encontrado.")
    return propio


def _volver(request, defecto):
    """URL interna de regreso (``volver``) o la de por defecto."""
    destino = request.POST.get('volver') or request.GET.get('volver') or ''
    if destino and url_has_allowed_host_and_scheme(destino, allowed_hosts={request.get_host()},
                                                   require_https=request.is_secure()):
        return destino
    return defecto


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
        .select_related('muestra', 'solicitud', 'resultado', 'tecnico_asignado')
        .annotate(n_fotos=Count('resultado__fotos'))
        .order_by('fecha_entrega_programada', 'muestra__codigo_laboratorio')
    )
    terminado = Q(resultado__estado__in=ResultadoEnsayo.ESTADOS_CERRADOS)
    detalles = detalles.filter(terminado) if vista == 'terminados' else detalles.exclude(terminado)

    detalles = list(detalles.select_related('servicio_cotizado__servicio')[:200])
    for d in detalles:
        e = _ensayo_de(d)
        d.plantilla = e.plantilla if e else ResultadoEnsayo.plantilla_para(d)
        d.total_fotos = FotoEnsayo.total_requerido(d.plantilla)
    sesion = SesionEnsayo.abierta_de(_perfil(request.user))
    return render(request, 'proyectos/compresion_lista.html', {
        'detalles': detalles,
        'vista': vista,
        'hoy': timezone.localdate(),
        'sesion': sesion,
        'form_cerrar': CerrarSesionForm(instance=sesion) if sesion else None,
        'puede_abrir': _perfil(request.user) is not None,
    })


@login_required
@permiso_requerido(PERMISO_REGISTRAR)
def registrar_ensayo_compresion(request, detalle_id):
    detalle = _detalle_o_404(request.user, detalle_id)
    ensayo = _ensayo_de(detalle)
    ve_todos = ve_todos_los_ensayos(request.user)
    ejecutor = _ejecutor(request.user, detalle)
    a_nombre_de = ejecutor if ejecutor is not None and ejecutor != _perfil(request.user) else None
    desde = request.GET.get('desde') or request.POST.get('desde')
    desde_solicitud = desde == 'solicitud'
    url = reverse('proyectos:registrar_compresion', args=[detalle.pk])
    url_salida = (reverse('proyectos:resultados_solicitud', args=[detalle.solicitud_id]) if desde_solicitud
                  else reverse('proyectos:mis_ensayos_compresion'))
    salida_texto = f'Solicitud {detalle.solicitud.codigo_solicitud}' if desde_solicitud else 'Mis ensayos'
    if desde_solicitud:
        url += '?desde=solicitud'
    elif desde == 'programa':
        # Desde la hoja del programa del día (HU-LIMS-21): al terminar vuelve a ella.
        fecha_programa = programa.leer_fecha(request.GET.get('fecha'), None)
        cliente_programa = request.GET.get('cliente') or ''
        if fecha_programa and cliente_programa.isdigit():
            url += '?' + urlencode({'desde': 'programa', 'fecha': fecha_programa.isoformat(),
                                    'cliente': cliente_programa})
            url_salida = reverse('proyectos:programa_cliente',
                                 args=[fecha_programa.isoformat(), int(cliente_programa)])
            salida_texto = f'Programa del {fecha_programa:%d/%m/%Y}'

    if request.method == 'POST':
        accion = request.POST.get('accion', 'guardar')

        if accion == 'reabrir':
            if not ve_todos or ensayo is None:
                return HttpResponseForbidden("Solo el supervisor puede reabrir un ensayo terminado.")
            if ensayo.aprobado:
                messages.error(request, "La probeta ya está aprobada en un informe; no se puede reabrir.")
                return redirect(url)
            ensayo.estado = ResultadoEnsayo.ESTADO_BORRADOR
            ensayo.terminado_en = None
            ensayo.save(update_fields=['estado', 'terminado_en', 'actualizado_en'])
            detalle.solicitud.sincronizar_estado()
            messages.success(request, "El ensayo volvió a quedar abierto para el técnico.")
            return redirect(url)

        if ensayo is not None and ensayo.terminado:
            messages.error(request, "Este ensayo ya está terminado; no se puede modificar.")
            return redirect(url)

        if ensayo is None:
            ensayo = ResultadoEnsayo.objects.create(
                detalle=detalle, plantilla=ResultadoEnsayo.plantilla_para(detalle),
            )
            detalle.solicitud.sincronizar_estado()

        if ensayo.es_compresion and 'muestra-fc_diseno' in request.POST:
            error = _aplicar_datos_cliente(request, detalle, ensayo)
            if error:
                messages.error(request, error)
                return redirect(url)
        aplicar = _aplicar_datos if ensayo.es_compresion else _aplicar_datos_generales
        error = aplicar(request, detalle, ensayo)
        if error:
            messages.error(request, error)
            return redirect(url)

        if accion == 'terminar' and not ensayo.es_compresion:
            faltan = ensayo.faltantes_para_terminar()
            if faltan:
                messages.error(request, "Para terminar falta " + ", ".join(faltan) + ".")
                return redirect(url)
            _cerrar_linea(request, detalle, ensayo, sesion=SesionEnsayo.abierta_de(ejecutor), ejecutor=ejecutor)
            return redirect(url_salida)

        if accion == 'terminar':
            faltan = ensayo.faltantes_para_terminar()
            if faltan:
                messages.error(request, "Para terminar falta " + ", ".join(faltan) + ".")
                return redirect(url)
            sesion = SesionEnsayo.abierta_de(ejecutor)
            if sesion is None:
                if a_nombre_de:
                    messages.error(request, f"Abre primero la sesión de ensayo de {a_nombre_de.nombre_completo} "
                                            "(condiciones ambientales y equipos del formato).")
                else:
                    messages.error(request, "Abre primero tu sesión de ensayo (condiciones ambientales y equipos).")
                return redirect(url)
            if sesion.fecha != ensayo.fecha_ensayo:
                messages.error(
                    request,
                    f"La fecha de ensayo ({ensayo.fecha_ensayo:%d/%m/%Y}) no coincide con la de tu sesión "
                    f"abierta ({sesion.fecha:%d/%m/%Y}).",
                )
                return redirect(url)
            try:
                ensayo.guardar_resultados()
            except DatosInsuficientes as exc:
                messages.error(request, str(exc))
                return redirect(url)
            _cerrar_linea(request, detalle, ensayo, sesion=sesion, ejecutor=ejecutor)
            return redirect(url_salida)

        messages.success(request, "Datos guardados.")
        return redirect(url)

    plantilla = ensayo.plantilla if ensayo else ResultadoEnsayo.plantilla_para(detalle)
    es_compresion_plantilla = plantilla == ResultadoEnsayo.PLANTILLA_COMPRESION
    fotos = {f.tipo: f for f in ensayo.fotos.all()} if ensayo else {}
    # Compresión: 5 recuadros fijos con recorte. General: galería libre.
    galeria = list(ensayo.fotos.order_by('pk')) if ensayo and not es_compresion_plantilla else []
    slots = [
        {
            'tipo': codigo,
            'etiqueta': etiqueta,
            'proporcion': FotoEnsayo.proporcion(codigo),
            'ancho': FotoEnsayo.PROPORCIONES[codigo][0],
            'alto': FotoEnsayo.PROPORCIONES[codigo][1],
            'foto': fotos.get(codigo),
        }
        for codigo, etiqueta in FotoEnsayo.tipos_de(plantilla)
    ] if es_compresion_plantilla else []
    orden = FotoEnsayo.ORDEN_TOMA if plantilla == ResultadoEnsayo.PLANTILLA_COMPRESION else [x['tipo'] for x in slots]
    slots.sort(key=lambda x: orden.index(x['tipo']))
    for n, slot in enumerate(slots, 1):
        slot['numero'] = n
    sesion = SesionEnsayo.abierta_de(ejecutor)
    resultado, error_calculo = None, None
    if ensayo is not None and ensayo.es_compresion:
        try:
            resultado = ensayo.calcular()
        except DatosInsuficientes as exc:
            error_calculo = str(exc)
    muestra = detalle.muestra
    return render(request, 'proyectos/compresion_registro.html', {
        'detalle': detalle,
        'ensayo': ensayo,
        'plantilla': plantilla,
        'es_compresion': plantilla == ResultadoEnsayo.PLANTILLA_COMPRESION,
        'muestra': muestra,
        'datos_probeta_completos': bool(muestra.fecha_fabricacion and muestra.fc_diseno),
        'form_cliente': DatosClienteProbetaForm(instance=muestra, prefix='muestra'),
        'foto': {s['tipo']: s for s in slots},
        'cambios': list(ensayo.cambios.select_related('usuario')) if ensayo else [],
        'sesion': sesion,
        'sesion_ensayo': ensayo.sesion if ensayo else None,
        'resultado': resultado,
        'error_calculo': error_calculo,
        'medidas': _medidas_para_formulario(ensayo),
        'fracturas': [n for n in range(1, 7)],
        'verificaciones': [
            {'campo': c, 'etiqueta': ResultadoEnsayo._meta.get_field(c).verbose_name,
             'valor': getattr(ensayo, c) if ensayo else None}
            for c in ('verif_perpendicularidad', 'verif_planitud')
        ],
        'tipos_defecto': ResultadoEnsayo.TIPOS_DEFECTO,
        'defectos_marcados': ensayo.lista_defectos if ensayo else [],
        'slots': slots,
        'galeria': galeria,
        'min_fotos': FotoEnsayo.MIN_FOTOS_GENERAL,
        'max_fotos': FotoEnsayo.MAX_FOTOS_GENERAL,
        'solo_lectura': bool(ensayo and ensayo.terminado),
        've_todos': ve_todos,
        'fecha_minima': _fecha_minima(detalle),
        'hoy': timezone.localdate(),
        'lado_maximo': FotoEnsayo.LADO_MAXIMO,
        'a_nombre_de': a_nombre_de,
        'desde_solicitud': desde_solicitud,
        'url_salida': url_salida,
        'salida_texto': salida_texto,
        'url_abrir_sesion': _url_abrir_sesion(a_nombre_de, url),
    })


ESTADOS_LINEA = {
    None: ('Sin empezar', 'gris'),
    ResultadoEnsayo.ESTADO_BORRADOR: ('En registro', 'ambar'),
    ResultadoEnsayo.ESTADO_TERMINADO: ('Terminado', 'verde'),
    ResultadoEnsayo.ESTADO_APROBADO: ('Aprobado', 'azul'),
}


@login_required
@permiso_requerido('ensayos.ver')
def resultados_solicitud(request, solicitud_id):
    """Pantalla completa de una solicitud: los 4 pasos y cada ensayo por registrar.

    Se llega desde el icono verde de la lista de solicitudes. El técnico ve sus
    líneas; quien ve todos los ensayos ve todas y puede registrarlas a nombre del
    técnico asignado (formato en papel). La solicitud se finaliza sola al terminar
    la última línea y pasa a revisión; después, el editor del informe.
    """
    solicitud = get_object_or_404(
        SolicitudEnsayo.objects.select_related('cotizacion__cliente'), pk=solicitud_id,
    )
    ve_todos = ve_todos_los_ensayos(request.user)
    todas = list(
        solicitud.detalles.select_related(
            'muestra', 'resultado', 'tecnico_asignado', 'servicio_cotizado__servicio',
        ).annotate(n_fotos=Count('resultado__fotos')).order_by('muestra__codigo_laboratorio', 'pk')
    )
    propias = [d for d in todas if ve_todos or (d.tecnico_asignado and d.tecnico_asignado.user_id == request.user.pk)]
    if not propias:
        return HttpResponseForbidden("No tienes asignado ningún ensayo de esta solicitud.")

    puede_registrar = trabajador_tiene_permiso(request.user, PERMISO_REGISTRAR)
    propio = _perfil(request.user)
    volver = reverse('proyectos:resultados_solicitud', args=[solicitud.pk])
    tecnicos = {}
    for d in propias:
        e = _ensayo_de(d)
        d.ensayo = e
        d.plantilla = e.plantilla if e else ResultadoEnsayo.plantilla_para(d)
        d.total_fotos = FotoEnsayo.total_requerido(d.plantilla)
        estado = e.estado if e else None
        d.estado_texto, d.estado_color = ESTADOS_LINEA[estado]
        if e and e.observacion_revision and not e.terminado:
            d.estado_texto, d.estado_color = 'Devuelto', 'rojo'
        d.a_nombre = bool(d.tecnico_asignado and d.tecnico_asignado.user_id != request.user.pk)
        if d.plantilla == ResultadoEnsayo.PLANTILLA_COMPRESION and not (e and e.terminado):
            ejecutor = _ejecutor(request.user, d)
            if ejecutor is not None:
                tecnicos[ejecutor.pk] = ejecutor

    sesiones = []
    for t in tecnicos.values():
        abierta = SesionEnsayo.abierta_de(t)
        ajeno = t != propio
        sesiones.append({
            'tecnico': t,
            'ajeno': ajeno,
            'sesion': abierta,
            'url_abrir': _url_abrir_sesion(t if ajeno else None, volver),
            'form_cerrar': CerrarSesionForm(instance=abierta) if abierta else None,
        })

    terminadas = sum(1 for d in todas if _ensayo_de(d) and _ensayo_de(d).terminado)
    aprobadas = sum(1 for d in todas if _ensayo_de(d) and _ensayo_de(d).aprobado)
    total = len(todas)
    informe = getattr(solicitud, 'informe_final', None) if hasattr(solicitud, 'informe_final') else None
    emitido = bool(informe and (informe.pdf_estado == InformeFinal.PDF_LISTO
                                or (not informe.pdf_estado and informe.archivo_pdf)))
    puede_aprobar = trabajador_tiene_permiso(request.user, 'informes.aprobar')
    pasos = [
        {'n': 1, 'titulo': 'Iniciar', 'hecho': solicitud.estado != 'pendiente',
         'detalle': 'En proceso' if solicitud.estado != 'pendiente' else 'Pendiente'},
        {'n': 2, 'titulo': 'Registrar resultados', 'hecho': total and terminadas == total,
         'detalle': f'{terminadas} de {total} terminados'},
        {'n': 3, 'titulo': 'Revisión', 'hecho': total and aprobadas == total,
         'detalle': f'{aprobadas} de {total} aprobados'},
        {'n': 4, 'titulo': 'Informe', 'hecho': emitido,
         'detalle': informe.codigo_informe if emitido else 'Por emitir'},
    ]
    for p in pasos:
        p['actual'] = False
    actual = next((p for p in pasos if not p['hecho']), None)
    if actual:
        actual['actual'] = True

    from .plazos import estado_plazo, plazo_solicitud
    plazo = plazo_solicitud(solicitud)
    faltan_datos_cliente = [
        d.muestra.codigo_laboratorio for d in propias
        if d.plantilla == ResultadoEnsayo.PLANTILLA_COMPRESION
        and not (d.muestra.fc_diseno and d.muestra.fecha_fabricacion)
    ]
    return render(request, 'proyectos/resultados_solicitud.html', {
        'solicitud': solicitud,
        'detalles': propias,
        'ocultas': len(todas) - len(propias),
        'pasos': pasos,
        'paso_actual': actual['n'] if actual else None,
        'terminadas': terminadas,
        'aprobadas': aprobadas,
        'total': total,
        'porcentaje': round(terminadas * 100 / total) if total else 0,
        'emitido': emitido,
        'informe': informe,
        've_todos': ve_todos,
        'puede_registrar': puede_registrar,
        'puede_aprobar': puede_aprobar,
        'puede_iniciar': trabajador_tiene_permiso(request.user, 'ensayos.editar'),
        'sesiones': sesiones,
        'volver': volver,
        'plazo': plazo,
        'estado_plazo': estado_plazo(plazo, entregado=emitido),
        'faltan_datos_cliente': faltan_datos_cliente,
        'hay_compresion_pendiente': any(
            d.plantilla == ResultadoEnsayo.PLANTILLA_COMPRESION and not (d.ensayo and d.ensayo.terminado)
            for d in propias),
    })


CAMPOS_MEDIDAS_LOTE = ['masa_g', 'd1', 'd2', 'l1', 'l2', 'l3']


@login_required
@permiso_requerido(PERMISO_REGISTRAR)
def medidas_solicitud(request, solicitud_id):
    """Medir y pesar todas las probetas de la solicitud de corrido, antes de romperlas.

    Así trabaja el laboratorio cuando hay varias probetas: primero masa, D1-D2
    y L1-L3 de todas; después cada una pasa a la prensa desde su registro.
    """
    solicitud = get_object_or_404(SolicitudEnsayo, pk=solicitud_id)
    pantalla = reverse('proyectos:resultados_solicitud', args=[solicitud.pk])
    ve_todos = ve_todos_los_ensayos(request.user)
    lineas = []
    for d in solicitud.detalles.select_related('muestra', 'resultado', 'tecnico_asignado', 'solicitud__recepcion',
                                               'servicio_cotizado__servicio').order_by('muestra__codigo_laboratorio', 'pk'):
        if not (ve_todos or (d.tecnico_asignado and d.tecnico_asignado.user_id == request.user.pk)):
            continue
        e = _ensayo_de(d)
        plantilla = e.plantilla if e else ResultadoEnsayo.plantilla_para(d)
        if plantilla != ResultadoEnsayo.PLANTILLA_COMPRESION:
            continue
        d.ensayo = e
        lineas.append(d)
    if not lineas:
        messages.error(request, "Esta solicitud no tiene probetas de compresión tuyas para medir.")
        return redirect(pantalla)
    return _medidas_en_lote(request, lineas, pantalla, solicitud.codigo_solicitud)


def _medidas_en_lote(request, lineas, pantalla, titulo, fecha_inicial=None):
    """Formulario «medir y pesar todas»: lo usan la solicitud y el programa del día.

    Cada corrección de un dato ya guardado queda en la trazabilidad y cada
    solicitud tocada recalcula su estado.
    """
    etiquetas = {f.name: str(f.verbose_name) for f in ResultadoEnsayo._meta.fields}
    errores = []
    if request.method == 'POST':
        # La fecha no puede ser anterior a la recepción más reciente del lote.
        referencia = max(lineas, key=lambda d: _fecha_minima(d) or date.min)
        fecha, error = _leer_fecha(request, referencia)
        if error:
            errores.append(error)
        lecturas = {}
        for d in lineas:
            if d.ensayo is not None and d.ensayo.terminado:
                continue
            valores = {}
            for campo in CAMPOS_MEDIDAS_LOTE:
                try:
                    valores[campo] = _leer_decimal(request.POST.get(f'{campo}-{d.pk}'), etiquetas[campo],
                                                   RANGOS_MEDIDAS[campo])
                except ValueError as exc:
                    errores.append(f"{d.muestra.codigo_laboratorio}: {exc}")
            lecturas[d.pk] = valores
        if not errores:
            guardadas = 0
            solicitudes = {}
            with transaction.atomic():
                for d in lineas:
                    valores = lecturas.get(d.pk)
                    if valores is None or not any(v is not None for v in valores.values()):
                        continue
                    ensayo = d.ensayo or ResultadoEnsayo.objects.create(
                        detalle=d, plantilla=ResultadoEnsayo.PLANTILLA_COMPRESION,
                    )
                    antes = trazabilidad.instantanea(ensayo, trazabilidad.CAMPOS_RESULTADO)
                    for campo, valor in valores.items():
                        setattr(ensayo, campo, valor)
                    if fecha:
                        ensayo.fecha_ensayo = fecha
                    ensayo.save(update_fields=[*CAMPOS_MEDIDAS_LOTE, 'fecha_ensayo', 'actualizado_en'])
                    trazabilidad.anotar_cambios(ensayo, ensayo, antes, trazabilidad.CAMPOS_RESULTADO, request.user)
                    solicitudes[d.solicitud_id] = d.solicitud
                    guardadas += 1
                for solicitud in solicitudes.values():
                    solicitud.sincronizar_estado()
            messages.success(request, f"Medidas guardadas de {guardadas} probeta{'s' if guardadas != 1 else ''}. "
                                      "Ahora ensaya cada una en la prensa.")
            return redirect(pantalla)

    filas = []
    for d in lineas:
        e = d.ensayo
        filas.append({
            'detalle': d,
            'terminado': bool(e and e.terminado),
            'campos': [
                {'campo': c, 'etiqueta': etiquetas[c].split(' (')[0], 'nombre': f'{c}-{d.pk}',
                 'valor': request.POST.get(f'{c}-{d.pk}', '') if request.method == 'POST'
                 else ('' if e is None or getattr(e, c) is None else getattr(e, c))}
                for c in CAMPOS_MEDIDAS_LOTE
            ],
        })
    fecha_actual = next((d.ensayo.fecha_ensayo for d in lineas if d.ensayo and d.ensayo.fecha_ensayo), None)
    fecha_actual = fecha_actual or fecha_inicial or timezone.localdate()
    return render(request, 'proyectos/medidas_solicitud.html', {
        'titulo': titulo,
        'filas': filas,
        'errores': errores,
        'pantalla': pantalla,
        'fecha': request.POST.get('fecha_ensayo') if request.method == 'POST' else fecha_actual.isoformat(),
        'hoy': timezone.localdate(),
    })


def _url_abrir_sesion(tecnico, volver):
    """Abrir sesión propia o, al pasar el formato en papel, a nombre del técnico."""
    url = reverse('proyectos:abrir_sesion_ensayo')
    if tecnico is None:
        return url
    return f"{url}?{urlencode({'tecnico': tecnico.pk, 'volver': volver})}"


def _cerrar_linea(request, detalle, ensayo, sesion=None, ejecutor=None):
    """Termina la línea: queda bloqueada, con su técnico y fecha real, y la solicitud se sincroniza."""
    propio = _perfil(request.user)
    ejecutor = ejecutor or propio
    ensayo.sesion = sesion
    ensayo.estado = ResultadoEnsayo.ESTADO_TERMINADO
    ensayo.terminado_en = timezone.now()
    ensayo.tecnico = ejecutor
    ensayo.registrado_por = propio if propio and propio != ejecutor else None
    ensayo.observacion_revision = ''
    ensayo.save()
    DetalleSolicitudEnsayo.objects.filter(pk=detalle.pk).update(fecha_entrega_real=timezone.localdate())
    solicitud = detalle.solicitud
    solicitud.sincronizar_estado()
    terminadas, total = solicitud.avance_resultados()
    texto = f"{detalle.muestra.codigo_laboratorio} terminada ({terminadas} de {total} de la solicitud)."
    if terminadas == total:
        texto += " La solicitud quedó finalizada y pasa a revisión."
    messages.success(request, texto)


EXTENSIONES_HOJA = ('.xlsx', '.xls', '.ods', '.csv', '.pdf')
HOJA_MAXIMO = 15 * 1024 * 1024


def _leer_fecha(request, detalle):
    """(fecha o None, error o None) de ``fecha_ensayo``."""
    texto_fecha = (request.POST.get('fecha_ensayo') or '').strip()
    if not texto_fecha:
        return None, None
    try:
        fecha = date.fromisoformat(texto_fecha)
    except ValueError:
        return None, "La fecha de ensayo no es válida."
    if fecha > timezone.localdate():
        return None, "La fecha de ensayo no puede ser futura."
    minima = _fecha_minima(detalle)
    if minima and fecha < minima:
        return None, f"La fecha de ensayo no puede ser anterior a la recepción ({minima:%d/%m/%Y})."
    return fecha, None


def _aplicar_datos_cliente(request, detalle, ensayo):
    """Datos que da el cliente (f'c, moldeo, edad, su código): el técnico los copia al empezar."""
    muestra = detalle.muestra
    antes = trazabilidad.instantanea(muestra, trazabilidad.CAMPOS_MUESTRA)
    form = DatosClienteProbetaForm(request.POST, instance=muestra, prefix='muestra')
    if not form.is_valid():
        errores = [f"{form.fields[c].label}: {e}" if c in form.fields else str(e)
                   for c, lista in form.errors.items() for e in lista]
        return "Datos de la probeta: " + " ".join(errores)
    form.save()
    trazabilidad.anotar_cambios(ensayo, muestra, antes, trazabilidad.CAMPOS_MUESTRA, request.user, prefijo='probeta:')
    return None


def _aplicar_datos_generales(request, detalle, ensayo):
    """Plantilla general: fecha, resumen, observaciones y la hoja de cálculo del ensayo."""
    fecha, error = _leer_fecha(request, detalle)
    if error:
        return error
    antes = trazabilidad.instantanea(ensayo, trazabilidad.CAMPOS_RESULTADO)
    hoja = request.FILES.get('hoja_calculo')
    if hoja:
        if not hoja.name.lower().endswith(EXTENSIONES_HOJA):
            return "La hoja debe ser Excel, ODS, CSV o PDF."
        if hoja.size > HOJA_MAXIMO:
            return "La hoja pesa más de 15 MB."
        anterior = ensayo.hoja_calculo.name if ensayo.hoja_calculo else None
        ensayo.hoja_calculo.save(hoja.name, hoja, save=False)
        if anterior:
            from .models import CambioResultado
            CambioResultado.objects.create(
                resultado=ensayo, campo='hoja_calculo', etiqueta='Hoja de cálculo',
                anterior='hoja anterior', nuevo=hoja.name[:255], usuario=request.user,
            )
            try:
                ensayo.hoja_calculo.storage.delete(anterior)
            except OSError:
                logger.warning("No se pudo borrar la hoja reemplazada %s", anterior)
    ensayo.fecha_ensayo = fecha
    ensayo.resumen = (request.POST.get('resumen') or '').strip()[:5000]
    ensayo.observaciones = (request.POST.get('observaciones') or '').strip()
    ensayo.save()
    trazabilidad.anotar_cambios(ensayo, ensayo, antes, trazabilidad.CAMPOS_RESULTADO, request.user)
    return None


@login_required
def hoja_resultado(request, detalle_id):
    """Descarga la hoja de cálculo desde la carpeta privada, solo a quien ve la línea."""
    revisor = trabajador_tiene_permiso(request.user, 'informes.ver') or trabajador_tiene_permiso(
        request.user, 'informes.aprobar'
    )
    if revisor:
        detalle = get_object_or_404(DetalleSolicitudEnsayo.objects.select_related('muestra'), pk=detalle_id)
    elif trabajador_tiene_permiso(request.user, PERMISO_REGISTRAR):
        detalle = get_object_or_404(_detalles_visibles(request.user).select_related('muestra'), pk=detalle_id)
    else:
        detalle = None
    ensayo = _ensayo_de(detalle) if detalle else None
    if ensayo is None or not ensayo.hoja_calculo:
        raise Http404("Hoja no encontrada.")
    try:
        archivo = ensayo.hoja_calculo.open('rb')
    except FileNotFoundError:
        raise Http404("La hoja ya no está disponible.")
    nombre = f"{detalle.muestra.codigo_laboratorio}{ensayo.hoja_calculo.name[ensayo.hoja_calculo.name.rfind('.'):]}"
    return FileResponse(archivo, as_attachment=True, filename=nombre)


def _medidas_para_formulario(ensayo):
    etiquetas = {f.name: f.verbose_name for f in ResultadoEnsayo._meta.fields}
    return [
        {
            'campo': campo,
            'etiqueta': etiquetas[campo],
            'valor': '' if ensayo is None or getattr(ensayo, campo) is None else getattr(ensayo, campo),
            'paso': '0.1' if campo == 'masa_g' else '0.01',
        }
        for campo in ResultadoEnsayo.CAMPOS_MEDIDOS
    ]


def _leer_decimal(texto, etiqueta, rango):
    """Decimal del formulario (acepta coma) o None si está vacío. ValueError si no vale."""
    texto = (texto or '').strip().replace(',', '.')
    if not texto:
        return None
    try:
        valor = Decimal(texto)
    except InvalidOperation:
        raise ValueError(f"{etiqueta}: «{texto}» no es un número.")
    if not valor.is_finite():
        raise ValueError(f"{etiqueta}: «{texto}» no es un número.")
    minimo, maximo = rango
    if not (minimo <= valor <= maximo):
        raise ValueError(f"{etiqueta} debe estar entre {minimo} y {maximo}.")
    return valor


def _aplicar_datos(request, detalle, ensayo):
    """Valida y guarda fecha, medidas, fractura y observaciones. Devuelve un error o None."""
    fecha, error = _leer_fecha(request, detalle)
    if error:
        return error
    etiquetas = {f.name: str(f.verbose_name) for f in ResultadoEnsayo._meta.fields}
    medidas = {}
    for campo in ResultadoEnsayo.CAMPOS_MEDIDOS:
        try:
            medidas[campo] = _leer_decimal(request.POST.get(campo), etiquetas[campo], RANGOS_MEDIDAS[campo])
        except ValueError as exc:
            return str(exc)
    texto_fractura = (request.POST.get('tipo_fractura') or '').strip()
    fractura = None
    if texto_fractura:
        if texto_fractura not in {str(n) for n in range(1, 7)}:
            return "El tipo de fractura debe ser del 1 al 6."
        fractura = int(texto_fractura)

    antes = trazabilidad.instantanea(ensayo, trazabilidad.CAMPOS_RESULTADO)
    ensayo.fecha_ensayo = fecha
    for campo, valor in medidas.items():
        setattr(ensayo, campo, valor)
    ensayo.tipo_fractura = fractura
    validos = dict(ResultadoEnsayo.TIPOS_DEFECTO)
    ensayo.tipos_defecto = ','.join(c for c, _ in ResultadoEnsayo.TIPOS_DEFECTO
                                    if c in set(request.POST.getlist('tipos_defecto')) and c in validos)
    ensayo.defectos = (request.POST.get('defectos') or '').strip()[:255]
    for campo in ('verif_perpendicularidad', 'verif_planitud'):
        valor = request.POST.get(campo)
        setattr(ensayo, campo, {'1': True, '0': False}.get(valor))
    ensayo.video_grabado = request.POST.get('video_grabado') == '1'
    ensayo.observaciones = (request.POST.get('observaciones') or '').strip()
    ensayo.save(update_fields=[
        'fecha_ensayo', 'observaciones', 'tipo_fractura', 'defectos', 'actualizado_en',
        'tipos_defecto', 'verif_perpendicularidad', 'verif_planitud', 'video_grabado',
        *ResultadoEnsayo.CAMPOS_MEDIDOS,
    ])
    trazabilidad.anotar_cambios(ensayo, ensayo, antes, trazabilidad.CAMPOS_RESULTADO, request.user)
    return None


@login_required
@require_POST
def subir_foto_compresion(request, detalle_id, tipo):
    if not trabajador_tiene_permiso(request.user, PERMISO_REGISTRAR):
        return JsonResponse({'ok': False, 'error': 'No tienes permiso para registrar ensayos.'}, status=403)
    if tipo not in FotoEnsayo.PROPORCIONES:
        raise Http404("Tipo de foto desconocido.")

    detalle = _detalle_o_404(request.user, detalle_id)
    plantilla = detalle.resultado.plantilla if _ensayo_de(detalle) else ResultadoEnsayo.plantilla_para(detalle)
    if tipo not in dict(FotoEnsayo.tipos_de(plantilla)):
        raise Http404("Este ensayo no pide esa foto.")
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
            ensayo, _ = ResultadoEnsayo.objects.get_or_create(detalle=detalle, defaults={'plantilla': plantilla})
        if tipo == FotoEnsayo.TIPO_GENERAL:
            # Galería: cada foto se agrega, hasta el máximo.
            ResultadoEnsayo.objects.select_for_update().filter(pk=ensayo.pk).first()
            if ensayo.fotos.count() >= FotoEnsayo.MAX_FOTOS_GENERAL:
                return JsonResponse({'ok': False, 'error': f'Se admiten hasta {FotoEnsayo.MAX_FOTOS_GENERAL} fotos.'},
                                    status=400)
            foto = FotoEnsayo(ensayo=ensayo, tipo=tipo, subido_por=request.user)
            foto.imagen.save('foto.jpg', contenido, save=False)
            foto.save()
            return JsonResponse({
                'ok': True, 'id': foto.pk,
                'url': reverse('proyectos:foto_compresion', args=[foto.pk]),
                'borrar': reverse('proyectos:borrar_foto_compresion', args=[foto.pk]),
                'total': ensayo.fotos.count(),
                'faltan': ensayo.faltantes_para_terminar(),
            })
        foto = FotoEnsayo.objects.select_for_update().filter(ensayo=ensayo, tipo=tipo).first()
        anterior = foto.imagen.name if foto and foto.imagen else None
        if foto is None:
            foto = FotoEnsayo(ensayo=ensayo, tipo=tipo)
        foto.subido_por = request.user
        foto.imagen.save('foto.jpg', contenido, save=False)
        foto.save()

    if anterior:
        trazabilidad.anotar_foto_reemplazada(ensayo, dict(FotoEnsayo.TIPOS).get(tipo, tipo), request.user)
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
@require_POST
def borrar_foto_compresion(request, foto_id):
    """Quita una foto de la galería del ensayo general (queda en la trazabilidad)."""
    if not trabajador_tiene_permiso(request.user, PERMISO_REGISTRAR):
        return JsonResponse({'ok': False, 'error': 'No tienes permiso para registrar ensayos.'}, status=403)
    foto = get_object_or_404(FotoEnsayo.objects.select_related('ensayo'), pk=foto_id)
    _detalle_o_404(request.user, foto.ensayo.detalle_id)
    ensayo = foto.ensayo
    if ensayo.terminado:
        return JsonResponse({'ok': False, 'error': 'El ensayo ya está terminado.'}, status=409)
    if ensayo.es_compresion:
        return JsonResponse({'ok': False, 'error': 'Las fotos de compresión se reemplazan, no se borran.'}, status=400)
    nombre = foto.imagen.name
    etiqueta = foto.get_tipo_display()
    foto.delete()
    trazabilidad.anotar_foto_borrada(ensayo, etiqueta, request.user)
    try:
        if nombre:
            FotoEnsayo._meta.get_field('imagen').storage.delete(nombre)
    except OSError:
        logger.warning("No se pudo borrar el archivo de la foto %s", nombre)
    return JsonResponse({'ok': True, 'total': ensayo.fotos.count(), 'faltan': ensayo.faltantes_para_terminar()})


@login_required
def foto_compresion(request, foto_id):
    """Sirve la foto desde la carpeta privada, solo a quien puede ver la probeta."""
    foto = get_object_or_404(FotoEnsayo.objects.select_related('ensayo__detalle'), pk=foto_id)
    # Quien revisa o redacta informes ve todas; el técnico, solo las de sus líneas.
    revisor = trabajador_tiene_permiso(request.user, 'informes.ver') or trabajador_tiene_permiso(
        request.user, 'informes.aprobar'
    )
    tecnico = trabajador_tiene_permiso(request.user, PERMISO_REGISTRAR) and _detalles_visibles(
        request.user
    ).filter(pk=foto.ensayo.detalle_id).exists()
    if not (revisor or tecnico):
        raise Http404("Foto no encontrada.")
    try:
        archivo = foto.imagen.open('rb')
    except FileNotFoundError:
        raise Http404("La foto ya no está disponible.")
    respuesta = FileResponse(archivo, content_type='image/jpeg')
    respuesta['Cache-Control'] = 'private, max-age=3600'
    return respuesta


# --- Sesión de ensayo (HU-LIMS-12/13) -------------------------------------

@login_required
@permiso_requerido(PERMISO_REGISTRAR)
def abrir_sesion_ensayo(request):
    propio = _perfil(request.user)
    perfil = _perfil_elegido(request, request.GET.get('tecnico'))
    volver = _volver(request, reverse('proyectos:mis_ensayos_compresion'))
    if perfil is None:
        messages.error(request, "Tu usuario no tiene ficha de trabajador; pide que la creen para abrir sesiones.")
        return redirect('proyectos:mis_ensayos_compresion')
    a_nombre_de = perfil if perfil != propio else None
    if SesionEnsayo.abierta_de(perfil):
        if a_nombre_de:
            messages.error(request, f"{perfil.nombre_completo} ya tiene una sesión abierta; ciérrala antes de abrir otra.")
        else:
            messages.error(request, "Ya tienes una sesión abierta; ciérrala antes de abrir otra.")
        return redirect(volver)

    form = AbrirSesionForm(request.POST or None, initial={'fecha': timezone.localdate()})
    if request.method == 'POST' and form.is_valid():
        sesion = form.save(commit=False)
        sesion.tecnico = perfil
        sesion.registrada_por = propio if a_nombre_de else None
        sesion.save()
        quien = f" de {perfil.nombre_completo}" if a_nombre_de else ""
        messages.success(request, f"Sesión{quien} abierta. Ya se pueden terminar probetas con fecha "
                                  f"{sesion.fecha:%d/%m/%Y}.")
        return redirect(volver)
    faltan_tipos = [
        etiqueta for campo, tipo in SesionEnsayo.EQUIPOS + SesionEnsayo.ACCESORIOS
        for codigo, etiqueta in Equipo.TIPOS
        if codigo == tipo and not form.fields[campo].queryset.exists()
    ]
    return render(request, 'proyectos/compresion_sesion.html', {
        'form': form,
        'faltan_tipos': faltan_tipos,
        'campos_equipo': [form[c] for c, _ in SesionEnsayo.EQUIPOS + SesionEnsayo.ACCESORIOS]
                         + [form['neopreno_usos']],
        'campos_comprobacion': form.campos_comprobacion(),
        'a_nombre_de': a_nombre_de,
        'volver': volver,
    })


@login_required
@require_POST
@permiso_requerido(PERMISO_REGISTRAR)
def cerrar_sesion_ensayo(request):
    perfil = _perfil_elegido(request, request.POST.get('tecnico'))
    volver = _volver(request, reverse('proyectos:mis_ensayos_compresion'))
    sesion = SesionEnsayo.abierta_de(perfil)
    if sesion is None:
        messages.error(request, "No hay ninguna sesión abierta.")
        return redirect(volver)
    form = CerrarSesionForm(request.POST, instance=sesion)
    if not form.is_valid():
        errores = [e for lista in form.errors.values() for e in lista]
        messages.error(request, "Para cerrar la sesión: " + " ".join(errores))
        return redirect(volver)
    sesion = form.save(commit=False)
    sesion.cerrada_en = timezone.now()
    sesion.save()
    n = sesion.ensayos.count()
    messages.success(request, f"Sesión cerrada con {n} probeta{'s' if n != 1 else ''} terminada{'s' if n != 1 else ''}.")
    return redirect(volver)


# --- Datos FOR-004 de las probetas, en recepción (HU-LIMS-11) -------------

@login_required
@permiso_requerido(PERMISO_DATOS_PROBETA)
def datos_probetas_recepcion(request, recepcion_id):
    recepcion = get_object_or_404(RecepcionMuestra.objects.select_related('cotizacion'), pk=recepcion_id)
    muestras = list(
        MuestraDetalle.objects.filter(recepcion=recepcion).select_related('tipo_muestra').order_by('nro_item', 'pk')
    )
    # Probetas de compresión primero; el resto (suelos, etc.) también se puede llenar.
    ids_compresion = set(
        DetalleSolicitudEnsayo.objects.filter(FILTRO_COMPRESION, muestra__recepcion=recepcion)
        .values_list('muestra_id', flat=True)
    )

    def formulario(m):
        inicial = {}
        if m.fecha_fabricacion is None and recepcion.fecha_fabricacion:
            inicial['fecha_fabricacion'] = recepcion.fecha_fabricacion
        return DatosProbetaForm(request.POST or None, instance=m, prefix=f'm{m.pk}', initial=inicial)

    filas = [{'muestra': m, 'form': formulario(m), 'compresion': m.pk in ids_compresion} for m in muestras]
    ubicacion = (request.POST.get('ubicacion_proyecto') if request.method == 'POST' else recepcion.ubicacion_proyecto) or ''

    if request.method == 'POST':
        if all(f['form'].is_valid() for f in filas):
            with transaction.atomic():
                recepcion.ubicacion_proyecto = ubicacion.strip()[:255]
                recepcion.save(update_fields=['ubicacion_proyecto'])
                for f in filas:
                    f['form'].save()
            messages.success(request, "Datos de las probetas guardados.")
            return redirect('proyectos:datos_probetas', recepcion_id=recepcion.pk)
        messages.error(request, "Revisa los datos marcados en rojo.")

    return render(request, 'proyectos/compresion_datos_probetas.html', {
        'recepcion': recepcion,
        'filas': sorted(filas, key=lambda f: not f['compresion']),
        'ubicacion': ubicacion,
        'hay_agrupadas': any(f['muestra'].cantidad > 1 for f in filas if f['compresion']),
    })


# --- Equipos (HU-LIMS-12) ---------------------------------------------------

@login_required
@permiso_requerido(PERMISO_EQUIPOS_VER)
def lista_equipos(request):
    hoy = timezone.localdate()
    equipos = list(Equipo.objects.all())
    for e in equipos:
        e.esta_vencido = e.vencido(hoy)
        e.vence_pronto = bool(
            e.vence_calibracion and not e.esta_vencido and (e.vence_calibracion - hoy).days <= 30
        )
    return render(request, 'proyectos/equipos_lista.html', {
        'equipos': equipos,
        'puede_editar': trabajador_tiene_permiso(request.user, PERMISO_EQUIPOS_EDITAR),
    })


@login_required
@permiso_requerido(PERMISO_EQUIPOS_EDITAR)
def editar_equipo(request, equipo_id=None):
    equipo = get_object_or_404(Equipo, pk=equipo_id) if equipo_id else None
    form = EquipoForm(request.POST or None, instance=equipo)
    if request.method == 'POST' and form.is_valid():
        equipo = form.save()
        messages.success(request, f"Equipo {equipo.codigo} guardado.")
        return redirect('proyectos:lista_equipos')
    return render(request, 'proyectos/equipos_form.html', {'form': form, 'equipo': equipo})


def redirigir_compresion(request, resto):
    """/proyectos/compresion/… → /proyectos/resultados/… (enlaces guardados)."""
    destino = request.path.replace('/compresion/', '/resultados/', 1)
    if request.META.get('QUERY_STRING'):
        destino += '?' + request.META['QUERY_STRING']
    return redirect(destino, permanent=True)


# ---------------------------------------------------------------------------
# Programa de ensayos del día (HU-LIMS-21): una hoja por cliente y por día.
# ---------------------------------------------------------------------------

def _hoja_cliente(request, fecha, cliente_id):
    """Las líneas de un cliente en el programa de `fecha` (incluye atrasadas si es hoy)."""
    hoy = timezone.localdate()
    del_dia, atrasadas, _ = programa.lineas_del_dia(request.user, fecha, hoy)
    lineas = [d for d in atrasadas + del_dia if d.solicitud.cotizacion.cliente_id == cliente_id]
    lineas.sort(key=lambda d: (not d.atrasada, d.muestra.codigo_laboratorio or '', d.pk))
    return lineas


@login_required
@permiso_requerido('ensayos.ver')
def programa_dia(request):
    """Programa del día: por cliente, las probetas que tocan romper (REQ-LIMS-62 a 65)."""
    hoy = timezone.localdate()
    fecha = programa.leer_fecha(request.GET.get('fecha'), hoy)
    ve_todos = ve_todos_los_ensayos(request.user)
    del_dia, atrasadas, sin_fecha = programa.lineas_del_dia(request.user, fecha, hoy)
    grupos = programa.agrupar_por_cliente(atrasadas + del_dia, ve_nombre=ve_todos)
    for g in grupos:
        g['url'] = reverse('proyectos:programa_cliente', args=[fecha.isoformat(), g['cliente_id']])
    total = sum(g['total'] for g in grupos)
    rotas = sum(g['rotas'] for g in grupos)
    return render(request, 'proyectos/programa_dia.html', {
        'fecha': fecha,
        'hoy': hoy,
        'es_hoy': fecha == hoy,
        'anterior': (fecha - timedelta(days=1)).isoformat(),
        'siguiente': (fecha + timedelta(days=1)).isoformat(),
        'grupos': grupos,
        'total': total,
        'rotas': rotas,
        'atrasadas': len(atrasadas),
        'sin_fecha': sin_fecha[:50],
        'sin_fecha_total': len(sin_fecha),
        've_todos': ve_todos,
    })


@login_required
@permiso_requerido('ensayos.ver')
def programa_cliente(request, fecha, cliente_id):
    """La «solicitud del día» de un cliente: lista para imprimir y para trabajar (REQ-LIMS-66 a 70)."""
    fecha = programa.leer_fecha(fecha, None)
    if fecha is None:
        raise Http404("Fecha no válida.")
    lineas = _hoja_cliente(request, fecha, cliente_id)
    if not lineas:
        messages.info(request, "Ese cliente no tiene probetas tuyas en el programa de ese día.")
        return redirect(f"{reverse('proyectos:programa_dia')}?fecha={fecha.isoformat()}")

    ve_todos = ve_todos_los_ensayos(request.user)
    grupo = programa.agrupar_por_cliente(lineas, ve_nombre=ve_todos)[0]
    volver = reverse('proyectos:programa_cliente', args=[fecha.isoformat(), cliente_id])
    puede_registrar = trabajador_tiene_permiso(request.user, PERMISO_REGISTRAR)
    propio = _perfil(request.user)
    tecnicos = {}
    for d in lineas:
        d.url_registro = (reverse('proyectos:registrar_compresion', args=[d.pk]) + '?' +
                          urlencode({'desde': 'programa', 'fecha': fecha.isoformat(), 'cliente': cliente_id}))
        if d.estado != programa.ESTADO_TERMINADA:
            ejecutor = _ejecutor(request.user, d)
            if ejecutor is not None:
                tecnicos[ejecutor.pk] = ejecutor
    sesiones = []
    for t in tecnicos.values():
        abierta = SesionEnsayo.abierta_de(t)
        ajeno = t != propio
        sesiones.append({
            'tecnico': t,
            'ajeno': ajeno,
            'sesion': abierta,
            'url_abrir': _url_abrir_sesion(t if ajeno else None, volver),
            'form_cerrar': CerrarSesionForm(instance=abierta) if abierta else None,
        })
    pendientes = [d for d in lineas if d.estado != programa.ESTADO_TERMINADA]
    informes = dict(InformeFinal.objects.filter(solicitud__in=grupo['solicitudes'])
                    .values_list('solicitud_id', 'codigo_informe'))
    for s in grupo['solicitudes']:
        s.informe_codigo = informes.get(s.pk)
    return render(request, 'proyectos/programa_cliente.html', {
        'fecha': fecha,
        'hoy': timezone.localdate(),
        'grupo': grupo,
        'lineas': lineas,
        'pendientes': len(pendientes),
        'por_medir': sum(1 for d in lineas if d.estado == programa.ESTADO_POR_MEDIR),
        've_todos': ve_todos,
        'puede_registrar': puede_registrar,
        'puede_aprobar': trabajador_tiene_permiso(request.user, 'informes.aprobar'),
        'sesiones': sesiones,
        'volver': volver,
        'url_programa': f"{reverse('proyectos:programa_dia')}?fecha={fecha.isoformat()}",
    })


@login_required
@permiso_requerido(PERMISO_REGISTRAR)
def programa_medidas(request, fecha, cliente_id):
    """«Medir y pesar todas primero» sobre la hoja del día, aunque vengan de varias solicitudes."""
    fecha_programa = programa.leer_fecha(fecha, None)
    if fecha_programa is None:
        raise Http404("Fecha no válida.")
    pantalla = reverse('proyectos:programa_cliente', args=[fecha_programa.isoformat(), cliente_id])
    lineas = [d for d in _hoja_cliente(request, fecha_programa, cliente_id)
              if d.estado != programa.ESTADO_TERMINADA]
    if not lineas:
        messages.error(request, "No quedan probetas por medir en esta hoja.")
        return redirect(pantalla)
    hoy = timezone.localdate()
    return _medidas_en_lote(request, lineas, pantalla, f'Programa del {fecha_programa:%d/%m/%Y}',
                            fecha_inicial=min(fecha_programa, hoy))
