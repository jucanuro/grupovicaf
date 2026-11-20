"""Registro del ensayo de compresión de probetas desde el celular.

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
from datetime import date
from decimal import Decimal, InvalidOperation

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

from .calculos_compresion import DatosInsuficientes
from .forms_compresion import AbrirSesionForm, CerrarSesionForm, DatosProbetaForm, EquipoForm
from .fotos import FotoInvalida, procesar_foto
from .models import (
    DetalleSolicitudEnsayo, EnsayoCompresion, Equipo, FotoEnsayo, MuestraDetalle,
    RecepcionMuestra, SesionEnsayo,
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
    terminado = Q(ensayo_compresion__estado__in=EnsayoCompresion.ESTADOS_CERRADOS)
    detalles = detalles.filter(terminado) if vista == 'terminados' else detalles.exclude(terminado)

    sesion = SesionEnsayo.abierta_de(_perfil(request.user))
    return render(request, 'proyectos/compresion_lista.html', {
        'detalles': detalles[:200],
        'vista': vista,
        'total_fotos': len(FotoEnsayo.TIPOS),
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

    if request.method == 'POST':
        accion = request.POST.get('accion', 'guardar')
        url = reverse('proyectos:registrar_compresion', args=[detalle.pk])

        if accion == 'reabrir':
            if not ve_todos or ensayo is None:
                return HttpResponseForbidden("Solo el supervisor puede reabrir un ensayo terminado.")
            if ensayo.aprobado:
                messages.error(request, "La probeta ya está aprobada en un informe; no se puede reabrir.")
                return redirect(url)
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
            sesion = SesionEnsayo.abierta_de(_perfil(request.user))
            if sesion is None:
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
            ensayo.sesion = sesion
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
    sesion = SesionEnsayo.abierta_de(_perfil(request.user))
    resultado, error_calculo = None, None
    if ensayo is not None:
        try:
            resultado = ensayo.calcular()
        except DatosInsuficientes as exc:
            error_calculo = str(exc)
    muestra = detalle.muestra
    return render(request, 'proyectos/compresion_registro.html', {
        'detalle': detalle,
        'ensayo': ensayo,
        'muestra': muestra,
        'datos_probeta_completos': bool(muestra.fecha_fabricacion and muestra.fc_diseno),
        'sesion': sesion,
        'sesion_ensayo': ensayo.sesion if ensayo else None,
        'resultado': resultado,
        'error_calculo': error_calculo,
        'medidas': _medidas_para_formulario(ensayo),
        'fracturas': [n for n in range(1, 7)],
        'slots': slots,
        'solo_lectura': bool(ensayo and ensayo.terminado),
        've_todos': ve_todos,
        'fecha_minima': _fecha_minima(detalle),
        'hoy': timezone.localdate(),
        'lado_maximo': FotoEnsayo.LADO_MAXIMO,
    })


def _medidas_para_formulario(ensayo):
    etiquetas = {f.name: f.verbose_name for f in EnsayoCompresion._meta.fields}
    return [
        {
            'campo': campo,
            'etiqueta': etiquetas[campo],
            'valor': '' if ensayo is None or getattr(ensayo, campo) is None else getattr(ensayo, campo),
            'paso': '0.1' if campo == 'masa_g' else '0.01',
        }
        for campo in EnsayoCompresion.CAMPOS_MEDIDOS
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
    etiquetas = {f.name: str(f.verbose_name) for f in EnsayoCompresion._meta.fields}
    medidas = {}
    for campo in EnsayoCompresion.CAMPOS_MEDIDOS:
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

    ensayo.fecha_ensayo = fecha
    for campo, valor in medidas.items():
        setattr(ensayo, campo, valor)
    ensayo.tipo_fractura = fractura
    ensayo.defectos = (request.POST.get('defectos') or '').strip()[:255]
    ensayo.observaciones = (request.POST.get('observaciones') or '').strip()
    ensayo.save(update_fields=[
        'fecha_ensayo', 'observaciones', 'tipo_fractura', 'defectos', 'actualizado_en',
        *EnsayoCompresion.CAMPOS_MEDIDOS,
    ])
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


# --- Sesión de ensayo (HU-LIMS-12/13) -------------------------------------

@login_required
@permiso_requerido(PERMISO_REGISTRAR)
def abrir_sesion_ensayo(request):
    perfil = _perfil(request.user)
    if perfil is None:
        messages.error(request, "Tu usuario no tiene ficha de trabajador; pide que la creen para abrir sesiones.")
        return redirect('proyectos:mis_ensayos_compresion')
    if SesionEnsayo.abierta_de(perfil):
        messages.error(request, "Ya tienes una sesión abierta; ciérrala antes de abrir otra.")
        return redirect('proyectos:mis_ensayos_compresion')

    form = AbrirSesionForm(request.POST or None, initial={'fecha': timezone.localdate()})
    if request.method == 'POST' and form.is_valid():
        sesion = form.save(commit=False)
        sesion.tecnico = perfil
        sesion.save()
        messages.success(request, "Sesión abierta. Ya puedes terminar probetas con fecha "
                                  f"{sesion.fecha:%d/%m/%Y}.")
        return redirect('proyectos:mis_ensayos_compresion')
    faltan_tipos = [
        etiqueta for campo, tipo in SesionEnsayo.EQUIPOS
        for codigo, etiqueta in Equipo.TIPOS
        if codigo == tipo and not form.fields[campo].queryset.exists()
    ]
    return render(request, 'proyectos/compresion_sesion.html', {
        'form': form,
        'faltan_tipos': faltan_tipos,
        'campos_equipo': [form[c] for c, _ in SesionEnsayo.EQUIPOS],
    })


@login_required
@require_POST
@permiso_requerido(PERMISO_REGISTRAR)
def cerrar_sesion_ensayo(request):
    sesion = SesionEnsayo.abierta_de(_perfil(request.user))
    if sesion is None:
        messages.error(request, "No tienes ninguna sesión abierta.")
        return redirect('proyectos:mis_ensayos_compresion')
    form = CerrarSesionForm(request.POST, instance=sesion)
    if not form.is_valid():
        errores = [e for lista in form.errors.values() for e in lista]
        messages.error(request, "Para cerrar la sesión: " + " ".join(errores))
        return redirect('proyectos:mis_ensayos_compresion')
    sesion = form.save(commit=False)
    sesion.cerrada_en = timezone.now()
    sesion.save()
    n = sesion.ensayos.count()
    messages.success(request, f"Sesión cerrada con {n} probeta{'s' if n != 1 else ''} terminada{'s' if n != 1 else ''}.")
    return redirect('proyectos:mis_ensayos_compresion')


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
