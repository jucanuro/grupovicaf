from django.core.exceptions import ValidationError
from django.core.validators import FileExtensionValidator
from django.db import models
from django.utils import timezone


class Acreditacion(models.Model):
    """Registro de acreditación (organismo + alcance) mostrado en /acreditacion/.

    Sin SeoModel: la página /acreditacion/ es única y su meta_title/
    meta_description se definen en la plantilla (mismo criterio que la home),
    mientras que este modelo son los registros/alcances que se listan dentro
    de ella — puede haber más de uno (p. ej. distintos alcances de ensayo).
    """

    organismo = models.CharField(max_length=150, default='INACAL')
    numero_acreditacion = models.CharField(max_length=50, verbose_name='N.º de acreditación')
    alcance = models.TextField(help_text='Descripción del alcance de acreditación (qué ensayos cubre).')

    vigencia_desde = models.DateField(blank=True, null=True)
    vigencia_hasta = models.DateField(blank=True, null=True)

    documento = models.FileField(
        upload_to='acreditacion/documentos/', blank=True,
        validators=[FileExtensionValidator(['pdf'])],
        help_text='Certificado de acreditación en PDF.',
    )
    logo = models.ImageField(upload_to='acreditacion/logos/', blank=True)
    logo_alt = models.CharField(
        max_length=125, blank=True,
        help_text='Obligatorio si se sube logo: describe el logo para accesibilidad y SEO.',
    )

    servicios_acreditados = models.ManyToManyField(
        'servicios.Servicio', blank=True, related_name='acreditaciones',
        verbose_name='Ensayos acreditados',
    )

    orden = models.PositiveIntegerField(default=0)
    activo = models.BooleanField(default=True)

    creado = models.DateTimeField(auto_now_add=True)
    actualizado = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Acreditación'
        verbose_name_plural = 'Acreditaciones'
        ordering = ['orden', '-vigencia_desde']

    def __str__(self):
        return f'{self.organismo} — {self.numero_acreditacion}'

    def clean(self):
        super().clean()
        if self.logo and not self.logo_alt:
            raise ValidationError({'logo_alt': 'Obligatorio cuando se sube un logo.'})

    @property
    def vigente(self):
        hoy = timezone.now().date()
        if self.vigencia_hasta and self.vigencia_hasta < hoy:
            return False
        return True


ARCHIVO_MAX_BYTES = 10 * 1024 * 1024
EXTENSIONES_IMAGEN = ('jpg', 'jpeg', 'png', 'webp')
EXTENSIONES_ARCHIVO = ('pdf',) + EXTENSIONES_IMAGEN


def validar_archivo(archivo):
    """Acepta solo un PDF real (firma %PDF-) o una imagen que Pillow pueda abrir, de 10 MB como máximo.

    La extensión sola no basta: el archivo se sirve tal cual desde /media/ y se
    muestra en el modal de la propia web (REQ-WEB-40).
    """
    if archivo.size and archivo.size > ARCHIVO_MAX_BYTES:
        raise ValidationError('El archivo no puede pesar más de 10 MB.')
    posicion = archivo.tell() if hasattr(archivo, 'tell') else 0
    archivo.seek(0)
    try:
        if archivo.name.lower().endswith('.pdf'):
            if archivo.read(5) != b'%PDF-':
                raise ValidationError('El archivo no es un PDF válido.')
        else:
            from PIL import Image
            try:
                Image.open(archivo).verify()
            except Exception:
                raise ValidationError('El archivo no es una imagen válida (JPG, PNG o WebP).')
    finally:
        archivo.seek(posicion)


LOGO_MAX_BYTES = 2 * 1024 * 1024


def validar_logo(imagen):
    """El logo va en cada card de la home y de /acreditacion/: 2 MB como máximo (REQ-WEB-62)."""
    if imagen.size and imagen.size > LOGO_MAX_BYTES:
        raise ValidationError('El logo no puede pesar más de 2 MB.')


def validar_pdf(archivo):
    """Validador de v3; solo lo importa la migración 0002_certificacion."""
    validar_archivo(archivo)


