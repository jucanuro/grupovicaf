"""Modelo de datos del módulo de correo (VCF-LIMS, opción B).

Aprobado por el Gerente el 2026-11-12 (documento VCF-LIMS_DIS_correo_v1).
El acceso a cada cuenta se valida SIEMPRE en el servidor con AccesoCuenta
(ver correo.cuentas). Los archivos (.eml, adjuntos) viven fuera de MEDIA_ROOT
(correo.almacen).
"""
import uuid

from django.conf import settings
from django.contrib.postgres.indexes import GinIndex
from django.contrib.postgres.search import SearchVectorField
from django.db import models
from django.db.models import Q

from .almacen import obtener_almacen


class CuentaCorreo(models.Model):
    direccion = models.EmailField('dirección', unique=True)
    nombre = models.CharField('nombre visible', max_length=120)
    slug = models.SlugField(unique=True, help_text='Se usa en la URL: /c/<slug>/bandeja/')
    activa = models.BooleanField(default=True)
    firma_predeterminada = models.ForeignKey(
        'Firma', null=True, blank=True, on_delete=models.SET_NULL, related_name='+',
        verbose_name='firma predeterminada',
    )
    creada_en = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['nombre']
        verbose_name = 'cuenta de correo'
        verbose_name_plural = 'cuentas de correo'

    def __str__(self):
        return self.direccion


class AccesoCuenta(models.Model):
    LECTURA = 'lectura'
    GESTIONA = 'gestiona'
    ADMINISTRA = 'administra'
    ROLES = [
        (LECTURA, 'Solo lectura'),
        (GESTIONA, 'Gestiona (responde, mueve, asigna)'),
        (ADMINISTRA, 'Administra la cuenta'),
    ]
    NIVEL = {LECTURA: 1, GESTIONA: 2, ADMINISTRA: 3}

    usuario = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='accesos_correo')
    cuenta = models.ForeignKey(CuentaCorreo, on_delete=models.CASCADE, related_name='accesos')
    rol = models.CharField(max_length=12, choices=ROLES, default=GESTIONA)

    class Meta:
        constraints = [models.UniqueConstraint(fields=['usuario', 'cuenta'], name='correo_acceso_unico')]
        verbose_name = 'acceso a cuenta'
        verbose_name_plural = 'accesos a cuentas'

    def __str__(self):
        return f'{self.usuario} → {self.cuenta} ({self.get_rol_display()})'

    def permite(self, rol_minimo):
        return self.NIVEL[self.rol] >= self.NIVEL[rol_minimo]


class Carpeta(models.Model):
    ENTRADA, SALIDA, ENVIADOS, BORRADORES = 'entrada', 'salida', 'enviados', 'borradores'
    ARCHIVADOS, SPAM, PAPELERA, PERSONAL = 'archivados', 'spam', 'papelera', 'personal'
    TIPOS = [
        (ENTRADA, 'Bandeja de entrada'),
        (SALIDA, 'Bandeja de salida'),
        (ENVIADOS, 'Enviados'),
        (BORRADORES, 'Borradores'),
        (ARCHIVADOS, 'Archivados'),
        (SPAM, 'Correo no deseado'),
        (PAPELERA, 'Papelera'),
        (PERSONAL, 'Personalizada'),
    ]
    DEL_SISTEMA = [ENTRADA, SALIDA, ENVIADOS, BORRADORES, ARCHIVADOS, SPAM, PAPELERA]

    cuenta = models.ForeignKey(CuentaCorreo, on_delete=models.CASCADE, related_name='carpetas')
    tipo = models.CharField(max_length=12, choices=TIPOS, default=PERSONAL)
    nombre = models.CharField(max_length=80)
    orden = models.PositiveSmallIntegerField(default=100)

    class Meta:
        ordering = ['cuenta', 'orden', 'nombre']
        constraints = [
            models.UniqueConstraint(
                fields=['cuenta', 'tipo'], condition=~Q(tipo='personal'), name='correo_carpeta_sistema_unica',
            ),
            models.UniqueConstraint(fields=['cuenta', 'nombre'], name='correo_carpeta_nombre_unico'),
        ]

    def __str__(self):
        return f'{self.cuenta.slug} / {self.nombre}'

    @property
    def es_del_sistema(self):
        return self.tipo != self.PERSONAL


