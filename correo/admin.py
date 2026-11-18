"""Correo en el admin de Django (solo laboratorio./admin/, regla 4).

La gestión diaria se hace en email.<dominio>/administrar/ (con bitácora). Aquí
queda la vista de respaldo para el superusuario; los mensajes no se exponen.
"""
from django.contrib import admin

from .models import AccesoCuenta, CuentaCorreo, EventoCuenta


class AccesoInline(admin.TabularInline):
    model = AccesoCuenta
    extra = 0
    autocomplete_fields = ['usuario']


@admin.register(CuentaCorreo)
class CuentaCorreoAdmin(admin.ModelAdmin):
    list_display = ['direccion', 'nombre', 'activa', 'creada_en']
    list_filter = ['activa']
    search_fields = ['direccion', 'nombre']
    prepopulated_fields = {'slug': ['nombre']}
    readonly_fields = ['creada_en']
    exclude = ['firma_predeterminada']
    inlines = [AccesoInline]


@admin.register(EventoCuenta)
class EventoCuentaAdmin(admin.ModelAdmin):
    list_display = ['creado_en', 'tipo', 'cuenta', 'usuario']
    list_filter = ['tipo']
    readonly_fields = ['creado_en', 'tipo', 'cuenta', 'usuario', 'detalle']

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
