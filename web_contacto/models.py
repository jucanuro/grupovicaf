from django.conf import settings
from django.core.validators import MinValueValidator, RegexValidator
from django.db import models

ESTADO_CHOICES = [
    ('nuevo', 'Nuevo'),
    ('atendido', 'Atendido'),
    ('cerrado', 'Cerrado'),
]

validar_ruc = RegexValidator(r'^\d{11}$', 'El RUC debe tener 11 dígitos numéricos.')


class MensajeContacto(models.Model):
    """Mensaje del formulario público /contacto/. Entra al flujo del LIMS vía panel de atención."""

    nombre = models.CharField(max_length=150)
    correo = models.EmailField()
    telefono = models.CharField(max_length=20, blank=True)
    asunto = models.CharField(max_length=150)
    mensaje = models.TextField()

    origen = models.CharField(
        max_length=255, blank=True,
        help_text='Ruta de la página que generó el contacto (para saber qué keyword convierte).',
    )
    ip = models.GenericIPAddressField(null=True, blank=True)

    estado = models.CharField(max_length=10, choices=ESTADO_CHOICES, default='nuevo')
    atendido_por = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='mensajes_contacto_atendidos',
    )
    fecha_atencion = models.DateTimeField(null=True, blank=True)

    creado = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Mensaje de contacto'
        verbose_name_plural = 'Mensajes de contacto'
        ordering = ['-creado']

    def __str__(self):
        return f'{self.nombre} - {self.asunto}'


class SolicitudCotizacionWeb(models.Model):
    """Solicitud pública de cotización: RUC + servicios elegidos + cantidad estimada.

    Al procesarse (ver web_contacto.services) crea/reutiliza clientes.Cliente
    por RUC y genera una servicios.Cotizacion pendiente con sus detalles.
    cliente/cotizacion quedan enlazados aquí solo como auditoría del origen web.
    """

    ruc = models.CharField(max_length=11, validators=[validar_ruc])
    razon_social = models.CharField(max_length=255)
    persona_contacto = models.CharField(max_length=200)
    correo_contacto = models.EmailField()
    telefono_contacto = models.CharField(max_length=20)

    necesidad = models.TextField(help_text='Descripción libre de la necesidad del visitante.')

    origen = models.CharField(
        max_length=255, blank=True,
        help_text='Ruta de la página que generó la solicitud (para saber qué keyword convierte).',
    )
    ip = models.GenericIPAddressField(null=True, blank=True)

    cliente = models.ForeignKey(
        'clientes.Cliente', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='solicitudes_web',
    )
    cotizacion = models.OneToOneField(
        'servicios.Cotizacion', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='solicitud_web',
    )

    creado = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Solicitud de cotización web'
        verbose_name_plural = 'Solicitudes de cotización web'
        ordering = ['-creado']

    def __str__(self):
        return f'{self.razon_social} ({self.ruc})'


class SolicitudCotizacionItem(models.Model):
    solicitud = models.ForeignKey(SolicitudCotizacionWeb, on_delete=models.CASCADE, related_name='items')
    servicio_publicado = models.ForeignKey(
        'web_catalogo.ServicioPublicado', on_delete=models.PROTECT, related_name='+',
    )
    cantidad_estimada = models.PositiveIntegerField(default=1, validators=[MinValueValidator(1)])

    class Meta:
        verbose_name = 'Ítem de solicitud de cotización web'
        verbose_name_plural = 'Ítems de solicitud de cotización web'

    def __str__(self):
        return f'{self.servicio_publicado.titulo_publico} x{self.cantidad_estimada}'
