"""Redactar, responder, reenviar, adjuntos, cotizaciones del LIMS y envío.

El envío real es el Paso 5: aquí el mensaje pasa a la Bandeja de salida y la
tarea Celery `enviar_mensaje` usa ServicioEnvioSimulado.
"""
import html as html_lib
import re
import uuid

from django.conf import settings
from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.core.validators import validate_email
from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Q, Sum
from django.http import Http404, JsonResponse
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils import timezone, formats
from django.views.decorators.http import require_POST

from servicios.models import Cotizacion
from trabajadores.permissions import trabajador_tiene_permiso

from .cuentas import ADMINISTRA, GESTIONA, cuentas_de, exigir_cuenta, exigir_mensaje, permite, roles_de
from .enlaces import adjunto_de_token, url_adjunto
from .mensajeria import (
    agregar_adjunto, actualizar_tiene_adjuntos, carpeta, crear_mensaje, direcciones, normalizar_asunto,
    nuevo_message_id, preparar_cuerpo, registrar_evento,
)
from .busqueda import indexar
from .directorio import sugerir
from .models import Adjunto, AccesoCuenta, CuentaCorreo, EventoMensaje, Firma, Mensaje
from .sanitizar import reemplazar_cid, sanitizar_html
from .tasks import adjuntar_cotizacion, enviar_mensaje
from .views_correo import contexto_bandeja_cuenta, correo_requerido

MAX_BYTES = settings.CORREO_MAX_ADJUNTOS_BYTES


def cuentas_para_enviar(user):
    roles = roles_de(user)
    return [c for c in cuentas_de(user) if permite(roles.get(c.pk), GESTIONA)]


def firmas_de(user, cuentas):
    return Firma.objects.filter(Q(usuario=user) | Q(cuenta__in=cuentas)).select_related('cuenta').order_by('cuenta_id', 'nombre')


def firma_por_defecto(user, cuenta, respuesta):
    """Firma de la cuenta (compartida) si tiene; si no, la personal predeterminada."""
    if cuenta.firma_predeterminada_id:
        return cuenta.firma_predeterminada.html
    campo = 'para_respuestas' if respuesta else 'para_nuevos'
    firma = Firma.objects.filter(usuario=user, **{campo: True}).first()
    return firma.html if firma else ''


PARTE = re.compile(r'(?:"[^"]*"|<[^>]*>|[^,;"<])+')


def _fmt(personas):
    """«Nombre <correo>, …»; el nombre va entre comillas si trae comas u otros separadores."""
    def una(p):
        nombre = (p.get('nombre') or '').replace('"', '').strip()
        if not nombre:
            return p['correo']
        if any(c in nombre for c in ',;<>@'):
            nombre = f'"{nombre}"'
        return f'{nombre} <{p["correo"]}>'
    return ', '.join(una(p) for p in personas)


def _original(borrador):
    """Mensaje citado (respuesta o reenvío) a partir de In-Reply-To/References."""
    ultimo_id = (borrador.in_reply_to or '').strip() or ((borrador.references or '').split() or [''])[-1]
    if not ultimo_id:
        return None
    return Mensaje.objects.filter(cuenta=borrador.cuenta, message_id=ultimo_id).exclude(pk=borrador.pk).first()


def _cita_html(borrador, original):
    if original is None:
        return ''
    fecha = formats.date_format(timezone.localtime(original.fecha), 'DATETIME_FORMAT')
    de = html_lib.escape(f'{original.de_nombre} <{original.de}>' if original.de_nombre else original.de)
    if borrador.in_reply_to:
        encabezado = f'<p>El {fecha}, {de} escribió:</p>'
    else:
        encabezado = (
            '<p>---------- Mensaje reenviado ----------<br>'
            f'<b>De:</b> {de}<br><b>Fecha:</b> {fecha}<br>'
            f'<b>Asunto:</b> {html_lib.escape(original.asunto)}<br>'
            f'<b>Para:</b> {html_lib.escape(_fmt(original.para))}</p>'
        )
    return f'{encabezado}<blockquote style="margin:0 0 0 8px;padding-left:12px;border-left:3px solid #E5E8EE">' \
           f'{original.cuerpo_html}</blockquote>'


# ------------------------------------------------------------- crear borrador

