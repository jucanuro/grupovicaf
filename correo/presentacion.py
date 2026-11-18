"""Arma el contexto de la vista de tres paneles (carpetas · lista · lectura)."""
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.core.paginator import Paginator
from django.db.models import Count, Max, Q
from django.urls import reverse
from django.utils import timezone

from .cuentas import GESTIONA, cuentas_de, permite, roles_de
from .enlaces import url_adjunto
from .mensajeria import registrar_evento
from .sanitizar import tiene_imagenes_remotas
from .models import AccesoCuenta, Carpeta, EventoMensaje, Hilo, Mensaje

POR_PAGINA = 40


def nombre_usuario(user):
    if user is None:
        return 'Sistema'
    perfil = getattr(user, 'trabajadorprofile', None)
    return getattr(perfil, 'nombre_completo', '') or user.get_full_name() or user.username


def panel_cuentas(user):
    """Cuentas del usuario con sus carpetas y contadores (panel izquierdo)."""
    cuentas = list(cuentas_de(user))
    carpetas = (
        Carpeta.objects.filter(cuenta__in=cuentas)
        .annotate(
            no_leidos=Count('mensajes', filter=Q(mensajes__leido=False)),
            total=Count('mensajes'),
            fallidos=Count('mensajes', filter=Q(mensajes__estado_envio=Mensaje.FALLIDO)),
        )
        .order_by('orden', 'nombre')
    )
    por_cuenta = {}
    for c in carpetas:
        # Qué número mostrar: no leídos, salvo salida/borradores (total).
        c.contador = c.total if c.tipo in ('salida', 'borradores') else c.no_leidos
        por_cuenta.setdefault(c.cuenta_id, []).append(c)
    roles = roles_de(user)
    for cuenta in cuentas:
        cuenta.lista_carpetas = por_cuenta.get(cuenta.pk, [])
        cuenta.rol = roles.get(cuenta.pk)
        cuenta.puede_gestionar = permite(cuenta.rol, GESTIONA)
    return cuentas


def filas_de_hilos(request, filtro, url_base, seleccionado=None):
    """Lista agrupada por conversación: una fila por hilo con su último mensaje.

    `filtro`: dict de lookups sobre Mensaje (p. ej. {'carpeta': carpeta}).
    """
    usuario = request.user
    filtro_mensajes = Q(**{f'mensajes__{k}': v for k, v in filtro.items()})
    hilos = (
        Hilo.objects.filter(cuenta__in=cuentas_de(usuario).values('pk'))
        .annotate(
            ultima=Max('mensajes__fecha', filter=filtro_mensajes),
            n=Count('mensajes', filter=filtro_mensajes, distinct=True),
            sin_leer=Count('mensajes', filter=filtro_mensajes & Q(mensajes__leido=False), distinct=True),
            con_adjuntos=Count('mensajes', filter=filtro_mensajes & Q(mensajes__tiene_adjuntos=True), distinct=True),
        )
        .filter(n__gt=0)
        .select_related('cuenta', 'asignacion__asignado_a__trabajadorprofile')
        .order_by('-ultima')
    )
    pagina = Paginator(hilos, POR_PAGINA).get_page(request.GET.get('p'))
    ids = [h.pk for h in pagina]
    ultimos = {}
    consulta = Mensaje.objects.filter(hilo__in=ids, **filtro)
    for m in consulta.order_by('hilo_id', '-fecha').only(
        'pk', 'hilo_id', 'de', 'de_nombre', 'para', 'asunto', 'vista_previa', 'fecha', 'estado_envio', 'ultimo_error',
    ):
        ultimos.setdefault(m.hilo_id, m)
    filas = []
    for h in pagina:
        m = ultimos.get(h.pk)
        if m is None:
            continue
        filas.append({
            'hilo': h, 'mensaje': m, 'n': h.n, 'no_leido': h.sin_leer > 0, 'adjunto': h.con_adjuntos > 0,
            'asignacion': getattr(h, 'asignacion', None), 'seleccionado': h.pk == seleccionado,
            'url': f'{url_base}{"&" if "?" in url_base else "?"}h={h.pk}' + (f'&p={pagina.number}' if pagina.number > 1 else ''),
            'url_completa': reverse('mensaje', args=[m.pk]),
            'enviado': m.estado_envio != Mensaje.RECIBIDO,
        })
    return filas, pagina


def abrir_hilo(request, hilo, carpeta_actual=None):
    """Mensajes del hilo, participantes, actividad y opciones (panel derecho)."""
    usuario = request.user
    rol = roles_de(usuario).get(hilo.cuenta_id)
    ocultas = {'papelera', 'spam'} - ({carpeta_actual.tipo} if carpeta_actual else set())
    mensajes = list(
        hilo.mensajes.exclude(carpeta__tipo__in=ocultas).exclude(estado_envio=Mensaje.BORRADOR)
        .select_related('carpeta', 'creado_por').prefetch_related('adjuntos').order_by('fecha')
    )
    if not mensajes:
        return None
    no_leidos = [m.pk for m in mensajes if not m.leido]
    if no_leidos:
        Mensaje.objects.filter(pk__in=no_leidos).update(leido=True)
    hace_poco = timezone.now() - timedelta(minutes=30)
    if not hilo.eventos.filter(usuario=usuario, tipo=EventoMensaje.ABRIO, creado_en__gte=hace_poco).exists():
        registrar_evento(hilo, EventoMensaje.ABRIO, usuario, mensajes[-1])

    for m in mensajes:
        m.lista_adjuntos = [
            {'nombre': a.nombre, 'tamano': a.tamano, 'url': url_adjunto(a), 'es_imagen': a.es_imagen}
            for a in m.adjuntos.all() if not a.incrustado
        ]
        m.lista_para = ', '.join(d.get('nombre') or d['correo'] for d in m.para)
        m.lista_cc = ', '.join(d.get('nombre') or d['correo'] for d in m.cc)
        m.imagenes_remotas = tiene_imagenes_remotas(m.cuerpo_html)

    eventos = list(hilo.eventos.select_related('usuario__trabajadorprofile').order_by('-creado_en')[:50])
    intervinientes = {}
    for e in reversed(eventos):
        if e.usuario_id:
            datos = intervinientes.setdefault(e.usuario_id, {'nombre': nombre_usuario(e.usuario), 'acciones': []})
            accion = e.get_tipo_display()
            if accion not in datos['acciones']:
                datos['acciones'].append(accion)
    asignables = get_user_model().objects.filter(
        accesos_correo__cuenta=hilo.cuenta, accesos_correo__rol__in=[AccesoCuenta.GESTIONA, AccesoCuenta.ADMINISTRA],
    ).select_related('trabajadorprofile').order_by('username')
    return {
        'hilo': hilo,
        'mensajes': mensajes,
        'ultimo': mensajes[-1],
        'participantes': hilo.participantes.select_related('cliente').order_by('nombre', 'correo'),
        'intervinientes': list(intervinientes.values()),
        'eventos': [{'quien': nombre_usuario(e.usuario), 'que': e.get_tipo_display(), 'cuando': e.creado_en,
                     'detalle': e.detalle} for e in eventos],
        'asignacion': getattr(hilo, 'asignacion', None),
        'asignables': [(u.pk, nombre_usuario(u)) for u in asignables],
        'carpetas_destino': hilo.cuenta.carpetas.order_by('orden', 'nombre'),
        'puede_gestionar': permite(rol, GESTIONA),
    }
