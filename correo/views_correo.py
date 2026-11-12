"""Vistas del host del correo (email.<dominio>), URLconf grupovicaf.urls_correo.

Toda consulta pasa por correo.cuentas (acceso validado en el servidor).
"""
import mimetypes

from django.contrib import messages
from django.contrib.auth import get_user_model, login, logout
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.db import IntegrityError, transaction
from django.db.models import Q
from django.http import FileResponse, Http404, HttpResponse, HttpResponseRedirect, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils.dateparse import parse_date
from django.views.decorators.cache import never_cache
from django.views.decorators.clickjacking import xframe_options_sameorigin
from django.views.decorators.http import require_POST

from clientes.models import Cliente
from servicios.models import Cotizacion
from trabajadores.permissions import trabajador_tiene_permiso

from . import busqueda
from .almacen import es_r2, url_prefirmada
from .cuentas import (
    GESTIONA, LECTURA, cuentas_de, exigir_cuenta, exigir_hilo, exigir_mensaje, mensajes_visibles, permite, roles_de,
)
from .enlaces import adjunto_de_token, consumir_enlace, destino_seguro, url_adjunto, url_lab
from .mensajeria import carpeta as carpeta_de, mover, registrar_evento
from .models import Adjunto, Asignacion, Carpeta, Contacto, EventoMensaje, Hilo, Mensaje
from .permisos import puede_usar_correo
from .presentacion import abrir_hilo, filas_de_hilos, panel_cuentas
from .sanitizar import bloquear_imagenes_remotas, reemplazar_cid, tiene_imagenes_remotas

BACKEND = 'django.contrib.auth.backends.ModelBackend'
URLCONF_LAB = 'grupovicaf.urls_lab'


def correo_requerido(vista):
    """login_required + permiso correo.ver (403 con pantalla propia)."""
    @login_required
    def envoltura(request, *args, **kwargs):
        if not puede_usar_correo(request.user):
            return render(request, 'correo/sin_acceso.html', status=403)
        return vista(request, *args, **kwargs)
    envoltura.__name__ = vista.__name__
    envoltura.__doc__ = vista.__doc__
    return envoltura


# ----------------------------------------------------------------- sesión

def ir_al_login(request):
    """LOGIN_URL del host de correo: el login vive en el LIMS."""
    abrir = reverse('correo:abrir', urlconf=URLCONF_LAB)
    return redirect(url_lab(request, abrir, next=destino_seguro(request.GET.get('next', '/'))))


@never_cache
def entrar(request):
    """Consume el enlace firmado y abre la sesión propia del host de correo."""
    datos = consumir_enlace(request.GET.get('t'))
    if datos is None:
        return render(request, 'correo/enlace_invalido.html', {
            'url_lab': url_lab(request, reverse('inicio', urlconf=URLCONF_LAB)),
        }, status=400)
    user = get_user_model().objects.filter(pk=datos['u'], is_active=True).first()
    if user is None or not puede_usar_correo(user):
        return render(request, 'correo/sin_acceso.html', status=403)
    login(request, user, backend=BACKEND)
    return redirect(datos['d'])


@require_POST
def salir(request):
    logout(request)
    return redirect(url_lab(request, reverse('inicio', urlconf=URLCONF_LAB)))


# ---------------------------------------------------------- tres paneles

def contexto_bandeja(request, *, titulo, filtro, url_base, cuenta=None, carpeta=None, extra=None, abrir=True):
    """Contexto de la lista (y del hilo abierto con ?h=). Lo usa también Redactar,
    que muestra la lista a la izquierda y el correo nuevo en el panel de lectura."""
    hilo_id = request.GET.get('h') if abrir else None
    lectura = None
    if hilo_id and hilo_id.isdigit():
        lectura = abrir_hilo(request, exigir_hilo(request.user, int(hilo_id)), carpeta)
    filas, pagina = filas_de_hilos(request, filtro, url_base, seleccionado=lectura and lectura['hilo'].pk)
    if carpeta is not None and carpeta.tipo == 'borradores':
        for fila in filas:
            fila['url'] = reverse('borrador', args=[fila['mensaje'].pk])
    contexto = {
        'cuentas': panel_cuentas(request.user),
        'cuenta_actual': cuenta,
        'carpeta_actual': carpeta,
        'titulo': titulo,
        'filas': filas,
        'pagina': pagina,
        'url_base': url_base,
        'lectura': lectura,
        'url_inicio_lab': url_lab(request, reverse('inicio', urlconf=URLCONF_LAB)),
        'volver': request.get_full_path() if abrir else url_base,
        # «Mover a» de la barra de comandos: carpetas de la cuenta (o del hilo abierto).
        'carpetas_mover': (list(cuenta.carpetas.order_by('orden', 'nombre')) if cuenta is not None
                           else list(lectura['carpetas_destino']) if lectura else []),
    }
    contexto.update(extra or {})
    return contexto


