from django.contrib import admin
from django.utils.html import format_html

from .models import (
    ClienteDestacado, ImagenLinea, LineaServicio, MiembroEquipoPublicado, PreguntaFrecuente, ServicioPublicado,
)


def aviso_meta_description(obj):
    if not obj.meta_description:
        return format_html('<span style="color:#b91c1c;font-weight:600;">Sin meta_description ⚠️</span>')
    return format_html('<span style="color:#15803d;">OK ({} car.)</span>', len(obj.meta_description))
aviso_meta_description.short_description = 'SEO'


def aviso_contenido(obj):
    if 'PENDIENTE DE REDACCIÓN' in obj.contenido:
        return format_html('<span style="color:#b91c1c;font-weight:600;">Pendiente ⚠️</span>')
    return format_html('<span style="color:#15803d;">Redactado</span>')
aviso_contenido.short_description = 'Contenido'


class PreguntaFrecuenteInline(admin.TabularInline):
    model = PreguntaFrecuente
    extra = 1
    fields = ('pregunta', 'respuesta', 'orden', 'activo')


class ImagenLineaInline(admin.TabularInline):
    model = ImagenLinea
    extra = 1
    fields = ('imagen', 'vista_previa', 'alt_text', 'orden', 'activo')
    readonly_fields = ('vista_previa',)

    @admin.display(description='Vista previa')
    def vista_previa(self, obj):
        if not obj.pk or not obj.imagen:
            return 'Sin imagen.'
        return format_html('<img src="{}" style="max-height:80px;width:auto;border-radius:6px;">', obj.imagen.url)


@admin.register(LineaServicio)
class LineaServicioAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'destacado', 'activo', 'orden', aviso_contenido, 'noindex', 'actualizado')
    list_editable = ('destacado', 'activo', 'orden')
    list_filter = ('activo', 'destacado')
    search_fields = ('nombre', 'resumen')
    ordering = ('orden', 'nombre')
    prepopulated_fields = {'slug': ('nombre',)}
    filter_horizontal = ('ensayos',)
    readonly_fields = ('creado', 'actualizado', 'vista_previa')
    inlines = [ImagenLineaInline]

    fieldsets = (
        ('Contenido', {
            'fields': ('nombre', 'titulo_h1', 'resumen', 'contenido', 'icono', 'imagen', 'vista_previa', 'imagen_alt'),
        }),
        ('Ensayos del LIMS', {'fields': ('ensayos',)}),
        ('SEO', {'fields': ('slug', 'meta_title', 'meta_description', 'noindex', 'imagen_og')}),
        ('Configuración', {'fields': ('destacado', 'activo', 'orden')}),
        ('Auditoría', {'fields': ('creado', 'actualizado'), 'classes': ('collapse',)}),
    )

    @admin.display(description='Vista previa')
    def vista_previa(self, obj):
        if not obj.imagen:
            return 'Sin imagen.'
        return format_html('<img src="{}" style="max-height:200px;width:auto;border-radius:8px;">', obj.imagen.url)


@admin.register(ServicioPublicado)
class ServicioPublicadoAdmin(admin.ModelAdmin):
    list_display = (
        'titulo_publico', 'servicio', 'linea', 'categoria', 'subcategoria',
        'destacado', 'activo', 'orden', aviso_meta_description, 'actualizado',
    )
    list_editable = ('destacado', 'activo', 'orden')
    list_filter = ('activo', 'destacado', 'categoria', 'subcategoria', 'linea')
    search_fields = ('titulo_publico', 'resumen', 'servicio__nombre', 'servicio__codigo_facturacion')
    ordering = ('categoria__nombre', 'subcategoria__nombre', 'orden')
    prepopulated_fields = {'slug': ('titulo_publico',)}
    autocomplete_fields = ('servicio', 'categoria', 'subcategoria', 'linea')
    readonly_fields = ('creado', 'actualizado', 'vista_previa')
    inlines = [PreguntaFrecuenteInline]

    fieldsets = (
        ('Vínculo con el LIMS', {'fields': ('servicio', 'categoria', 'subcategoria', 'linea')}),
        ('Contenido', {
            'fields': ('titulo_publico', 'resumen', 'contenido', 'zona_principal', 'imagen', 'vista_previa', 'imagen_alt'),
        }),
        ('SEO', {'fields': ('slug', 'meta_title', 'meta_description', 'noindex', 'imagen_og')}),
        ('Configuración', {'fields': ('destacado', 'activo', 'orden')}),
        ('Auditoría', {'fields': ('creado', 'actualizado'), 'classes': ('collapse',)}),
    )

    @admin.display(description='Vista previa')
    def vista_previa(self, obj):
        if not obj.imagen:
            return 'Sin imagen.'
        return format_html('<img src="{}" style="max-height:200px;width:auto;border-radius:8px;">', obj.imagen.url)


@admin.register(ClienteDestacado)
class ClienteDestacadoAdmin(admin.ModelAdmin):
    list_display = ('cliente', 'mostrar_logo', 'activo', 'orden', 'actualizado')
    list_editable = ('mostrar_logo', 'activo', 'orden')
    list_filter = ('activo', 'mostrar_logo')
    search_fields = ('cliente__razon_social',)
    ordering = ('orden', 'id')
    autocomplete_fields = ('cliente',)
    readonly_fields = ('creado', 'actualizado')


@admin.register(MiembroEquipoPublicado)
class MiembroEquipoPublicadoAdmin(admin.ModelAdmin):
    list_display = ('perfil', 'mostrar_correo', 'activo', 'orden', 'actualizado')
    list_editable = ('mostrar_correo', 'activo', 'orden')
    list_filter = ('activo', 'mostrar_correo', 'perfil__rol')
    search_fields = ('perfil__nombre_completo',)
    ordering = ('orden', 'id')
    autocomplete_fields = ('perfil',)
    readonly_fields = ('creado', 'actualizado')
