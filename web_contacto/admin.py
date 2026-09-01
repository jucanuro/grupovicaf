from django.contrib import admin

from .models import MensajeContacto, SolicitudCotizacionItem, SolicitudCotizacionWeb


@admin.register(MensajeContacto)
class MensajeContactoAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'correo', 'asunto', 'origen', 'estado', 'atendido_por', 'creado')
    list_filter = ('estado', 'creado')
    search_fields = ('nombre', 'correo', 'asunto', 'mensaje')
    readonly_fields = ('nombre', 'correo', 'telefono', 'asunto', 'mensaje', 'origen', 'ip', 'creado')
    autocomplete_fields = ('atendido_por',)
    ordering = ('-creado',)

    fieldsets = (
        ('Mensaje', {'fields': ('nombre', 'correo', 'telefono', 'asunto', 'mensaje')}),
        ('Origen', {'fields': ('origen', 'ip', 'creado')}),
        ('Atención', {'fields': ('estado', 'atendido_por', 'fecha_atencion')}),
    )


class SolicitudCotizacionItemInline(admin.TabularInline):
    model = SolicitudCotizacionItem
    extra = 0
    readonly_fields = ('servicio_publicado', 'cantidad_estimada')
    can_delete = False


@admin.register(SolicitudCotizacionWeb)
class SolicitudCotizacionWebAdmin(admin.ModelAdmin):
    list_display = (
        'razon_social', 'ruc', 'cliente', 'cotizacion', 'origen', 'creado',
    )
    list_filter = ('creado',)
    search_fields = ('razon_social', 'ruc', 'correo_contacto', 'cotizacion__numero_oferta')
    readonly_fields = (
        'ruc', 'razon_social', 'persona_contacto', 'correo_contacto', 'telefono_contacto',
        'necesidad', 'origen', 'ip', 'cliente', 'cotizacion', 'creado',
    )
    autocomplete_fields = ('cliente',)
    inlines = [SolicitudCotizacionItemInline]
    ordering = ('-creado',)

    def has_add_permission(self, request):
        return False
