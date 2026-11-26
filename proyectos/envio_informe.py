"""Envío inteligente del informe al cliente (HU-LIMS-47).

El correo es el canal preferido y vive en el propio sistema: en vez de mandar el PDF a ciegas,
se busca en las bandejas del usuario el correo con el que el cliente pidió el servicio y se
prepara una **respuesta** a ese hilo (con el informe adjunto y el enlace de validación):

- Para: el contacto del cliente. Si el correo original lo reenvió otra persona, esa persona
  y el resto de destinatarios del correo van **con copia**.
- Desde: la cuenta de la empresa que recibió el pedido (si es un buzón personal, se avisa y se
  usa una cuenta de la empresa).
- Si no hay un correo de origen, se redacta uno nuevo desde una cuenta de la empresa.

El borrador queda en el módulo de correo para que la persona lo revise y lo envíe; cuando sale,
el informe pasa solo a «enviado» (ver ``correo.tasks.enviar_mensaje``). WhatsApp es el canal
alternativo: abre el chat con el mensaje armado y deja registrado el envío.
"""
from dataclasses import dataclass, field
from urllib.parse import quote

from django.conf import settings
from django.db import transaction
from django.db.models import Q
from django.urls import reverse
from django.utils import timezone


@dataclass
class PlanCorreo:
    """Lo que se hará al abrir el correo: se muestra antes para que la persona lo confirme."""
    modo: str = 'nuevo'                 # 'respuesta' o 'nuevo'
    cuenta: object = None               # CuentaCorreo desde la que se envía
    cuenta_empresa: bool = False        # True si no es un buzón personal
    aviso: str = ''
    origen: object = None               # Mensaje al que se responde
    para: list = field(default_factory=list)
    cc: list = field(default_factory=list)
    asunto: str = ''
    puede: bool = False                 # ¿el usuario puede redactar desde alguna cuenta?
    motivo: str = ''


def _correos_cliente(informe):
    """Direcciones del cliente: la de la cotización, la de su ficha y los contactos del correo ligados a él."""
    from correo.models import Contacto
    cotizacion = informe.solicitud.cotizacion
    cliente = cotizacion.cliente
    vistas, lista = set(), []
    for c in (cotizacion.correo_contacto, cliente.correo_contacto,
              *Contacto.objects.filter(cliente=cliente).values_list('correo', flat=True)):
        c = (c or '').strip().lower()
        if '@' in c and c not in vistas:
            vistas.add(c)
            lista.append(c)
    return lista


def nombre_contacto(informe):
    cotizacion = informe.solicitud.cotizacion
    return (cotizacion.persona_contacto or cotizacion.cliente.persona_contacto or '').strip()


def enlace_validacion(informe):
    return f"{settings.SITE_URL.rstrip('/')}{reverse('proyectos:validar_informe_publico', args=[informe.slug_validacion])}"


def _buscar_origen(user, informe, correos):
    """Correo con el que el cliente pidió el servicio (el mejor candidato en las cuentas del usuario)."""
    from correo.cuentas import cuentas_de
    from correo.models import Mensaje
    cuentas = list(cuentas_de(user))
    if not cuentas:
        return None
    solicitud = informe.solicitud
    cotizacion = solicitud.cotizacion
    del_cliente = Q(de__in=correos) if correos else Q(pk__in=[])
    pistas = [p for p in (solicitud.codigo_solicitud, informe.codigo_informe, cotizacion.numero_oferta,
                          getattr(cotizacion, 'codigo_cotizacion', '')) if p]
    con_pista = Q()
    for p in pistas:
        con_pista |= Q(asunto__icontains=str(p))
    base = Mensaje.objects.filter(cuenta__in=cuentas, estado_envio=Mensaje.RECIBIDO).exclude(carpeta__tipo__in=['spam', 'papelera'])
    # 1) un correo del cliente que menciona la solicitud/cotización; 2) el más reciente del cliente;
    # 3) cualquier correo que mencione la cotización (p. ej. lo reenvió otra persona).
    for filtro in ((del_cliente & con_pista) if pistas else None, del_cliente, con_pista if pistas else None):
        if filtro is None:
            continue
        encontrado = base.filter(filtro).select_related('cuenta', 'hilo').order_by('-fecha').first()
        if encontrado:
            return encontrado
    return None