def contexto_bandeja_cuenta(request, cuenta):
    """Lista de la bandeja de entrada de `cuenta`, sin hilo abierto."""
    carpeta = carpeta_de(cuenta, 'entrada')
    return contexto_bandeja(
        request, titulo=carpeta.nombre, filtro={'carpeta': carpeta},
        url_base=reverse('bandeja_cuenta', args=[cuenta.slug]), cuenta=cuenta, carpeta=carpeta, abrir=False,
    )


def _render_bandeja(request, **kwargs):
    return render(request, 'correo/bandeja.html', contexto_bandeja(request, **kwargs))


@correo_requerido
def bandeja(request, cuenta=None):
    """Bandeja de entrada unificada (todas las cuentas) o de una cuenta."""
    if cuenta is not None:
        cuenta_obj = exigir_cuenta(request.user, cuenta)
        return carpeta_vista(request, cuenta, carpeta_de(cuenta_obj, 'entrada').pk)
    filtro = {'carpeta__tipo': 'entrada', 'cuenta__in': cuentas_de(request.user).values('pk')}
    filtro_cuenta = request.GET.get('cuenta')
    if filtro_cuenta:
        filtro['cuenta__slug'] = filtro_cuenta
    return _render_bandeja(
        request, titulo='Bandeja unificada', filtro=filtro,
        url_base=reverse('bandeja') + (f'?cuenta={filtro_cuenta}' if filtro_cuenta else ''),
        extra={'unificada': True, 'filtro_cuenta': filtro_cuenta},
    )


@correo_requerido
def carpeta_vista(request, cuenta, carpeta_id):
    cuenta_obj = exigir_cuenta(request.user, cuenta)
    carpeta = get_object_or_404(Carpeta, pk=carpeta_id, cuenta=cuenta_obj)
    if carpeta.tipo == 'entrada':
        url_base = reverse('bandeja_cuenta', args=[cuenta_obj.slug])
    else:
        url_base = reverse('carpeta', args=[cuenta_obj.slug, carpeta.pk])
    return _render_bandeja(
        request, titulo=carpeta.nombre, filtro={'carpeta': carpeta}, url_base=url_base,
        cuenta=cuenta_obj, carpeta=carpeta,
    )


@correo_requerido
def mensaje_completo(request, pk):
    """Pantalla completa (doble clic en la lista): el hilo del mensaje."""
    mensaje = exigir_mensaje(request.user, pk)
    lectura = abrir_hilo(request, mensaje.hilo, mensaje.carpeta)
    if lectura is None:
        raise Http404
    return render(request, 'correo/mensaje_completo.html', {
        'lectura': lectura, 'cuenta_actual': mensaje.cuenta,
        'volver': reverse('carpeta', args=[mensaje.cuenta.slug, mensaje.carpeta_id]) + f'?h={mensaje.hilo_id}',
    })


def _csp_cuerpo(request, imagenes):
    origen = f'{request.scheme}://{request.get_host()}'
    img = f"{origen} data:" + (' https:' if imagenes else '')
    return '; '.join((
        "default-src 'none'",
        "style-src 'unsafe-inline' https://fonts.googleapis.com",
        'font-src https://fonts.gstatic.com data:',
        f'img-src {img}',
        "frame-ancestors 'self'",
        "base-uri 'none'",
        "form-action 'none'",
        'sandbox allow-same-origin allow-popups allow-popups-to-escape-sandbox',
    ))


@xframe_options_sameorigin
@correo_requerido
def mensaje_cuerpo(request, pk):
    """Cuerpo HTML del mensaje para el iframe sandbox (sin scripts)."""
    mensaje = exigir_mensaje(request.user, pk)
    imagenes = request.GET.get('imagenes') == '1'
    html = _cuerpo_para_mostrar(mensaje, imagenes)
    respuesta = HttpResponse(render_to_string('correo/cuerpo.html', {'html': html}))
    respuesta['Content-Security-Policy'] = _csp_cuerpo(request, imagenes)
    respuesta['Cache-Control'] = 'private, no-store'
    return respuesta


