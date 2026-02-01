from django.contrib import admin
from django.utils.html import format_html
from .models import Cliente

@admin.register(Cliente)
class ClienteAdmin(admin.ModelAdmin):
    list_display = ('mostrar_logo', 'codigo_confidencial', 'razon_social', 'ruc', 
                    'persona_contacto', 'activo', 'creado_en')
    
    list_display_links = ('mostrar_logo', 'codigo_confidencial', 'razon_social')
    
    list_filter = ('activo', 'creado_en', 'creado_por')
    
    search_fields = ('codigo_confidencial', 'razon_social', 'ruc', 'persona_contacto')
    
    fieldsets = (
        ('IDENTIFICACIÓN Y BRANDING', {
            'fields': (('logo_empresa', 'mostrar_logo_detalle'), 'codigo_confidencial', 'razon_social', 'ruc', 'activo'),
            'description': 'Datos de identidad corporativa y anonimato.'
        }),
        ('DATOS FISCALES Y WEB', {
            'fields': ('direccion', 'sitio_web'),
            'classes': ('collapse',), 
        }),
        ('CONTACTO Y VALIDACIÓN', {
            'fields': ('persona_contacto', 'cargo_contacto', 'celular_contacto', 'correo_contacto', 'firma_electronica'),
        }),
        ('AUDITORÍA', {
            'fields': (('creado_por', 'creado_en'), 'actualizado_en'),
            'classes': ('collapse',),
        }),
    )

    readonly_fields = ('codigo_confidencial', 'creado_en', 'actualizado_en', 'creado_por', 'mostrar_logo_detalle')
    def mostrar_logo(self, obj):
        """Muestra una miniatura redonda en la lista principal"""
        if obj.logo_empresa:
            return format_html('<img src="{}" style="width: 35px; height: 35px; border-radius: 50%; object-fit: cover; border: 1px solid #ddd;" />', obj.logo_empresa.url)
        return format_html('<span style="color: #ccc;">No logo</span>')
    mostrar_logo.short_description = 'Logo'

    def mostrar_logo_detalle(self, obj):
        """Muestra el logo en grande dentro del formulario de edición"""
        if obj.logo_empresa:
            return format_html('<img src="{}" style="max-height: 150px; border-radius: 8px; box-shadow: 0 4px 6px -1px rgba(0,0,0,0.1);" />', obj.logo_empresa.url)
        return "No hay logo cargado aún."
    mostrar_logo_detalle.short_description = 'Previsualización del Logo'

    def save_model(self, request, obj, form, change):
        if not change:
            obj.creado_por = request.user
        super().save_model(request, obj, form, change)