class CertificacionQuerySet(models.QuerySet):
    def publicadas(self, hoy=None):
        """Certificaciones que se muestran en la web (RN-15, REQ-WEB-42).

        Activas, con archivo y, si tienen vigencia, sin pasar según la fecha de
        Lima. El día del vencimiento todavía cuenta como vigente.
        """
        hoy = hoy or timezone.localdate()
        return (
            self.filter(activo=True)
            .filter(models.Q(vigencia_hasta__isnull=True) | models.Q(vigencia_hasta__gte=hoy))
            .exclude(archivo='')
        )


    def para_card(self):
        """Lista blanca de campos para las cards y el modal (regla 2 de CLAUDE.md)."""
        return self.only(
            'id', 'titulo', 'descripcion', 'tipo', 'institucion', 'logo', 'logo_ancho', 'logo_alto', 'archivo', 'vigencia_hasta', 'orden',
        )


def primera_acreditacion(certificaciones):
    """Primera certificación de tipo Acreditación de una lista ya publicada.

    Es la que abren los accesos "Ver certificado" de INACAL (REQ-WEB-50).
    """
    return next((c for c in certificaciones if c.tipo == Certificacion.TIPO_ACREDITACION), None)


class Certificacion(models.Model):
    """Acreditación, certificación ISO u otro reconocimiento mostrado como card.

    Modelo único desde specs/WEB v4. Desde v6 la card de /acreditacion/ y de
    la home lleva arriba el logo de la institución (o un sello genérico si no
    tiene), al medio el tipo, el título y la descripción, y abajo "Ver
    documento"; abre el archivo (imagen o PDF) en un modal. Sin SeoModel: no
    tiene página propia.
    """

    TIPO_ACREDITACION = 'acreditacion'
    TIPO_ISO = 'iso'
    TIPO_OTRO = 'otro'
    TIPOS = [
        (TIPO_ACREDITACION, 'Acreditación'),
        (TIPO_ISO, 'Certificación ISO'),
        (TIPO_OTRO, 'Otro'),
    ]

    titulo = models.CharField(max_length=120, verbose_name='Título', help_text='Ej.: Acreditación INACAL LE-230')
    descripcion = models.CharField(
        max_length=200, verbose_name='Descripción corta',
        help_text='Una o dos frases; la card muestra hasta 3 líneas.',
    )
    tipo = models.CharField(max_length=20, choices=TIPOS, default=TIPO_OTRO)
    institucion = models.CharField(
        max_length=150, verbose_name='Institución que la otorga',
        help_text='Ej.: Instituto Nacional de Calidad (INACAL)',
    )
    logo = models.ImageField(
        upload_to='certificaciones/logos/', blank=True, width_field='logo_ancho', height_field='logo_alto',
        validators=[FileExtensionValidator(EXTENSIONES_IMAGEN), validar_logo],
        verbose_name='Logo de la institución',
        help_text='JPG, PNG o WebP, máximo 2 MB, de preferencia con fondo transparente o blanco. '
                  'Sin logo, la card muestra un sello genérico.',
    )
    # Los llena Django al subir el logo: width/height del <img> sin abrir el archivo (regla 17).
    logo_ancho = models.PositiveIntegerField(blank=True, null=True, editable=False)
    logo_alto = models.PositiveIntegerField(blank=True, null=True, editable=False)

    archivo = models.FileField(
        upload_to='certificaciones/',
        validators=[FileExtensionValidator(EXTENSIONES_ARCHIVO), validar_archivo],
        verbose_name='Archivo (imagen o PDF)',
        help_text='JPG, PNG, WebP o PDF, máximo 10 MB. En móvil el PDF se abre en una pestaña nueva.',
    )
    vigencia_hasta = models.DateField(
        blank=True, null=True, verbose_name='Vigente hasta',
        help_text='Opcional. Desde el día siguiente la certificación deja de mostrarse en la web.',
    )

    orden = models.PositiveIntegerField(default=0)
    activo = models.BooleanField(default=True)

    creado = models.DateTimeField(auto_now_add=True)
    actualizado = models.DateTimeField(auto_now=True)

    objects = CertificacionQuerySet.as_manager()

    class Meta:
        verbose_name = 'Certificación'
        verbose_name_plural = 'Certificaciones'
        ordering = ['orden', 'titulo']

    def __str__(self):
        return self.titulo

    @property
    def es_pdf(self):
        return bool(self.archivo) and self.archivo.name.lower().endswith('.pdf')

    @property
    def vigente(self):
        return self.vigencia_hasta is None or self.vigencia_hasta >= timezone.localdate()

    @property
    def publicada(self):
        return self.activo and bool(self.archivo) and self.vigente
