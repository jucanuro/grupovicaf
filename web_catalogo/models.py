from io import BytesIO
from pathlib import Path

from django.core.exceptions import ValidationError
from django.core.files.base import ContentFile
from django.db import models
from PIL import Image

from grupovicaf.seo import SeoModel

# Ancho de la miniatura de galería: "8 miniaturas visibles" del encargo debe
# significar peso liviano, no solo tamaño en pantalla. Sin esto, cada
# miniatura servía el archivo de 1600px del lightbox (~150-300 KB c/u) nada
# más que reescalado por CSS — regla 17 de CLAUDE.md, rendimiento es ranking.
ANCHO_MINIATURA = 480
CALIDAD_MINIATURA = 70


class LineaServicioQuerySet(models.QuerySet):
    def publicadas(self):
        return self.filter(activo=True)


class LineaServicio(SeoModel):
    """Línea comercial (ej. "Mecánica de Suelos") que agrupa ensayos del LIMS.

    Vive en /servicios/<slug>/, el mismo prefijo que ServicioPublicado: la
    página de línea enlaza a sus ensayos individuales (/servicios/ensayo-cbr/)
    y viceversa vía ServicioPublicado.linea. servicios_list_view resuelve el
    slug probando primero LineaServicio y luego ServicioPublicado (ver
    docstring de servicio_detalle_view en views.py).

    ensayos apunta directo a servicios.Servicio (no a ServicioPublicado):
    una línea agrupa el catálogo interno completo, tenga o no cada ensayo
    su propia página pública todavía.
    """

    nombre = models.CharField(max_length=100, help_text='Ej: "Mecánica de Suelos".')
    titulo_h1 = models.CharField(
        max_length=150,
        help_text='H1 de la página. Ej: "Mecánica de suelos y estudios geotécnicos en Cajamarca".',
    )
    resumen = models.CharField(max_length=300, help_text='Una o dos líneas, para la tarjeta del índice.')
    contenido = models.TextField(
        help_text='Texto comercial de la página de línea. Redacción única (ver CLAUDE.md regla 16).',
    )
    imagen = models.ImageField(upload_to='catalogo/lineas/', blank=True)
    imagen_alt = models.CharField(
        max_length=125, blank=True,
        help_text='Obligatorio si se sube imagen: describe la escena para accesibilidad y SEO.',
    )
    icono = models.CharField(
        max_length=50, blank=True,
        help_text='Nombre de ícono opcional para la tarjeta del índice (uso libre en la plantilla).',
    )

    ensayos = models.ManyToManyField(
        'servicios.Servicio', blank=True, related_name='lineas_servicio',
        help_text='Ensayos del LIMS que agrupa esta línea comercial.',
    )

    destacado = models.BooleanField(default=False)
    orden = models.PositiveIntegerField(default=0)
    activo = models.BooleanField(default=True)

    creado = models.DateTimeField(auto_now_add=True)
    actualizado = models.DateTimeField(auto_now=True)

    objects = LineaServicioQuerySet.as_manager()

    class Meta:
        verbose_name = 'Línea de servicio'
        verbose_name_plural = 'Líneas de servicio'
        ordering = ['orden', 'nombre']

    def __str__(self):
        return self.nombre

    def clean(self):
        super().clean()
        if self.imagen and not self.imagen_alt:
            raise ValidationError({'imagen_alt': 'Obligatorio cuando se sube una imagen.'})


class ImagenLineaQuerySet(models.QuerySet):
    def publicadas(self):
        return self.filter(activo=True)


class ImagenLinea(models.Model):
    """Foto de la galería "Así trabajamos" de una LineaServicio.

    alt_text es obligatorio (blank=False): sin descripción no hay forma de
    cumplir accesibilidad ni SEO de imagen, así que el admin no deja
    guardar la fila sin él (ver ImagenLineaInline en admin.py).
    """

    linea = models.ForeignKey(LineaServicio, on_delete=models.CASCADE, related_name='galeria')
    imagen = models.ImageField(
        upload_to='catalogo/lineas/galeria/', width_field='ancho', height_field='alto',
        help_text='Foto completa: se usa en el lightbox al ampliar.',
    )
    imagen_miniatura = models.ImageField(
        upload_to='catalogo/lineas/galeria/miniaturas/',
        width_field='ancho_miniatura', height_field='alto_miniatura',
        editable=False, blank=True,
        help_text='Se genera sola a partir de "imagen" al guardar (ver save()).',
    )
    # Cacheados en columnas propias (width_field/height_field arriba) para no
    # abrir cada archivo con Pillow al pintar la plantilla: una línea puede
    # traer varias decenas de fotos (ver 0005_infohtml_y_galeria_lineas).
    ancho = models.PositiveIntegerField(default=0, editable=False)
    alto = models.PositiveIntegerField(default=0, editable=False)
    ancho_miniatura = models.PositiveIntegerField(default=0, editable=False)
    alto_miniatura = models.PositiveIntegerField(default=0, editable=False)
    alt_text = models.CharField(
        max_length=125,
        help_text='Obligatorio: describe la escena para accesibilidad y SEO.',
    )
    orden = models.PositiveIntegerField(default=0)
    activo = models.BooleanField(default=True)
    creado = models.DateTimeField(auto_now_add=True)

    objects = ImagenLineaQuerySet.as_manager()

    class Meta:
        verbose_name = 'Imagen de línea'
        verbose_name_plural = 'Imágenes de línea'
        ordering = ['orden', 'id']

    def __str__(self):
        return f'{self.linea.nombre} — {self.alt_text}'

    def save(self, *args, **kwargs):
        if self.imagen and not self.imagen_miniatura:
            self.imagen.open('rb')
            with Image.open(self.imagen) as fuente:
                miniatura = fuente.convert('RGB')
                if miniatura.width > ANCHO_MINIATURA:
                    alto = round(miniatura.height * ANCHO_MINIATURA / miniatura.width)
                    miniatura = miniatura.resize((ANCHO_MINIATURA, alto), Image.LANCZOS)
                buffer = BytesIO()
                miniatura.save(buffer, format='WEBP', quality=CALIDAD_MINIATURA)
            self.imagen.seek(0)
            nombre = f'{Path(self.imagen.name).stem}_mini.webp'
            self.imagen_miniatura.save(nombre, ContentFile(buffer.getvalue()), save=False)
        super().save(*args, **kwargs)


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
    linea = models.ForeignKey(
        'LineaServicio', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='ensayos_publicados',
        help_text='Línea comercial a la que pertenece este ensayo (ej. "Mecánica de Suelos"). Opcional.',
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
        help_text='Ciudad usada en el H1 ("Ensayo CBR en Cajamarca").',
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