def planear_correo(user, informe):
    """Qué se hará al enviar por correo (sin crear nada)."""
    from correo.cuentas import GESTIONA, cuentas_de, permite, roles_de
    from correo.mensajeria import normalizar_asunto
    from correo.models import CuentaCorreo
    plan = PlanCorreo()
    roles = roles_de(user)
    gestionables = [c for c in cuentas_de(user) if permite(roles.get(c.pk), GESTIONA)]
    if not gestionables:
        plan.motivo = 'No tienes una cuenta de correo desde la que puedas enviar.'
        return plan
    plan.puede = True
    correos = _correos_cliente(informe)
    propias = set(CuentaCorreo.objects.values_list('direccion', flat=True))
    origen = _buscar_origen(user, informe, correos)
    empresa = [c for c in gestionables if not c.personal]

    if origen is not None and origen.cuenta in gestionables:
        plan.modo, plan.origen = 'respuesta', origen
        plan.cuenta = origen.cuenta
        if origen.cuenta.personal and empresa:
            plan.cuenta = empresa[0]
            plan.aviso = (f"El pedido llegó a un buzón personal ({origen.cuenta.direccion}); se enviará desde la cuenta "
                          f"de la empresa {plan.cuenta.direccion}.")
    else:
        plan.cuenta = (empresa or gestionables)[0]
    plan.cuenta_empresa = not plan.cuenta.personal
    if not plan.cuenta_empresa and not plan.aviso:
        plan.aviso = "Se enviará desde un buzón personal: conviene usar una cuenta de la empresa."

    if plan.modo == 'respuesta':
        o = plan.origen
        remitente = {'nombre': o.de_nombre, 'correo': o.de}
        otros = [p for p in (list(o.para) + list(o.cc)) if p['correo'] not in propias and p['correo'] != o.de]
        if o.de in correos or not correos:
            # Lo escribió el propio cliente: se le responde a él y se copia a los demás del hilo.
            plan.para = [remitente]
            plan.cc = otros
        else:
            # Lo reenvió otra persona: va al contacto del cliente y se copia a quien lo envió y a los demás.
            plan.para = [{'nombre': nombre_contacto(informe), 'correo': correos[0]}]
            plan.cc = [remitente] + otros
        plan.asunto = f"RE: {normalizar_asunto(o.asunto)}"
    else:
        plan.para = [{'nombre': nombre_contacto(informe), 'correo': c} for c in correos[:1]]
        plan.asunto = f"Informe de ensayo {informe.codigo_informe} · {informe.solicitud.cotizacion.cliente.razon_social}"
        if not plan.para:
            plan.aviso = (plan.aviso + ' ' if plan.aviso else '') + "El cliente no tiene correo registrado: agrégalo al redactar."
    plan.para = [p for p in plan.para if p['correo'] not in propias] or plan.para
    return plan


def _cuerpo_html(informe, saludo):
    proyecto = informe.solicitud.cotizacion.proyecto_asociado or ''
    enlace = enlace_validacion(informe)
    return (
        f"<p>{saludo},</p>"
        f"<p>Adjuntamos el informe de ensayo <b>{informe.codigo_informe}</b>"
        f"{' del proyecto ' + proyecto if proyecto else ''} (solicitud {informe.solicitud.codigo_solicitud}).</p>"
        f"<p>Puede validar su autenticidad escaneando el código QR del informe o ingresando a: "
        f'<a href="{enlace}">{enlace}</a></p>'
        "<p>Quedamos atentos a sus comentarios.</p><p><br></p>"
    )


@transaction.atomic
def crear_borrador_correo(user, informe, plan=None):
    """Crea el borrador en el correo (respuesta o nuevo) con el PDF adjunto y lo liga al informe."""
    from correo.mensajeria import agregar_adjunto, crear_mensaje, nuevo_message_id
    from correo.models import Mensaje
    from correo.views_redactar import firma_por_defecto

    plan = plan or planear_correo(user, informe)
    if not plan.puede:
        raise PermissionError(plan.motivo)
    nombre = (plan.para[0]['nombre'] if plan.para else '').split(' ')[0] if plan.para else ''
    saludo = f"Estimado/a {nombre}" if nombre else "Estimados señores"
    firma = firma_por_defecto(user, plan.cuenta, respuesta=plan.modo == 'respuesta')
    o = plan.origen
    borrador = crear_mensaje(
        plan.cuenta, 'borradores', de=plan.cuenta.direccion, de_nombre=plan.cuenta.nombre,
        para=plan.para, cc=plan.cc, asunto=plan.asunto,
        html=_cuerpo_html(informe, saludo) + firma,
        in_reply_to=o.message_id if o else '',
        references=(f'{o.references} {o.message_id}'.strip() if o else ''),
        leido=True, estado=Mensaje.BORRADOR, creado_por=user, hilo=o.hilo if o else None,
        message_id=nuevo_message_id(plan.cuenta),
    )
    if informe.archivo_pdf:
        with informe.archivo_pdf.open('rb') as f:
            agregar_adjunto(borrador, f"{informe.codigo_informe}.pdf", 'application/pdf', f.read())
    informe.mensaje_envio = borrador.pk
    informe.save(update_fields=['mensaje_envio'])
    return borrador


def marcar_enviado(informe, canal):
    from .models import InformeFinal
    InformeFinal.objects.filter(pk=informe.pk).update(
        estado_envio='enviado', fecha_envio=timezone.now(), canal_envio=canal,
    )


def telefono_whatsapp(informe):
    """Celular del cliente listo para wa.me (si son 9 dígitos se asume Perú)."""
    cotizacion = informe.solicitud.cotizacion
    cliente = cotizacion.cliente
    crudo = getattr(cotizacion, 'telefono_contacto', '') or getattr(cliente, 'celular_contacto', '') or ''
    n = ''.join(ch for ch in str(crudo) if ch.isdigit())
    return f'51{n}' if len(n) == 9 else n


def texto_whatsapp(informe):
    nombre = nombre_contacto(informe).split(' ')[0]
    saludo = f"Hola {nombre}" if nombre else "Hola"
    return (f"{saludo}, le saluda Grupo VICAF. Su informe de ensayo {informe.codigo_informe} ya está listo. "
            f"Puede verlo y validarlo aquí: {enlace_validacion(informe)}")


def url_whatsapp(informe, telefono=None):
    return f"https://wa.me/{telefono if telefono is not None else telefono_whatsapp(informe)}?text={quote(texto_whatsapp(informe))}"
