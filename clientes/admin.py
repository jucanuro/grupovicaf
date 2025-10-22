from django.contrib import admin
from .models import Cliente

@admin.register(Cliente)
class ClienteAdmin(admin.ModelAdmin):
    # Campos que se muestran en el listado
    list_display = ('razon_social', 'ruc', 'persona_contacto', 'celular_contacto', 'activo', 'creado_por', 'creado_en')
    
    # Campos por los que se puede filtrar
    list_filter = ('activo', 'creado_en', 'creado_por')
    
    # Campos por los que se puede buscar (permite buscar por RUC y Razón Social)
    search_fields = ('razon_social', 'ruc', 'persona_contacto', 'correo_contacto')
    
    # Estructura del formulario de edición/creación
    fieldsets = (
        ('INFORMACIÓN PRINCIPAL DEL CLIENTE', {
            'fields': ('razon_social', 'ruc', 'direccion', 'sitio_web', 'activo')
        }),
        ('DATOS DE CONTACTO PRINCIPAL', {
            'fields': ('persona_contacto', 'cargo_contacto', 'celular_contacto', 'correo_contacto', 'firma_electronica')
        }),
        ('AUDITORÍA DEL SISTEMA', {
            # Los campos auto_now_add/auto_now son de solo lectura
            'fields': ('creado_por', 'creado_en', 'actualizado_en'),
            'classes': ('collapse',), # Ocultar por defecto para mantener limpio
        }),
    )

    # Campos de solo lectura para auditoría
    readonly_fields = ('creado_en', 'actualizado_en', 'creado_por')

    def save_model(self, request, obj, form, change):
        """
        Sobreescribe el método save_model para asegurar que 'creado_por'
        se establezca automáticamente al usuario logeado solo en la creación.
        """
        if not change:
            obj.creado_por = request.user
        super().save_model(request, obj, form, change)