def _cuerpo_para_mostrar(mensaje, imagenes):
    por_cid = {a.content_id.strip('<>'): a for a in mensaje.adjuntos.exclude(content_id='')}
    html = reemplazar_cid(mensaje.cuerpo_html, lambda cid: url_adjunto(por_cid[cid]) if cid in por_cid else None)
    if not imagenes:
        html, _ = bloquear_imagenes_remotas(html)
    return html


@correo_requerido
def imprimir(request, pk):
    mensaje = exigir_mensaje(request.user, pk)
    respuesta = render(request, 'correo/imprimir.html', {
        'm': mensaje, 'html': _cuerpo_para_mostrar(mensaje, imagenes=False),
        'para': ', '.join(d['correo'] for d in mensaje.para), 'cc': ', '.join(d['correo'] for d in mensaje.cc),
        'adjuntos': mensaje.adjuntos.filter(incrustado=False),
    })
    origen = f'{request.scheme}://{request.get_host()}'
    respuesta['Content-Security-Policy'] = (
        "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
        f"font-src https://fonts.gstatic.com; img-src {origen} data:; frame-ancestors 'none'; base-uri 'none'"
    )
    return respuesta


@never_cache
def adjunto(request, token):
    """Descarga con enlace firmado de corta duración (como una URL prefirmada de R2).

    No usa la sesión: el enlace solo se emite tras validar el acceso a la cuenta.
    """
    pk = adjunto_de_token(token)
    if pk is None:
        raise Http404('El enlace venció. Vuelve a abrir el correo.')
    adj = get_object_or_404(Adjunto, pk=pk)
    seguro_en_linea = adj.tipo_mime in ('image/png', 'image/jpeg', 'image/gif', 'image/webp')
    tipo = adj.tipo_mime if seguro_en_linea else (mimetypes.guess_type(adj.nombre)[0] or adj.tipo_mime)
    if es_r2() and not adj.incrustado:
        # R2: el archivo no pasa por el servidor (2 GB de RAM); se redirige a una URL
        # prefirmada de 300 s. Las imágenes del cuerpo (cid:) siguen por aquí porque
        # la CSP del iframe solo admite imágenes del propio origen.
        destino = url_prefirmada(adj.archivo.name, descarga=adj.nombre, tipo=tipo, en_linea=seguro_en_linea)
        respuesta = HttpResponseRedirect(destino)
        respuesta['Cache-Control'] = 'no-store'
        respuesta['Referrer-Policy'] = 'no-referrer'
        return respuesta
    respuesta = FileResponse(
        adj.archivo.open('rb'), as_attachment=not seguro_en_linea, filename=adj.nombre,
        content_type=tipo,
    )
    respuesta['Content-Security-Policy'] = "default-src 'none'; sandbox"
    respuesta['X-Content-Type-Options'] = 'nosniff'
    respuesta['Cache-Control'] = 'private, max-age=300'
    return respuesta


# ---------------------------------------------------------------- acciones

ACCIONES = {'leido', 'no_leido', 'archivar', 'eliminar', 'spam', 'mover', 'no_spam'}


