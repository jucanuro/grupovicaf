from django.contrib import admin
from django.utils.html import format_html

from .models import Acreditacion


@admin.register(Acreditacion)
class AcreditacionAdmin(admin.ModelAdmin):
    list_display = (
        'organismo', 'numero_acreditacion', 'vigencia_hasta', 'vigente_display',
        'activo', 'orden',
    )
    list_editable = ('activo', 'orden')
    list_filter = ('activo', 'organismo')
    search_fields = ('organismo', 'numero_acreditacion', 'alcance')
    ordering = ('orden', '-vigencia_desde')
    readonly_fields = ('creado', 'actualizado', 'vista_previa_logo')
    filter_horizontal = ('servicios_acreditados',)

    fieldsets = (
        ('Datos de la acreditación', {
            'fields': ('organismo', 'numero_acreditacion', 'alcance', 'vigencia_desde', 'vigencia_hasta'),
        }),
        ('Archivos', {
            'fields': ('documento', 'logo', 'vista_previa_logo', 'logo_alt'),
        }),
        ('Ensayos acreditados', {
            'fields': ('servicios_acreditados',),
        }),
        ('Configuración', {
            'fields': ('activo', 'orden'),
        }),
        ('Auditoría', {
            'fields': ('creado', 'actualizado'),
            'classes': ('collapse',),
        }),
    )

    @admin.display(description='Vigente', boolean=True)
    def vigente_display(self, obj):
        return obj.vigente

    @admin.display(description='Vista previa del logo')
    def vista_previa_logo(self, obj):
        if not obj.logo:
            return 'Sin logo.'
        return format_html('<img src="{}" style="max-height:120px;width:auto;border-radius:8px;">', obj.logo.url)
