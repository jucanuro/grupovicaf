from django.db import models


class NegocioConfig(models.Model):
    """Datos NAP y de negocio para JSON-LD y footer del sitio público.

    Fuente única: cualquier plantilla que muestre nombre, dirección, teléfono
    u horario debe leerlo de aquí (vía el context processor
    ``siteconfig.context_processors.negocio``), nunca hardcodeado.
    Singleton: se espera una sola fila (pk=1).
    """

    nombre = models.CharField(max_length=150, default='Grupo VICAF SAC')
    descripcion = models.CharField(max_length=300)

    direccion_calle = models.CharField(max_length=200)
    direccion_localidad = models.CharField(max_length=100, default='Cajamarca')
    direccion_region = models.CharField(max_length=100, default='Cajamarca')
    direccion_codigo_postal = models.CharField(max_length=20, blank=True)
    direccion_pais = models.CharField(max_length=2, default='PE')

    telefono = models.CharField(max_length=20)
    whatsapp = models.CharField(max_length=20, blank=True)
    correo = models.EmailField(default='informes@grupovicaf.com')

    latitud = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    longitud = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)

    horario_semana_apertura = models.TimeField(null=True, blank=True)
    horario_semana_cierre = models.TimeField(null=True, blank=True)
    horario_sabado_apertura = models.TimeField(null=True, blank=True)
    horario_sabado_cierre = models.TimeField(null=True, blank=True)

    ciudades_cobertura = models.JSONField(default=list, blank=True)

    acreditacion_entidad = models.CharField(max_length=100, default='INACAL')
    acreditacion_codigo = models.CharField(max_length=50, default='LE-230')

    linkedin_url = models.URLField(blank=True)
    facebook_url = models.URLField(blank=True)
    instagram_url = models.URLField(blank=True)

    class Meta:
        verbose_name = 'Configuración del negocio'
        verbose_name_plural = 'Configuración del negocio'

    def __str__(self):
        return self.nombre

    def save(self, *args, **kwargs):
        self.pk = 1
        super().save(*args, **kwargs)
