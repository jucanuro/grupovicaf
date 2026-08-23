from django.core.exceptions import ValidationError
from django.db import models


def validar_meta_title(value):
    if len(value) > 60:
        raise ValidationError(
            f"meta_title tiene {len(value)} caracteres; Google trunca a partir de 60."
        )


def validar_meta_description(value):
    if len(value) > 160:
        raise ValidationError(
            f"meta_description tiene {len(value)} caracteres; Google trunca a partir de 160."
        )


class SeoModel(models.Model):
    """Campos SEO comunes a todo modelo con página propia en el sitio público."""

    slug = models.SlugField(unique=True)
    meta_title = models.CharField(
        max_length=60, blank=True, validators=[validar_meta_title],
        help_text="Si se deja en blanco, se usa el título natural de la página.",
    )
    meta_description = models.CharField(
        max_length=160, blank=True, validators=[validar_meta_description],
    )
    noindex = models.BooleanField(default=False)
    imagen_og = models.ImageField(upload_to='seo/og/', blank=True)

    class Meta:
        abstract = True
