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
