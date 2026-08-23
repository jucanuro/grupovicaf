from django.db import models
from django.utils import timezone


class CarruselInicioQuerySet(models.QuerySet):
    def vigentes(self):
        ahora = timezone.now()
        return (
            self.filter(activo=True)
            .filter(models.Q(fecha_inicio__isnull=True) | models.Q(fecha_inicio__lte=ahora))
            .filter(models.Q(fecha_fin__isnull=True) | models.Q(fecha_fin__gte=ahora))
        )


class CarruselInicio(models.Model):
    """Slide del carrusel de la home. Portado de _ref/vicafpro/inicio/models.py."""

    titulo = models.CharField(max_length=100)
    descripcion = models.TextField()
    imagen = models.ImageField(upload_to='inicio/carrusel/')
    alt_text = models.CharField(
        max_length=125,
        verbose_name='Texto alternativo',
        help_text='Describe la escena para accesibilidad y SEO de imagen. Obligatorio.',
    )
    enlace = models.URLField(blank=True)

    orden = models.PositiveIntegerField(default=0)
    activo = models.BooleanField(default=True)
    fecha_inicio = models.DateTimeField(
        blank=True, null=True,
        help_text='Si se define, el slide no se muestra antes de esta fecha.',
    )
    fecha_fin = models.DateTimeField(
        blank=True, null=True,
        help_text='Si se define, el slide deja de mostrarse después de esta fecha.',
    )

    creado = models.DateTimeField(auto_now_add=True)
    actualizado = models.DateTimeField(auto_now=True)

    objects = CarruselInicioQuerySet.as_manager()

    class Meta:
        verbose_name = 'Slide del carrusel'
        verbose_name_plural = 'Carrusel de inicio'
        ordering = ['orden', '-creado']

    def __str__(self):
        return self.titulo