class Contacto(models.Model):
    correo = models.EmailField(unique=True)
    nombre = models.CharField(max_length=200, blank=True)
    empresa = models.CharField(max_length=200, blank=True)
    # Solo el vínculo: el contacto no copia RUC ni otros datos del LIMS.
    cliente = models.ForeignKey(
        'clientes.Cliente', null=True, blank=True, on_delete=models.SET_NULL, related_name='contactos_correo',
    )

    class Meta:
        ordering = ['nombre', 'correo']

    def __str__(self):
        return f'{self.nombre} <{self.correo}>' if self.nombre else self.correo


class Hilo(models.Model):
    cuenta = models.ForeignKey(CuentaCorreo, on_delete=models.CASCADE, related_name='hilos')
    asunto = models.CharField(max_length=500, blank=True)
    ultimo_mensaje_en = models.DateTimeField(db_index=True)
    participantes = models.ManyToManyField(Contacto, blank=True, related_name='hilos')

    class Meta:
        ordering = ['-ultimo_mensaje_en']

    def __str__(self):
        return self.asunto or '(sin asunto)'


def _ruta_eml(instancia, nombre):
    return f'{instancia.cuenta.slug}/eml/{uuid.uuid4().hex}.eml'


class Mensaje(models.Model):
    BORRADOR, EN_COLA, ENVIADO, FALLIDO, RECIBIDO = 'borrador', 'en_cola', 'enviado', 'fallido', 'recibido'
    ESTADOS = [
        (RECIBIDO, 'Recibido'),
        (BORRADOR, 'Borrador'),
        (EN_COLA, 'En cola de envío'),
        (ENVIADO, 'Enviado'),
        (FALLIDO, 'Falló el envío'),
    ]

    cuenta = models.ForeignKey(CuentaCorreo, on_delete=models.CASCADE, related_name='mensajes')
    carpeta = models.ForeignKey(Carpeta, on_delete=models.PROTECT, related_name='mensajes')
    hilo = models.ForeignKey(Hilo, on_delete=models.CASCADE, related_name='mensajes')

    message_id = models.CharField(max_length=998, blank=True, db_index=True)
    in_reply_to = models.CharField(max_length=998, blank=True)
    references = models.TextField(blank=True)

    de = models.EmailField()
    de_nombre = models.CharField(max_length=200, blank=True)
    # Listas de {"nombre": ..., "correo": ...}
    para = models.JSONField(default=list, blank=True)
    cc = models.JSONField(default=list, blank=True)
    cco = models.JSONField(default=list, blank=True)

    asunto = models.CharField(max_length=500, blank=True)
    cuerpo_texto = models.TextField(blank=True)
    cuerpo_html = models.TextField(blank=True, help_text='Ya sanitizado (correo.sanitizar).')
    vista_previa = models.CharField(max_length=200, blank=True)
    fecha = models.DateTimeField(db_index=True)
    leido = models.BooleanField(default=False)
    tiene_adjuntos = models.BooleanField(default=False)

    eml = models.FileField(storage=obtener_almacen, upload_to=_ruta_eml, blank=True, max_length=300)
    eml_sha256 = models.CharField(max_length=64, blank=True)
    tamano = models.PositiveIntegerField(default=0)

    estado_envio = models.CharField(max_length=10, choices=ESTADOS, default=RECIBIDO)
    intentos = models.PositiveSmallIntegerField(default=0)
    ultimo_error = models.TextField(blank=True)
    creado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name='+',
    )
    actualizado_en = models.DateTimeField(auto_now=True)

    busqueda = SearchVectorField(null=True, editable=False)

    class Meta:
        ordering = ['-fecha']
        indexes = [
            GinIndex(fields=['busqueda'], name='correo_mensaje_busqueda'),
            models.Index(fields=['cuenta', 'carpeta', '-fecha'], name='correo_mensaje_lista'),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=['cuenta', 'eml_sha256'], condition=~Q(eml_sha256=''), name='correo_mensaje_eml_unico',
            ),
        ]

    def __str__(self):
        return self.asunto or '(sin asunto)'

    @property
    def destinatarios(self):
        return list(self.para) + list(self.cc)


def _ruta_adjunto(instancia, nombre):
    return f'{instancia.mensaje.cuenta.slug}/adjuntos/{uuid.uuid4().hex}'


class Adjunto(models.Model):
    mensaje = models.ForeignKey(Mensaje, on_delete=models.CASCADE, related_name='adjuntos')
    nombre = models.CharField(max_length=255)
    tipo_mime = models.CharField(max_length=127, default='application/octet-stream')
    tamano = models.PositiveIntegerField(default=0)
    archivo = models.FileField(storage=obtener_almacen, upload_to=_ruta_adjunto, max_length=300)
    sha256 = models.CharField(max_length=64, blank=True)
    content_id = models.CharField(max_length=255, blank=True)
    incrustado = models.BooleanField(default=False, help_text='Imagen dentro del cuerpo (cid:).')

    class Meta:
        ordering = ['id']

    def __str__(self):
        return self.nombre

    @property
    def es_imagen(self):
        return self.tipo_mime.startswith('image/')