@require_POST
@correo_requerido
def acciones(request):
    """Acciones en bloque sobre hilos (lista) o mensajes (panel de lectura)."""
    accion = request.POST.get('accion', '')
    volver = destino_seguro(request.POST.get('volver', '/'))
    if accion.startswith('mover:'):
        accion, destino_id = 'mover', accion.split(':', 1)[1]
    else:
        destino_id = request.POST.get('destino')
    if accion not in ACCIONES:
        messages.error(request, 'Acción no válida.')
        return redirect(volver)

    visibles = mensajes_visibles(request.user).select_related('cuenta', 'carpeta', 'hilo')
    hilos = [int(x) for x in request.POST.getlist('hilos') if x.isdigit()]
    ids = [int(x) for x in request.POST.getlist('mensajes') if x.isdigit()]
    origen = request.POST.get('origen', '')
    # Barra de comandos: sin casillas marcadas, la acción va sobre el hilo abierto.
    abierto = request.POST.get('hilo_abierto', '')
    if not hilos and not ids and abierto.isdigit():
        hilos = [int(abierto)]
    seleccion = Q(pk__in=ids)
    if hilos:
        filtro_hilos = Q(hilo__in=hilos)
        if origen.isdigit():
            filtro_hilos &= Q(carpeta_id=int(origen))
        elif origen == 'entrada':
            filtro_hilos &= Q(carpeta__tipo='entrada')
        seleccion |= filtro_hilos
    objetivo = list(visibles.filter(seleccion).exclude(estado_envio=Mensaje.BORRADOR))
    if not objetivo:
        messages.info(request, 'No seleccionaste ningún correo.')
        return redirect(volver)

    roles = roles_de(request.user)
    if any(not permite(roles.get(m.cuenta_id), GESTIONA) for m in objetivo):
        raise PermissionDenied('Tu rol en la cuenta es de solo lectura.')

    with transaction.atomic():
        if accion in ('leido', 'no_leido'):
            Mensaje.objects.filter(pk__in=[m.pk for m in objetivo]).update(leido=(accion == 'leido'))
            texto = 'Marcados como leídos.' if accion == 'leido' else 'Marcados como no leídos.'
        elif accion == 'mover':
            destino = Carpeta.objects.filter(pk=destino_id, cuenta__in=cuentas_de(request.user)).first() \
                if str(destino_id).isdigit() else None
            if destino is None or any(m.cuenta_id != destino.cuenta_id for m in objetivo):
                messages.error(request, 'Elige una carpeta de la misma cuenta.')
                return redirect(volver)
            mover(objetivo, destino, request.user)
            texto = f'Movidos a {destino.nombre}.'
        else:
            tipo = {'archivar': 'archivados', 'spam': 'spam', 'no_spam': 'entrada', 'eliminar': 'papelera'}[accion]
            evento = {'archivar': EventoMensaje.ARCHIVO, 'eliminar': EventoMensaje.ELIMINO}.get(accion, EventoMensaje.MOVIO)
            definitivos = [m for m in objetivo if accion == 'eliminar' and m.carpeta.tipo == 'papelera']
            for m in definitivos:
                registrar_evento(m.hilo, EventoMensaje.ELIMINO, request.user, None, definitivo=True, asunto=m.asunto)
                m.delete()
            restantes = [m for m in objetivo if m not in definitivos]
            for cuenta_id in {m.cuenta_id for m in restantes}:
                de_cuenta = [m for m in restantes if m.cuenta_id == cuenta_id]
                mover(de_cuenta, carpeta_de(de_cuenta[0].cuenta, tipo), request.user, evento)
            texto = {
                'archivar': 'Archivados.', 'spam': 'Movidos a Correo no deseado.', 'no_spam': 'Devueltos a la bandeja.',
                'eliminar': 'Eliminados definitivamente.' if definitivos and not restantes else 'Movidos a la Papelera.',
            }[accion]
    messages.success(request, texto)
    # Si el hilo abierto ya no está en esta carpeta, cerrar el panel de lectura. También
    # al marcar como no leído: volver a abrirlo lo marcaría leído otra vez.
    if accion != 'leido' and '?h=' in volver:
        volver = volver.split('?h=')[0]
    return redirect(volver)


@require_POST
@correo_requerido
def asignar(request, pk):
    hilo = exigir_hilo(request.user, pk, GESTIONA)
    volver = destino_seguro(request.POST.get('volver', '/'))
    usuario_id = request.POST.get('usuario')
    if not usuario_id:
        Asignacion.objects.filter(hilo=hilo).delete()
        registrar_evento(hilo, EventoMensaje.ASIGNO, request.user, a='(nadie)')
        messages.success(request, 'Se quitó la asignación.')
        return redirect(volver)
    asignado = get_user_model().objects.filter(
        pk=usuario_id, accesos_correo__cuenta=hilo.cuenta, accesos_correo__rol__in=['gestiona', 'administra'],
    ).first()
    if asignado is None:
        messages.error(request, 'Esa persona no gestiona esta cuenta.')
        return redirect(volver)
    Asignacion.objects.update_or_create(
        hilo=hilo, defaults={'asignado_a': asignado, 'asignado_por': request.user, 'estado': Asignacion.PENDIENTE},
    )
    registrar_evento(hilo, EventoMensaje.ASIGNO, request.user, a=asignado.username)
    messages.success(request, 'Conversación asignada.')
    return redirect(volver)


