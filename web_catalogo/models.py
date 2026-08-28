from django.core.exceptions import ValidationError
from django.db import models

from grupovicaf.seo import SeoModel


class ServicioPublicadoQuerySet(models.QuerySet):
    def publicados(self):
        return self.filter(activo=True)


class ServicioPublicado(SeoModel):
    """Página pública de un ensayo del LIMS (servicios.Servicio).

    servicio es null=True/blank=True a propósito: cuando el ensayo interno
    no existe todavía, o cuando hay varias variantes del mismo ensayo en el
    LIMS (p. ej. Proctor Estándar vs Modificado) y no es seguro adivinar
    cuál corresponde, la página se publica igual con el companion sin
    vincular hasta que alguien lo confirme en el admin (autocomplete).
    categoria/subcategoria viven aquí y no en servicios.Servicio porque el
    LIMS no relaciona Servicio con CategoriaServicio/Subcategoria (esos
    campos solo existen en Cotizacion/PlantillaCotizacion) — regla 1 de
    CLAUDE.md: companion model, nunca se toca el modelo del LIMS.
    """

    servicio = models.OneToOneField(
        'servicios.Servicio', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='publicado',
    )
    categoria = models.ForeignKey(
        'servicios.CategoriaServicio', on_delete=models.PROTECT, related_name='servicios_publicados',
    )
    subcategoria = models.ForeignKey(
        'servicios.Subcategoria', on_delete=models.PROTECT, null=True, blank=True,
        related_name='servicios_publicados',
    )

    titulo_publico = models.CharField(
        max_length=150, help_text='Nombre comercial, no el código interno. Ej: "Ensayo CBR".',
    )
    resumen = models.CharField(max_length=300, help_text='Para listados y como meta description.')
    contenido = models.TextField(help_text='Página completa del ensayo (600-1000 palabras).')
    imagen = models.ImageField(upload_to='catalogo/servicios/', blank=True)
    imagen_alt = models.CharField(
        max_length=125, blank=True,
        help_text='Obligatorio si se sube imagen: describe la escena para accesibilidad y SEO.',
    )
    zona_principal = models.CharField(
        max_length=100, default='Cajamarca',
        help_text='Ciudad usada en el H1 ("Ensayo CBR en Cajamarca"). '
                   'Sin enlace a landing de zona todavía: web_zonas no existe.',
    )

    destacado = models.BooleanField(default=False)
    orden = models.PositiveIntegerField(default=0)
    activo = models.BooleanField(default=True)

    creado = models.DateTimeField(auto_now_add=True)
    actualizado = models.DateTimeField(auto_now=True)

    objects = ServicioPublicadoQuerySet.as_manager()

    class Meta:
        verbose_name = 'Servicio publicado'
        verbose_name_plural = 'Servicios publicados'
        ordering = ['categoria__nombre', 'subcategoria__nombre', 'orden', 'titulo_publico']

    def __str__(self):
        return self.titulo_publico

    def clean(self):
        super().clean()
        if self.imagen and not self.imagen_alt:
            raise ValidationError({'imagen_alt': 'Obligatorio cuando se sube una imagen.'})


class PreguntaFrecuente(models.Model):
    """Pregunta frecuente de una página de servicio, para el bloque FAQPage."""

    servicio_publicado = models.ForeignKey(
        ServicioPublicado, on_delete=models.CASCADE, related_name='preguntas',
    )
    pregunta = models.CharField(max_length=255)
    respuesta = models.TextField()
    orden = models.PositiveIntegerField(default=0)
    activo = models.BooleanField(default=True)

    class Meta:
        verbose_name = 'Pregunta frecuente'
        verbose_name_plural = 'Preguntas frecuentes'
        ordering = ['orden', 'id']

    def __str__(self):
        return self.pregunta


class ClienteDestacado(models.Model):
    """Companion de clientes.Cliente para el muro de logos de /clientes/."""

    cliente = models.OneToOneField(
        'clientes.Cliente', on_delete=models.CASCADE, related_name='destacado',
    )
    mostrar_logo = models.BooleanField(default=True)
    enlace = models.URLField(blank=True, help_text='Sitio web del cliente (opcional).')
    orden = models.PositiveIntegerField(default=0)
    activo = models.BooleanField(default=True)

    creado = models.DateTimeField(auto_now_add=True)
    actualizado = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Cliente destacado'
        verbose_name_plural = 'Clientes destacados'
        ordering = ['orden', 'id']

    def __str__(self):
        return f'Destacado: {self.cliente.razon_social}'


class MiembroEquipoPublicado(models.Model):
    """Companion de trabajadores.TrabajadorProfile para /equipo/."""

    perfil = models.OneToOneField(
        'trabajadores.TrabajadorProfile', on_delete=models.CASCADE, related_name='publicado',
    )
    bio_publica = models.TextField(
        blank=True, help_text='Biografía corta para la web. Nunca datos internos.',
    )
    mostrar_correo = models.BooleanField(default=False)
    orden = models.PositiveIntegerField(default=0)
    activo = models.BooleanField(default=True)

    creado = models.DateTimeField(auto_now_add=True)
    actualizado = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Miembro de equipo publicado'
        verbose_name_plural = 'Miembros de equipo publicados'
        ordering = ['orden', 'id']

    def __str__(self):
        return f'Publicado: {self.perfil.nombre_completo}'