class Firma(models.Model):
    nombre = models.CharField(max_length=80)
    html = models.TextField(help_text='Ya sanitizado.')
    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.CASCADE, related_name='firmas_correo',
    )
    cuenta = models.ForeignKey(
        CuentaCorreo, null=True, blank=True, on_delete=models.CASCADE, related_name='firmas',
    )
    para_nuevos = models.BooleanField('predeterminada para correos nuevos', default=False)
    para_respuestas = models.BooleanField('predeterminada para respuestas', default=False)
    actualizada_en = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['nombre']
        constraints = [
            models.CheckConstraint(
                check=(Q(usuario__isnull=False, cuenta__isnull=True) | Q(usuario__isnull=True, cuenta__isnull=False)),
                name='correo_firma_de_usuario_o_de_cuenta',
            ),
        ]

    def __str__(self):
        return self.nombre

    @property
    def es_compartida(self):
        return self.cuenta_id is not None


class EventoMensaje(models.Model):
    ABRIO, RESPONDIO, REENVIO, ASIGNO, MOVIO = 'abrio', 'respondio', 'reenvio', 'asigno', 'movio'
    ARCHIVO, ELIMINO, ENVIO, ATENDIO, MARCO = 'archivo', 'elimino', 'envio', 'atendio', 'marco'
    TIPOS = [
        (ABRIO, 'abrió'),
        (RESPONDIO, 'respondió'),
        (REENVIO, 'reenvió'),
        (ASIGNO, 'asignó'),
        (MOVIO, 'movió'),
        (ARCHIVO, 'archivó'),
        (ELIMINO, 'eliminó'),
        (ENVIO, 'envió'),
        (ATENDIO, 'marcó como atendido'),
        (MARCO, 'marcó'),
    ]

    hilo = models.ForeignKey(Hilo, on_delete=models.CASCADE, related_name='eventos')
    mensaje = models.ForeignKey(Mensaje, null=True, blank=True, on_delete=models.SET_NULL, related_name='eventos')
    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name='+',
    )
    tipo = models.CharField(max_length=10, choices=TIPOS)
    detalle = models.JSONField(default=dict, blank=True)
    creado_en = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ['creado_en']
        verbose_name = 'evento'


class Asignacion(models.Model):
    PENDIENTE, ATENDIDO = 'pendiente', 'atendido'
    ESTADOS = [(PENDIENTE, 'Pendiente'), (ATENDIDO, 'Atendido')]

    hilo = models.OneToOneField(Hilo, on_delete=models.CASCADE, related_name='asignacion')
    asignado_a = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='+')
    asignado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name='+',
    )
    estado = models.CharField(max_length=10, choices=ESTADOS, default=PENDIENTE)
    actualizado_en = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'asignación'
        verbose_name_plural = 'asignaciones'


class EventoCuenta(models.Model):
    """Bitácora de la administración: quién creó cuentas o cambió accesos y cuándo."""
    CREO, EDITO, ACTIVO, DESACTIVO = 'creo', 'edito', 'activo', 'desactivo'
    DIO_ACCESO, CAMBIO_ROL, QUITO_ACCESO = 'dio_acceso', 'cambio_rol', 'quito_acceso'
    TIPOS = [
        (CREO, 'creó la cuenta'),
        (EDITO, 'editó la cuenta'),
        (ACTIVO, 'activó la cuenta'),
        (DESACTIVO, 'desactivó la cuenta'),
        (DIO_ACCESO, 'dio acceso'),
        (CAMBIO_ROL, 'cambió el rol'),
        (QUITO_ACCESO, 'quitó el acceso'),
    ]

    # SET_NULL: la bitácora sobrevive aunque se borre la cuenta (detalle guarda la dirección).
    cuenta = models.ForeignKey(CuentaCorreo, null=True, blank=True, on_delete=models.SET_NULL, related_name='bitacora')
    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name='+',
    )
    tipo = models.CharField(max_length=14, choices=TIPOS)
    detalle = models.JSONField(default=dict, blank=True)
    creado_en = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ['-creado_en']
        verbose_name = 'evento de administración'
        verbose_name_plural = 'bitácora de administración'

    def __str__(self):
        return f'{self.get_tipo_display()} · {self.detalle.get("cuenta", "")}'