@correo_requerido
def redactar(request):
    """Crea el borrador (nuevo, respuesta, responder a todos o reenvío) y abre el editor."""
    g = request.GET
    original = None
    modo = 'nuevo'
    for clave in ('responder', 'responder_todos', 'reenviar'):
        if (g.get(clave) or '').isdigit():
            original = exigir_mensaje(request.user, int(g[clave]), GESTIONA)
            modo = clave
            break

    if original is not None:
        cuenta = original.cuenta
    else:
        disponibles = cuentas_para_enviar(request.user)
        cuenta = next((c for c in disponibles if c.slug == g.get('cuenta')), disponibles[0] if disponibles else None)
        if cuenta is None:
            raise PermissionDenied('No gestionas ninguna cuenta de correo.')
        cuenta = exigir_cuenta(request.user, cuenta.slug, GESTIONA)

    propias = set(CuentaCorreo.objects.values_list('direccion', flat=True))
    para, cc, asunto, in_reply_to, references, adjuntos = [], [], '', '', '', []
    if modo in ('responder', 'responder_todos'):
        para = [{'nombre': original.de_nombre, 'correo': original.de}] if original.de not in propias else list(original.para)
        if modo == 'responder_todos':
            ya = {p['correo'] for p in para}
            para += [p for p in original.para if p['correo'] not in propias and p['correo'] not in ya]
            cc = [p for p in original.cc if p['correo'] not in propias]
        asunto = f'RE: {normalizar_asunto(original.asunto)}'
        in_reply_to = original.message_id
        references = f'{original.references} {original.message_id}'.strip()
    elif modo == 'reenviar':
        asunto = f'RV: {normalizar_asunto(original.asunto)}'
        references = f'{original.references} {original.message_id}'.strip()
        adjuntos = list(original.adjuntos.all())
    elif g.get('para'):
        para = direcciones(g['para'])

    firma = firma_por_defecto(request.user, cuenta, respuesta=modo != 'nuevo')
    with transaction.atomic():
        borrador = crear_mensaje(
            cuenta, 'borradores', de=cuenta.direccion, de_nombre=cuenta.nombre, para=para, cc=cc, asunto=asunto,
            html='<p><br></p>' + firma, in_reply_to=in_reply_to, references=references, leido=True,
            estado=Mensaje.BORRADOR, creado_por=request.user, hilo=original.hilo if original else None,
            message_id=nuevo_message_id(cuenta),
        )
        for a in adjuntos:  # el reenvío conserva los adjuntos (mismo archivo, sin copiarlo)
            Adjunto.objects.create(
                mensaje=borrador, nombre=a.nombre, tipo_mime=a.tipo_mime, tamano=a.tamano, archivo=a.archivo.name,
                sha256=a.sha256, content_id=a.content_id, incrustado=a.incrustado,
            )
        if adjuntos:
            actualizar_tiene_adjuntos(borrador)
    return redirect('borrador', borrador.pk)


def _exigir_borrador(user, pk):
    borrador = exigir_mensaje(user, pk, GESTIONA)
    if borrador.estado_envio != Mensaje.BORRADOR:
        raise Http404('Ese mensaje ya no es un borrador.')
    if borrador.creado_por_id not in (None, user.pk) and not permite(roles_de(user).get(borrador.cuenta_id), ADMINISTRA):
        raise PermissionDenied('Este borrador es de otra persona.')
    return borrador


def _adjuntos_json(borrador):
    lista = [
        {'id': a.pk, 'nombre': a.nombre, 'tamano': a.tamano, 'url': url_adjunto(a)}
        for a in borrador.adjuntos.filter(incrustado=False)
    ]
    total = borrador.adjuntos.aggregate(t=Sum('tamano'))['t'] or 0
    return {'adjuntos': lista, 'total': total, 'maximo': MAX_BYTES}


def _html_para_editor(borrador):
    """cid: -> enlaces firmados, para que el editor muestre las imágenes."""
    por_cid = {a.content_id: a for a in borrador.adjuntos.exclude(content_id='')}
    return reemplazar_cid(borrador.cuerpo_html, lambda cid: url_adjunto(por_cid[cid]) if cid in por_cid else None)


_URL_ADJ = re.compile(r'src="[^"]*/a/([^"/]+)/"')


def _html_desde_editor(borrador, html):
    """Enlaces firmados de imágenes propias -> cid: (los enlaces vencen)."""
    propios = {a.pk: a for a in borrador.adjuntos.filter(incrustado=True)}

    def cambiar(m):
        pk = adjunto_de_token(m.group(1))
        if pk in propios:
            return f'src="cid:{propios[pk].content_id}"'
        return m.group(0)
    return _URL_ADJ.sub(cambiar, sanitizar_html(html))


