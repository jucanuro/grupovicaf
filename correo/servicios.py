"""Interfaces de recepción y envío, y la implementación activa de cada una.

- Recepción: `correo.recepcion.RecepcionEML` lee un .eml real (RFC 5322) y lo
  guarda en la cuenta destinataria. La usan `recibir_eml`, el puente de Mailpit
  en desarrollo y, en el Paso 4, el webhook de Cloudflare Email Routing.
- Envío: `ServicioEnvioSimulado` (no sale nada) o `correo.envio.ServicioEnvioSMTP`
  (MIME completo por SMTP: Mailpit en desarrollo, Amazon SES en producción).
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass(frozen=True)
class ResultadoEnvio:
    ok: bool
    id_proveedor: str = ''   # p. ej. el MessageId de SES
    error: str = ''
    reintentar: bool = False
    eml: bytes = b''         # el mensaje MIME tal como salió (se guarda en el Mensaje)


class ServicioRecepcion(ABC):
    """Guarda un mensaje entrante a partir de su .eml original en R2.

    Lo usarán el webhook firmado de Cloudflare (Paso 4) y el importador IMAP
    del histórico (Paso 6). Debe ser idempotente por sha256.
    """

    @abstractmethod
    def recibir(self, crudo: bytes, destinatarios=()):
        """Parsea el .eml, sanitiza el HTML, arma el hilo y devuelve los Mensajes creados
        (uno por cuenta VICAF destinataria). `destinatarios`: los RCPT TO del sobre,
        si se conocen (incluyen las copias ocultas que no van en las cabeceras)."""

    def guardar(self, clave_r2: str, sha256: str):
        """Variante del Paso 4: el .eml ya está en el almacén (R2) con esa clave."""
        from .almacen import almacen_correo

        with almacen_correo.open(clave_r2, 'rb') as archivo:
            return self.recibir(archivo.read())


class ServicioEnvio(ABC):
    """Envía un mensaje de la Bandeja de salida y lo pasa a Enviados."""

    @abstractmethod
    def enviar(self, mensaje) -> ResultadoEnvio:
        """Arma el MIME (con adjuntos e imágenes incrustadas) y lo entrega al proveedor."""


class ServicioEnvioSimulado(ServicioEnvio):
    """Pasos 2 y 3: no sale nada a Internet. Marca el mensaje como enviado.

    Un destinatario que termina en `@falla.invalid` simula un rebote, para
    poder probar la Bandeja de salida (fallidos y reintento).
    """

    def enviar(self, mensaje) -> ResultadoEnvio:
        destinos = [d['correo'] for d in list(mensaje.para) + list(mensaje.cc) + list(mensaje.cco)]
        if any(d.endswith('@falla.invalid') for d in destinos):
            return ResultadoEnvio(ok=False, error='Rebote simulado: el dominio no existe.', reintentar=False)
        return ResultadoEnvio(ok=True, id_proveedor=f'simulado-{mensaje.pk}')


def servicio_envio() -> ServicioEnvio:
    """Implementación activa según CORREO_ENVIO ('simulado' o 'smtp')."""
    from django.conf import settings

    if settings.CORREO_ENVIO == 'smtp':
        from .envio import ServicioEnvioSMTP
        return ServicioEnvioSMTP()
    return ServicioEnvioSimulado()
