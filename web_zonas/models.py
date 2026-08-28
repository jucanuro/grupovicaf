from django.db import models

from grupovicaf.seo import SeoModel


class ZonaCoberturaQuerySet(models.QuerySet):
    def activas(self):
        return self.filter(activo=True)


class ZonaCobertura(SeoModel):
    """Landing page de intención local: "estudio de suelos en <ciudad>".

    ADVERTENCIA (ver CLAUDE.md regla 16): `introduccion` y `contenido` son
    redacción única por zona, nunca generada sustituyendo la ciudad en una
    plantilla — dos páginas casi idénticas se canibalizan y Google las trata
    como doorway pages. `titulo_h1` sí sigue un patrón ("Laboratorio de
    suelos en <ciudad>") porque es el campo que fija la keyword objetivo de
    la URL (regla 10), no contenido de lectura.
    """

    nombre = models.CharField(max_length=100, help_text='Ej: "Jaén".')
    provincia = models.CharField(max_length=100)
    departamento = models.CharField(max_length=100, default='Cajamarca')

    titulo_h1 = models.CharField(
        max_length=150, help_text='H1 de la página. Ej: "Laboratorio de suelos en Jaén".',
    )
    introduccion = models.TextField(
        help_text='Párrafo de entrada (1-2 líneas), redacción única de esta zona.',
    )
    contenido = models.TextField(
        help_text=(
            'Redacción única de esta zona (no reutilizar entre zonas). Debe incluir: '
            'proyectos reales ejecutados en la zona, tiempos de respuesta típicos, '
            'cómo se envían las muestras desde ahí hacia el laboratorio, y referencias '
            'locales (vías de acceso, obras conocidas, gremios). Ver CLAUDE.md regla 16.'
        ),
    )

    servicios = models.ManyToManyField(
        'web_catalogo.ServicioPublicado', blank=True, related_name='zonas',
        help_text='Ensayos disponibles para esta zona. El listado se genera automáticamente.',
    )

    latitud = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    longitud = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)

    es_sede = models.BooleanField(
        default=False,
        help_text='Marca la sede física del laboratorio (Cajamarca). Las demás son cobertura.',
    )
    orden = models.PositiveIntegerField(default=0)
    activo = models.BooleanField(default=True)

    creado = models.DateTimeField(auto_now_add=True)
    actualizado = models.DateTimeField(auto_now=True)

    objects = ZonaCoberturaQuerySet.as_manager()

    class Meta:
        verbose_name = 'Zona de cobertura'
        verbose_name_plural = 'Zonas de cobertura'
        ordering = ['-es_sede', 'orden', 'nombre']

    def __str__(self):
        return self.nombre