@correo_requerido
def borrador(request, pk):
    b = _exigir_borrador(request.user, pk)
    disponibles = cuentas_para_enviar(request.user)
    original = _original(b)
    puede_cotizar = trabajador_tiene_permiso(request.user, 'cotizaciones.ver')
    # Como en Outlook: la lista de la cuenta a la izquierda y el correo nuevo en el
    # panel de lectura. ?completo=1 lo abre a pantalla completa.
    contexto = contexto_bandeja_cuenta(request, b.cuenta)
    contexto.update({
        'b': b,
        'cuentas_envio': disponibles,
        'cuenta_actual': b.cuenta,
        'para': _fmt(b.para), 'cc': _fmt(b.cc), 'cco': _fmt(b.cco),
        'cuerpo_editor': _html_para_editor(b),
        'original': original,
        'modo': 'responder' if b.in_reply_to else ('reenviar' if b.references else 'nuevo'),
        'firmas': firmas_de(request.user, disponibles),
        'adjuntos': _adjuntos_json(b),
        'puede_cotizar': puede_cotizar,
        'completo': request.GET.get('completo') == '1',
        'redactando': True,
    })
    return render(request, 'correo/redactar.html', contexto)


def _guardar_campos(request, b):
    """Aplica lo que mandó el formulario al borrador. Devuelve lista de errores."""
    p = request.POST
    errores = []
    cuenta_id = p.get('cuenta')
    if cuenta_id and str(cuenta_id).isdigit() and int(cuenta_id) != b.cuenta_id:
        nueva = exigir_cuenta(request.user, pk=int(cuenta_id), rol=GESTIONA)
        if b.in_reply_to or b.references:
            errores.append('Una respuesta o reenvío sale de la misma cuenta del correo original.')
        else:
            b.cuenta = nueva
            b.carpeta = carpeta(nueva, 'borradores')
            b.de, b.de_nombre = nueva.direccion, nueva.nombre
    for campo in ('para', 'cc', 'cco'):
        if campo in p:
            # Separa por coma o punto y coma, salvo dentro de "comillas" o <correo>.
            sueltos = [t.strip() for t in PARTE.findall(p.get(campo, '')) if t.strip()]
            lista = direcciones(', '.join(sueltos))
            for t in sueltos:
                correo = (re.search(r'<([^>]+)>', t) or [None, t])[1].strip()
                try:
                    validate_email(correo)
                except ValidationError:
                    errores.append(f'«{t}» no es un correo válido.')
            setattr(b, campo, lista)
    if 'asunto' in p:
        b.asunto = p.get('asunto', '')[:500]
    if 'cuerpo_html' in p:
        limpio = _html_desde_editor(b, p.get('cuerpo_html', ''))
        b.cuerpo_html, b.cuerpo_texto, b.vista_previa = preparar_cuerpo(html=limpio)
        b.cuerpo_html = limpio
    b.fecha = timezone.now()
    b.save()
    indexar(b)
    return errores


@require_POST
@correo_requerido
def guardar(request, pk):
    b = _exigir_borrador(request.user, pk)
    errores = _guardar_campos(request, b)
    hora = formats.time_format(timezone.localtime(b.fecha), 'H:i')
    if request.headers.get('x-requested-with') == 'fetch':
        return JsonResponse({'ok': True, 'guardado': hora, 'avisos': errores})
    messages.success(request, f'Borrador guardado a las {hora}.')
    return redirect('borrador', b.pk)


@require_POST
@correo_requerido
def enviar(request, pk):
    b = _exigir_borrador(request.user, pk)
    errores = _guardar_campos(request, b)
    if not (b.para or b.cc or b.cco):
        errores.append('Agrega al menos un destinatario.')
    total = b.adjuntos.aggregate(t=Sum('tamano'))['t'] or 0
    if total > MAX_BYTES:
        errores.append('Los adjuntos superan los 25 MB.')
    if errores:
        for e in errores:
            messages.error(request, e)
        return redirect('borrador', b.pk)

    original = _original(b)
    with transaction.atomic():
        b.cuerpo_html = b.cuerpo_html + _cita_html(b, original)
        _, b.cuerpo_texto, b.vista_previa = preparar_cuerpo(html=b.cuerpo_html)
        b.estado_envio = Mensaje.EN_COLA
        b.carpeta = carpeta(b.cuenta, 'salida')
        b.fecha = timezone.now()
        b.save()
        indexar(b)
        tipo = EventoMensaje.RESPONDIO if b.in_reply_to else (EventoMensaje.REENVIO if b.references else EventoMensaje.ENVIO)
        registrar_evento(b.hilo, tipo, request.user, b, para=[d['correo'] for d in b.para])
        type(b.hilo).objects.filter(pk=b.hilo_id).update(ultimo_mensaje_en=b.fecha)
        if not b.hilo.asunto:
            type(b.hilo).objects.filter(pk=b.hilo_id).update(asunto=normalizar_asunto(b.asunto))
        transaction.on_commit(lambda: enviar_mensaje.delay(b.pk))
    messages.success(request, 'Mensaje en la Bandeja de salida. Se enviará en unos segundos.')
    return redirect('bandeja_cuenta', b.cuenta.slug)


