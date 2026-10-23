from django.contrib import admin

from .models import NegocioConfig


@admin.register(NegocioConfig)
class NegocioConfigAdmin(admin.ModelAdmin):
    fieldsets = (
        (None, {'fields': ('nombre', 'ruc', 'descripcion')}),
        ('Dirección', {'fields': (
            'direccion_calle', 'direccion_localidad', 'direccion_region',
            'direccion_codigo_postal', 'direccion_pais', 'latitud', 'longitud',
        )}),
        ('Contacto', {'fields': ('telefono', 'whatsapp', 'correo')}),
        ('Horario', {'fields': (
            'horario_semana_apertura', 'horario_semana_cierre',
            'horario_sabado_apertura', 'horario_sabado_cierre',
        )}),
        ('Cobertura', {'fields': ('ciudades_cobertura',)}),
        ('Acreditación', {'fields': (
            'acreditacion_entidad', 'acreditacion_codigo', 'ensayos_acreditados',
        )}),
        ('Redes sociales', {'fields': ('linkedin_url', 'facebook_url', 'instagram_url')}),
    )

    def has_add_permission(self, request):
        return not NegocioConfig.objects.exists()

    def has_delete_permission(self, request, obj=None):
        return False