@require_POST
@correo_requerido
def atendido(request, pk):
    hilo = exigir_hilo(request.user, pk, GESTIONA)
    volver = destino_seguro(request.POST.get('volver', '/'))
    asignacion, _ = Asignacion.objects.get_or_create(
        hilo=hilo, defaults={'asignado_a': request.user, 'asignado_por': request.user},
    )
    asignacion.estado = Asignacion.PENDIENTE if asignacion.estado == Asignacion.ATENDIDO else Asignacion.ATENDIDO
    asignacion.save(update_fields=['estado', 'actualizado_en'])
    if asignacion.estado == Asignacion.ATENDIDO:
        registrar_evento(hilo, EventoMensaje.ATENDIO, request.user)
    messages.success(request, 'Marcada como atendida.' if asignacion.estado == 'atendido' else 'Marcada como pendiente.')
    return redirect(volver)


@require_POST
@correo_requerido
def carpeta_nueva(request, cuenta):
    cuenta_obj = exigir_cuenta(request.user, cuenta, GESTIONA)
    nombre = (request.POST.get('nombre') or '').strip()[:80]
    if not nombre:
        messages.error(request, 'Escribe un nombre para la carpeta.')
    else:
        try:
            with transaction.atomic():
                nueva = Carpeta.objects.create(cuenta=cuenta_obj, tipo=Carpeta.PERSONAL, nombre=nombre, orden=200)
            messages.success(request, f'Carpeta «{nombre}» creada.')
            return redirect('carpeta', cuenta_obj.slug, nueva.pk)
        except IntegrityError:
            messages.error(request, 'Ya existe una carpeta con ese nombre.')
    return redirect('bandeja_cuenta', cuenta_obj.slug)


@require_POST
@correo_requerido
def carpeta_eliminar(request, cuenta, carpeta_id):
    cuenta_obj = exigir_cuenta(request.user, cuenta, GESTIONA)
    carpeta = get_object_or_404(Carpeta, pk=carpeta_id, cuenta=cuenta_obj, tipo=Carpeta.PERSONAL)
    mensajes = list(carpeta.mensajes.select_related('hilo', 'cuenta'))
    if mensajes:
        mover(mensajes, carpeta_de(cuenta_obj, 'entrada'), request.user)
    carpeta.delete()
    messages.success(request, f'Carpeta «{carpeta.nombre}» eliminada; sus correos volvieron a la bandeja.')
    return redirect('bandeja_cuenta', cuenta_obj.slug)


# ------------------------------------------------------ búsqueda y contacto

@correo_requerido
def buscar(request):
    g = request.GET
    resultados = mensajes_visibles(request.user).exclude(estado_envio=Mensaje.BORRADOR) \
        .select_related('cuenta', 'carpeta', 'hilo')
    if g.get('cuenta'):
        resultados = resultados.filter(cuenta__slug=g['cuenta'])
    if g.get('carpeta'):
        resultados = resultados.filter(carpeta__tipo=g['carpeta'])
    else:
        resultados = resultados.exclude(carpeta__tipo__in=['papelera', 'spam'])
    if g.get('de'):
        resultados = resultados.filter(Q(de__icontains=g['de']) | Q(de_nombre__icontains=g['de']))
    if g.get('para'):
        resultados = busqueda.filtrar_direccion(resultados, 'para', g['para'])
    if parse_date(g.get('desde') or ''):
        resultados = resultados.filter(fecha__date__gte=parse_date(g['desde']))
    if parse_date(g.get('hasta') or ''):
        resultados = resultados.filter(fecha__date__lte=parse_date(g['hasta']))
    if g.get('adjunto') == '1':
        resultados = resultados.filter(tiene_adjuntos=True)
    if (g.get('participante') or '').isdigit():
        resultados = resultados.filter(
            Q(hilo__eventos__usuario_id=int(g['participante'])) | Q(creado_por_id=int(g['participante']))
        ).distinct()
    hay_filtros = any(g.get(k) for k in ('q', 'cuenta', 'carpeta', 'de', 'para', 'desde', 'hasta', 'adjunto', 'participante'))
    resultados = busqueda.buscar(resultados, g.get('q')) if g.get('q') else resultados.order_by('-fecha')
    resultados = list(resultados[:100]) if hay_filtros else []
    for m in resultados:
        m.url = reverse('carpeta', args=[m.cuenta.slug, m.carpeta_id]) + f'?h={m.hilo_id}'
    cuentas_usuario = list(cuentas_de(request.user))
    companeros = get_user_model().objects.filter(
        accesos_correo__cuenta__in=cuentas_usuario,
    ).distinct().select_related('trabajadorprofile').order_by('username')
    from .presentacion import nombre_usuario
    return render(request, 'correo/buscar.html', {
        'cuentas': panel_cuentas(request.user),
        'resultados': resultados, 'hay_filtros': hay_filtros, 'g': g,
        'tipos_carpeta': Carpeta.TIPOS[:-1],
        'companeros': [(u.pk, nombre_usuario(u)) for u in companeros],
        'url_inicio_lab': url_lab(request, reverse('inicio', urlconf=URLCONF_LAB)),
    })


