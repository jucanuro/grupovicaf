"""Enviar una cotización al cliente desde el correo del sistema (como el informe, HU-LIMS-47).

Se crea el borrador en el módulo de correo con el destinatario del cliente, el asunto y un cuerpo
ya redactado; el PDF de la cotización se adjunta en segundo plano. La persona revisa y envía.
"""
from django.db import transaction
from django.urls import reverse

from correo.cuentas import GESTIONA, cuentas_de, permite, roles_de
from correo.enlaces import crear_enlace, url_correo
from correo.mensajeria import crear_mensaje, nuevo_message_id
from correo.models import Mensaje


def destinatario(cotizacion):
    cliente = cotizacion.cliente
    correo = (cotizacion.correo_contacto or cliente.correo_contacto or '').strip().lower()
    nombre = (cotizacion.persona_contacto or cliente.persona_contacto or '').strip()
    return correo, nombre


def cuenta_de_empresa(user):
    roles = roles_de(user)
    gestionables = [c for c in cuentas_de(user) if permite(roles.get(c.pk), GESTIONA)]
    empresa = [c for c in gestionables if not c.personal]
    return (empresa or gestionables or [None])[0]


def _cuerpo(cotizacion, nombre):
    saludo = f"Estimado/a {nombre.split(' ')[0]}" if nombre else "Estimados señores"
    return (
        f"<p>{saludo},</p>"
        f"<p>Adjuntamos la cotización <b>{cotizacion.numero_oferta or 'S/N'}</b>"
        f"{' por ' + cotizacion.asunto_servicio if cotizacion.asunto_servicio else ''}.</p>"
        "<p>Quedamos atentos a su confirmación para coordinar los ensayos.</p><p><br></p>"
    )


@transaction.atomic
def crear_borrador(user, cotizacion):
    """Borrador de correo para la cotización. Devuelve (borrador, motivo_si_no)."""
    from correo.tasks import adjuntar_cotizacion
    from correo.views_redactar import firma_por_defecto

    correo_cliente, nombre = destinatario(cotizacion)
    if not correo_cliente:
        return None, 'El cliente no tiene correo registrado: agrégalo en la cotización o en el cliente.'
    cuenta = cuenta_de_empresa(user)
    if cuenta is None:
        return None, 'No tienes una cuenta de correo desde la que puedas enviar.'
    borrador = crear_mensaje(
        cuenta, 'borradores', de=cuenta.direccion, de_nombre=cuenta.nombre,
        para=[{'nombre': nombre, 'correo': correo_cliente}],
        asunto=f"Cotización {cotizacion.numero_oferta or 'S/N'}" + (f" · {cotizacion.asunto_servicio}" if cotizacion.asunto_servicio else ''),
        html=_cuerpo(cotizacion, nombre) + firma_por_defecto(user, cuenta, respuesta=False),
        leido=True, estado=Mensaje.BORRADOR, creado_por=user, message_id=nuevo_message_id(cuenta),
    )
    transaction.on_commit(lambda: adjuntar_cotizacion.delay(borrador.pk, cotizacion.pk, user.pk))
    return borrador, ''


def url_redactar(request, borrador):
    destino = reverse('borrador', urlconf='grupovicaf.urls_correo', args=[borrador.pk]) + '?completo=1'
    entrar = reverse('entrar', urlconf='grupovicaf.urls_correo')
    return url_correo(request, entrar, t=crear_enlace(request.user, destino))
