from django.contrib import admin

from .models import CalendarioCategoria, CalendarioMiembro


class CalendarioMiembroInline(admin.TabularInline):
    model = CalendarioMiembro
    extra = 1
    autocomplete_fields = ['user']


@admin.register(CalendarioCategoria)
class CalendarioAdmin(admin.ModelAdmin):
    """Calendarios de equipo (con sus miembros) y personales.

    Un calendario de equipo sin miembros lo ven todos; al agregar miembros solo
    lo ven ellos y crean eventos los que tienen «Puede crear eventos»."""
    list_display = ['nombre', 'tipo', 'propietario', 'color', 'activo']
    list_filter = ['tipo', 'activo']
    search_fields = ['nombre']
    inlines = [CalendarioMiembroInline]
    autocomplete_fields = ['propietario']