@correo_requerido
def api_buscar(request):
    """Sugerencias de la barra de búsqueda mientras se escribe (como Outlook):
    personas (directorio.sugerir, con su misma regla de privacidad) y los
    correos que coinciden, solo de las cuentas que el usuario puede abrir."""
    from urllib.parse import urlencode

    from .directorio import sugerir
    from .templatetags.correo_tags import fecha_corta
    q = (request.GET.get('q') or '').strip()[:100]
    if len(q) < 2:
        return JsonResponse({'personas': [], 'correos': []})
    personas = [
        {**p, 'url': reverse('contacto') + '?' + urlencode({'correo': p['correo']})}
        for p in sugerir(request.user, q, limite=4)
    ]
    visibles = (mensajes_visibles(request.user).exclude(estado_envio=Mensaje.BORRADOR)
                .exclude(carpeta__tipo__in=['papelera', 'spam']).select_related('cuenta'))
    correos = [{
        'asunto': m.asunto or '(sin asunto)',
        'remitente': m.de_nombre or m.de,
        'cuenta': m.cuenta.nombre or m.cuenta.direccion,
        'fecha': fecha_corta(m.fecha),
        'adjunto': m.tiene_adjuntos,
        'url': reverse('carpeta', args=[m.cuenta.slug, m.carpeta_id]) + f'?h={m.hilo_id}',
    } for m in busqueda.buscar_al_escribir(visibles, q)[:5]]
    return JsonResponse({'personas': personas, 'correos': correos})


@correo_requerido
def contacto(request):
    """Historial por contacto: todos los correos con esa persona o empresa en
    las cuentas del usuario, y su cliente del LIMS si coincide."""
    correo = (request.GET.get('correo') or '').strip().lower()
    if '@' not in correo:
        raise Http404
    dominio = correo.split('@', 1)[1]
    por_empresa = request.GET.get('empresa') == '1'
    visibles = mensajes_visibles(request.user).exclude(estado_envio=Mensaje.BORRADOR).select_related('cuenta', 'carpeta')
    if por_empresa:
        historial = visibles.filter(Q(de__iendswith='@' + dominio) | Q(hilo__participantes__correo__iendswith='@' + dominio))
    else:
        historial = visibles.filter(Q(de=correo) | Q(hilo__participantes__correo=correo))
    historial = list(historial.distinct().order_by('-fecha')[:200])
    for m in historial:
        m.url = reverse('carpeta', args=[m.cuenta.slug, m.carpeta_id]) + f'?h={m.hilo_id}'
    ficha = Contacto.objects.filter(correo=correo).select_related('cliente').first()
    cliente = ficha.cliente if ficha else Cliente.objects.filter(correo_contacto__iexact=correo).first()
    cotizaciones = []
    puede_ver_cotizaciones = trabajador_tiene_permiso(request.user, 'cotizaciones.ver')
    if cliente and puede_ver_cotizaciones:
        cotizaciones = list(
            Cotizacion.objects.filter(cliente=cliente, es_plantilla=False)
            .only('pk', 'numero_oferta', 'fecha_generacion', 'estado', 'asunto_servicio')
            .order_by('-fecha_generacion', '-pk')[:5]
        )
        for c in cotizaciones:
            c.url = url_lab(request, reverse('servicios:ver_pdf_cotizacion', urlconf=URLCONF_LAB, args=[c.pk]))
    por_cuenta = {}
    for m in historial:
        por_cuenta[m.cuenta.nombre] = por_cuenta.get(m.cuenta.nombre, 0) + 1
    return render(request, 'correo/contacto.html', {
        'cuentas': panel_cuentas(request.user),
        'correo': correo, 'dominio': dominio, 'por_empresa': por_empresa, 'ficha': ficha,
        'cliente': {'razon_social': cliente.razon_social} if cliente else None,
        'cotizaciones': cotizaciones, 'puede_ver_cotizaciones': puede_ver_cotizaciones,
        'historial': historial, 'por_cuenta': sorted(por_cuenta.items()),
        'url_inicio_lab': url_lab(request, reverse('inicio', urlconf=URLCONF_LAB)),
    })
