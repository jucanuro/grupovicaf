from django.contrib import admin
from django.utils.html import format_html

from .models import CarruselInicio


@admin.register(CarruselInicio)
class CarruselInicioAdmin(admin.ModelAdmin):
    list_display = (
        'miniatura',
        'titulo',
        'activo',
        'orden',
        'fecha_inicio',
        'fecha_fin',
    )
    list_editable = ('orden', 'activo')
    list_filter = ('activo',)
    search_fields = ('titulo', 'descripcion')
    ordering = ('orden', '-creado')
    readonly_fields = ('creado', 'actualizado', 'vista_previa')

    fieldsets = (
        ('Contenido', {
            'fields': ('titulo', 'descripcion', 'imagen', 'vista_previa', 'alt_text', 'enlace'),
        }),
        ('Programación', {
            'fields': ('activo', 'orden', 'fecha_inicio', 'fecha_fin'),
        }),
        ('Auditoría', {
            'fields': ('creado', 'actualizado'),
            'classes': ('collapse',),
        }),
    )

    @admin.display(description='Imagen')
    def miniatura(self, obj):
        if not obj.imagen:
            return '—'
        return format_html(
            '<img src="{}" style="height:40px;width:auto;border-radius:4px;">', obj.imagen.url
        )

    @admin.display(description='Vista previa')
    def vista_previa(self, obj):
        if not obj.imagen:
            return 'Sin imagen.'
        return format_html(
            '<img src="{}" style="max-height:200px;width:auto;border-radius:8px;">', obj.imagen.url
        )
