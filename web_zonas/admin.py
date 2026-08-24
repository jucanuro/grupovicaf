from django.contrib import admin
from django.utils.html import format_html

from .models import ZonaCobertura


def aviso_contenido(obj):
    if 'PENDIENTE DE REDACCIÓN' in obj.contenido:
        return format_html('<span style="color:#b91c1c;font-weight:600;">Pendiente ⚠️</span>')
    return format_html('<span style="color:#15803d;">Redactado</span>')
aviso_contenido.short_description = 'Contenido'


@admin.register(ZonaCobertura)
class ZonaCoberturaAdmin(admin.ModelAdmin):
    list_display = (
        'nombre', 'provincia', 'es_sede', 'activo', 'orden', aviso_contenido, 'noindex', 'actualizado',
    )
    list_editable = ('es_sede', 'activo', 'orden')
    list_filter = ('activo', 'es_sede', 'departamento')
    search_fields = ('nombre', 'provincia')
    ordering = ('-es_sede', 'orden', 'nombre')
    prepopulated_fields = {'slug': ('nombre',)}
    filter_horizontal = ('servicios',)
    readonly_fields = ('creado', 'actualizado')

    fieldsets = (
        ('Ubicación', {'fields': ('nombre', 'provincia', 'departamento', 'latitud', 'longitud', 'es_sede')}),
        ('Contenido', {'fields': ('titulo_h1', 'introduccion', 'contenido', 'servicios')}),
        ('SEO', {'fields': ('slug', 'meta_title', 'meta_description', 'noindex', 'imagen_og')}),
        ('Configuración', {'fields': ('activo', 'orden')}),
        ('Auditoría', {'fields': ('creado', 'actualizado'), 'classes': ('collapse',)}),
    )
