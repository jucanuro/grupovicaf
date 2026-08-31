import os

from django.core.exceptions import ValidationError
from django.db import models

from grupovicaf.seo import SeoModel


class Nosotros(SeoModel):
    """Contenido institucional de la página /nosotros/. Fila única (singleton).

    Portado de _ref/vicafpro/nosotros/models.py. Mejora sobre el original:
    hereda de SeoModel (slug/meta_title/meta_description/noindex/imagen_og,
    regla 11 de CLAUDE.md) y añade imagen_alt e imagen/creado/actualizado
    para accesibilidad y auditoría, ausentes en la versión anterior.
    """

    titulo = models.CharField(max_length=100)
    contenido = models.TextField()
    imagen = models.ImageField(upload_to='nosotros/', blank=True)
    imagen_alt = models.CharField(
        max_length=125, blank=True,
        help_text='Obligatorio si se sube imagen: describe la escena para accesibilidad y SEO.',
    )

    mision = models.TextField(blank=True)
    vision = models.TextField(blank=True)

    creado = models.DateTimeField(auto_now_add=True)
    actualizado = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Nosotros'
        verbose_name_plural = 'Nosotros'

    def __str__(self):
        return self.titulo

    def clean(self):
        super().clean()
        if self.imagen and not self.imagen_alt:
            raise ValidationError({'imagen_alt': 'Obligatorio cuando se sube una imagen.'})


class TipoDocumentoNosotros(SeoModel):
    """Categoría de documentos institucionales (p. ej. Certificados, Propuestas).

    Portado de _ref/vicafpro/nosotros/models.py. Mejora: el slug propio del
    original (max_length=120, unique) es redundante con SeoModel.slug, que ya
    cumple ese rol y se comparte con meta_title/meta_description/noindex/
    imagen_og — se retira el campo duplicado.
    """

    nombre = models.CharField(max_length=100, unique=True)
    descripcion = models.TextField(blank=True)
    orden = models.PositiveIntegerField(default=0)
    activo = models.BooleanField(default=True)

    creado = models.DateTimeField(auto_now_add=True)
    actualizado = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Tipo de documento'
        verbose_name_plural = 'Tipos de documento'
        ordering = ['orden', 'nombre']

    def __str__(self):
        return self.nombre


class DocumentoNosotros(models.Model):
    """Documento descargable (certificado, propuesta, etc.). Sin página propia:
    se muestra en modal/enlace directo desde /nosotros/, por lo que no hereda
    de SeoModel."""

    tipo = models.ForeignKey(
        TipoDocumentoNosotros, on_delete=models.PROTECT, related_name='documentos',
    )

    titulo = models.CharField(max_length=150)
    descripcion = models.TextField(blank=True)

    imagen = models.ImageField(
        upload_to='nosotros/documentos/imagenes/', blank=True,
        help_text='Imagen de portada o miniatura del documento.',
    )
    archivo = models.FileField(
        upload_to='nosotros/documentos/archivos/',
        help_text='Subir PDF, imagen, Word, Excel o PowerPoint.',
    )

    orden = models.PositiveIntegerField(default=0)
    activo = models.BooleanField(default=True)
    destacado = models.BooleanField(
        default=False,
        help_text='Marcar si deseas priorizar este documento entre los primeros visibles.',
    )

    fecha_publicacion = models.DateField(blank=True, null=True)
    creado = models.DateTimeField(auto_now_add=True)
    actualizado = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Documento de Nosotros'
        verbose_name_plural = 'Documentos de Nosotros'
        ordering = ['orden', '-destacado', '-creado']

    def __str__(self):
        return f'{self.tipo.nombre} - {self.titulo}'

    @property
    def extension_archivo(self):
        if not self.archivo:
            return ''
        return os.path.splitext(self.archivo.name)[1].lower()

    @property
    def es_imagen(self):
        return self.extension_archivo in ['.jpg', '.jpeg', '.png', '.webp', '.gif']

    @property
    def es_pdf(self):
        return self.extension_archivo == '.pdf'

    @property
    def es_office(self):
        return self.extension_archivo in ['.doc', '.docx', '.xls', '.xlsx', '.ppt', '.pptx']

    @property
    def es_certificado(self):
        nombre_tipo = self.tipo.nombre.lower() if self.tipo_id else ''
        return 'certificado' in nombre_tipo