@require_POST
@correo_requerido
def descartar(request, pk):
    b = _exigir_borrador(request.user, pk)
    cuenta = b.cuenta
    b.delete()
    messages.success(request, 'Borrador descartado.')
    return redirect('bandeja_cuenta', cuenta.slug)


@require_POST
@correo_requerido
def reintentar(request, pk):
    m = exigir_mensaje(request.user, pk, GESTIONA)
    if m.estado_envio != Mensaje.FALLIDO:
        messages.info(request, 'Ese mensaje no está pendiente de reintento.')
    else:
        Mensaje.objects.filter(pk=m.pk).update(estado_envio=Mensaje.EN_COLA, ultimo_error='')
        transaction.on_commit(lambda: enviar_mensaje.delay(m.pk))
        messages.success(request, 'Reintentando el envío.')
    return redirect('carpeta', m.cuenta.slug, m.carpeta_id)


# ------------------------------------------------------------------ adjuntos

@correo_requerido
def adjuntos(request, pk):
    b = _exigir_borrador(request.user, pk)
    if request.method == 'GET':
        return JsonResponse(_adjuntos_json(b))
    archivo = request.FILES.get('archivo')
    if archivo is None:
        return JsonResponse({'error': 'No llegó ningún archivo.'}, status=400)
    total = b.adjuntos.aggregate(t=Sum('tamano'))['t'] or 0
    if total + archivo.size > MAX_BYTES:
        return JsonResponse({'error': 'Supera el límite de 25 MB por correo.'}, status=400)
    incrustado = request.POST.get('incrustado') == '1'
    if incrustado and not (archivo.content_type or '').startswith('image/'):
        return JsonResponse({'error': 'Solo se pueden insertar imágenes.'}, status=400)
    adj = agregar_adjunto(
        b, archivo.name, archivo.content_type, archivo.read(),
        content_id=f'{uuid.uuid4().hex}@vicaf' if incrustado else '', incrustado=incrustado,
    )
    datos = _adjuntos_json(b)
    datos.update({'id': adj.pk, 'url': url_adjunto(adj)})
    return JsonResponse(datos)


@require_POST
@correo_requerido
def adjunto_quitar(request, pk, adjunto_id):
    b = _exigir_borrador(request.user, pk)
    b.adjuntos.filter(pk=adjunto_id).delete()
    actualizar_tiene_adjuntos(b)
    return JsonResponse(_adjuntos_json(b))


@require_POST
@correo_requerido
def adjuntar_cotizacion_vista(request, pk):
    b = _exigir_borrador(request.user, pk)
    if not trabajador_tiene_permiso(request.user, 'cotizaciones.ver'):
        raise PermissionDenied
    cot_id = request.POST.get('cotizacion', '')
    if not cot_id.isdigit() or not Cotizacion.objects.filter(pk=cot_id, es_plantilla=False).exists():
        return JsonResponse({'error': 'Cotización no encontrada.'}, status=400)
    transaction.on_commit(lambda: adjuntar_cotizacion.delay(b.pk, int(cot_id), request.user.pk))
    return JsonResponse({'ok': True, 'pendiente': True})


# ---------------------------------------------------------------------- APIs

@correo_requerido
def api_contactos(request):
    """Autocompletado de Para/CC/CCO (ver correo/directorio.py). Sin `q`: recientes."""
    excluir = (request.GET.get('excluir') or '').split(',')
    return JsonResponse({'resultados': sugerir(request.user, request.GET.get('q', '')[:100], excluir=excluir[:100])})


@correo_requerido
def api_cotizaciones(request):
    if not trabajador_tiene_permiso(request.user, 'cotizaciones.ver'):
        raise PermissionDenied
    q = (request.GET.get('q') or '').strip()
    cotizaciones = Cotizacion.objects.filter(es_plantilla=False).select_related('cliente')
    if q:
        cotizaciones = cotizaciones.filter(
            Q(numero_oferta__icontains=q) | Q(cliente__razon_social__icontains=q) | Q(asunto_servicio__icontains=q)
        )
    datos = [{
        'id': c.pk, 'numero': c.numero_oferta or f'#{c.pk}', 'cliente': c.cliente.razon_social,
        'asunto': c.asunto_servicio, 'fecha': c.fecha_generacion.strftime('%d/%m/%Y'), 'estado': c.estado,
    } for c in cotizaciones.order_by('-fecha_generacion', '-pk')[:15]]
    return JsonResponse({'resultados': datos})
