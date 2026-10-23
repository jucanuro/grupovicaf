from django.contrib import admin
from django.utils.html import format_html

from .models import Acreditacion, Certificacion


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


@admin.register(Certificacion)
class CertificacionAdmin(admin.ModelAdmin):
    list_display = (
        'titulo', 'tipo', 'institucion', 'vigencia_hasta', 'publicada_display', 'activo', 'orden',
    )
    list_editable = ('activo', 'orden')
    list_filter = ('tipo', 'activo')
    search_fields = ('titulo', 'descripcion', 'institucion')
    ordering = ('orden', 'titulo')
    readonly_fields = ('creado', 'actualizado', 'vista_previa_logo', 'vista_previa_archivo')

    fieldsets = (
        ('Card', {
            'fields': ('titulo', 'descripcion', 'tipo', 'institucion', 'logo', 'vista_previa_logo'),
        }),
        ('Documento', {
            'description': 'La certificación solo se muestra en la web si está activa, '
                           'tiene archivo y su vigencia (si tiene) no ha pasado.',
            'fields': ('archivo', 'vista_previa_archivo', 'vigencia_hasta'),
        }),
        ('Configuración', {
            'fields': ('activo', 'orden'),
        }),
        ('Auditoría', {
            'fields': ('creado', 'actualizado'),
            'classes': ('collapse',),
        }),
    )

    @admin.display(description='Publicada en la web', boolean=True)
    def publicada_display(self, obj):
        return obj.publicada

    @admin.display(description='Vista previa del logo')
    def vista_previa_logo(self, obj):
        if not obj.logo:
            return 'Sin logo: la card muestra un sello genérico.'
        return format_html(
            '<img src="{}" alt="" style="max-height:96px;width:auto;padding:8px;background:#f8fafc;border-radius:8px;">',
            obj.logo.url,
        )

    @admin.display(description='Vista previa')
    def vista_previa_archivo(self, obj):
        if not obj.archivo:
            return 'Sin archivo: no se muestra en la web.'
        if obj.es_pdf:
            return format_html('<a href="{}" target="_blank" rel="noopener">Abrir PDF</a>', obj.archivo.url)
        return format_html('<img src="{}" style="max-height:160px;width:auto;border-radius:8px;">', obj.archivo.url)
