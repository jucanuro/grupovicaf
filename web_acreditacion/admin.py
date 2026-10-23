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
        'norma', 'numero_certificado', 'organismo', 'vigencia_hasta', 'publicada_display',
        'activo', 'orden',
    )
    list_editable = ('activo', 'orden')
    list_filter = ('activo', 'organismo')
    search_fields = ('norma', 'numero_certificado', 'organismo', 'alcance')
    ordering = ('orden', '-vigencia_hasta')
    readonly_fields = ('creado', 'actualizado', 'vista_previa_sello')

    fieldsets = (
        ('Datos del certificado', {
            'fields': (
                'norma', 'sistema', 'numero_certificado', 'organismo', 'alcance', 'sede',
                'fecha_emision', 'vigencia_hasta',
            ),
        }),
        ('Archivos', {
            'description': 'La certificación solo se muestra en la web si está activa, '
                           'tiene PDF y su vigencia no ha pasado.',
            'fields': ('archivo', 'sello', 'vista_previa_sello', 'sello_alt'),
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

    @admin.display(description='Vista previa del sello')
    def vista_previa_sello(self, obj):
        if not obj.sello:
            return 'Sin sello: la web muestra un distintivo de texto con la norma.'
        return format_html('<img src="{}" style="max-height:120px;width:auto;border-radius:8px;">', obj.sello.url)
