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


PDF_MAX_BYTES = 10 * 1024 * 1024


def validar_pdf(archivo):
    """Rechaza lo que no sea un PDF real (firma %PDF-) o pese más de 10 MB.

    La extensión sola no basta: el archivo se sirve tal cual desde /media/ y se
    embebe en un <iframe> de la propia web (REQ-WEB-36 y 37).
    """
    if archivo.size and archivo.size > PDF_MAX_BYTES:
        raise ValidationError('El PDF no puede pesar más de 10 MB.')
    posicion = archivo.tell() if hasattr(archivo, 'tell') else 0
    archivo.seek(0)
    firma = archivo.read(5)
    archivo.seek(posicion)
    if firma != b'%PDF-':
        raise ValidationError('El archivo no es un PDF válido.')


class CertificacionQuerySet(models.QuerySet):
    def publicadas(self, hoy=None):
        """Certificaciones que se muestran en la web (RN-15).

        Activas, con PDF y con la vigencia sin pasar según la fecha de Lima. El
        día del vencimiento todavía cuenta como vigente.
        """
        hoy = hoy or timezone.localdate()
        return self.filter(activo=True, vigencia_hasta__gte=hoy).exclude(archivo='')


class Certificacion(models.Model):
    """Certificación de un sistema de gestión (p. ej. ISO 9001) mostrada en /acreditacion/.

    Aparte de Acreditacion: una certificación de sistema de gestión no tiene
    ensayos acreditados y sí norma y sede. Sin SeoModel por el mismo motivo que
    Acreditacion: no tiene página propia, se lista dentro de /acreditacion/.
    """

    norma = models.CharField(max_length=60, help_text='Ej.: ISO 9001:2015')
    sistema = models.CharField(
        max_length=120, blank=True, verbose_name='Sistema de gestión',
        help_text='Ej.: Sistema de Gestión de la Calidad',
    )
    numero_certificado = models.CharField(max_length=50, unique=True, verbose_name='N.º de certificado')
    organismo = models.CharField(max_length=150, verbose_name='Organismo certificador')
    alcance = models.TextField(help_text='Actividades que cubre el certificado, tal como figuran en el PDF.')
    sede = models.CharField(max_length=200, blank=True, help_text='Dirección donde se realizan las actividades.')

    fecha_emision = models.DateField(blank=True, null=True, verbose_name='Fecha de emisión')
    vigencia_hasta = models.DateField(
        verbose_name='Vigente hasta',
        help_text='Desde el día siguiente la certificación deja de mostrarse en la web.',
    )

    archivo = models.FileField(
        upload_to='certificaciones/', blank=True,
        validators=[FileExtensionValidator(['pdf']), validar_pdf],
        verbose_name='Certificado (PDF)',
        help_text='Sin PDF la certificación no se muestra en la web. Máximo 10 MB.',
    )
    sello = models.ImageField(upload_to='certificaciones/sellos/', blank=True)
    sello_alt = models.CharField(
        max_length=125, blank=True, verbose_name='Texto alternativo del sello',
        help_text='Obligatorio si se sube sello: describe el sello para accesibilidad y SEO.',
    )

    orden = models.PositiveIntegerField(default=0)
    activo = models.BooleanField(default=True)

    creado = models.DateTimeField(auto_now_add=True)
    actualizado = models.DateTimeField(auto_now=True)

    objects = CertificacionQuerySet.as_manager()

    class Meta:
        verbose_name = 'Certificación'
        verbose_name_plural = 'Certificaciones'
        ordering = ['orden', '-vigencia_hasta']

    def __str__(self):
        return f'{self.norma} — {self.numero_certificado}'

    def clean(self):
        super().clean()
        if self.sello and not self.sello_alt:
            raise ValidationError({'sello_alt': 'Obligatorio cuando se sube un sello.'})

    @property
    def vigente(self):
        return self.vigencia_hasta >= timezone.localdate()

    @property
    def publicada(self):
        return self.activo and bool(self.archivo) and self.vigente
