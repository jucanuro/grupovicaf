"""Interfaces para conectar la recepción (Paso 4) y el envío (Paso 5).

Todavía NO se implementan: quedan definidas para que las pantallas de los
pasos 2 y 3 hablen con ellas y luego solo cambie la implementación
(Cloudflare Email Routing + R2 para recibir, Amazon SES para enviar).
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass(frozen=True)
class ResultadoEnvio:
    ok: bool
    id_proveedor: str = ''   # p. ej. el MessageId de SES
    error: str = ''
    reintentar: bool = False


class ServicioRecepcion(ABC):
    """Guarda un mensaje entrante a partir de su .eml original en R2.

    Lo usarán el webhook firmado de Cloudflare (Paso 4) y el importador IMAP
    del histórico (Paso 6). Debe ser idempotente por sha256.
    """

    @abstractmethod
    def guardar(self, clave_r2: str, sha256: str):
        """Lee el .eml, lo parsea, sanitiza el HTML, arma el hilo y devuelve el Mensaje."""


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
            return ResultadoEnvio(ok=False, error='Rebote simulado: el dominio no existe.', reintentar=True)
        return ResultadoEnvio(ok=True, id_proveedor=f'simulado-{mensaje.pk}')


def servicio_envio() -> ServicioEnvio:
    """Implementación activa. En el Paso 5 devolverá la de Amazon SES."""
    return ServicioEnvioSimulado()
