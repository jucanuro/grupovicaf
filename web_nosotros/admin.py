from django.contrib import admin
from django.utils.html import format_html

from .models import DocumentoNosotros, Nosotros, TipoDocumentoNosotros


def aviso_meta_description(obj):
    if not obj.meta_description:
        return format_html('<span style="color:#b91c1c;font-weight:600;">Sin meta_description ⚠️</span>')
    return format_html('<span style="color:#15803d;">OK ({} car.)</span>', len(obj.meta_description))
aviso_meta_description.short_description = 'SEO'


@admin.register(Nosotros)
class NosotrosAdmin(admin.ModelAdmin):
    list_display = ('titulo', 'slug', aviso_meta_description, 'actualizado')
    search_fields = ('titulo', 'contenido')
    prepopulated_fields = {'slug': ('titulo',)}
    readonly_fields = ('creado', 'actualizado', 'vista_previa')

    fieldsets = (
        ('Contenido', {'fields': ('titulo', 'contenido', 'imagen', 'vista_previa', 'imagen_alt')}),
        ('Misión y visión', {'fields': ('mision', 'vision')}),
        ('SEO', {'fields': ('slug', 'meta_title', 'meta_description', 'noindex', 'imagen_og')}),
        ('Auditoría', {'fields': ('creado', 'actualizado'), 'classes': ('collapse',)}),
    )

    def has_add_permission(self, request):
        # Fila única: la página /nosotros/ lee siempre el primer registro.
        return not Nosotros.objects.exists()

    @admin.display(description='Vista previa')
    def vista_previa(self, obj):
        if not obj.imagen:
            return 'Sin imagen.'
        return format_html('<img src="{}" style="max-height:200px;width:auto;border-radius:8px;">', obj.imagen.url)


@admin.register(TipoDocumentoNosotros)
class TipoDocumentoNosotrosAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'slug', 'activo', 'orden', aviso_meta_description, 'actualizado')
    list_editable = ('activo', 'orden')
    list_filter = ('activo',)
    search_fields = ('nombre', 'slug', 'descripcion')
    prepopulated_fields = {'slug': ('nombre',)}
    ordering = ('orden', 'nombre')
    readonly_fields = ('creado', 'actualizado')

    fieldsets = (
        ('Información del tipo', {'fields': ('nombre', 'descripcion')}),
        ('Configuración', {'fields': ('activo', 'orden')}),
        ('SEO', {'fields': ('slug', 'meta_title', 'meta_description', 'noindex', 'imagen_og')}),
        ('Auditoría', {'fields': ('creado', 'actualizado'), 'classes': ('collapse',)}),
    )


@admin.register(DocumentoNosotros)
class DocumentoNosotrosAdmin(admin.ModelAdmin):
    list_display = ('titulo', 'tipo', 'miniatura', 'activo', 'destacado', 'orden', 'fecha_publicacion', 'actualizado')
    list_filter = ('tipo', 'activo', 'destacado', 'fecha_publicacion')
    search_fields = ('titulo', 'descripcion', 'tipo__nombre')
    list_editable = ('activo', 'destacado', 'orden')
    list_select_related = ('tipo',)
    ordering = ('orden', '-destacado', '-creado')
    readonly_fields = ('creado', 'actualizado')
    autocomplete_fields = ('tipo',)
    date_hierarchy = 'fecha_publicacion'

    fieldsets = (
        ('Información principal', {'fields': ('tipo', 'titulo', 'descripcion')}),
        ('Archivos del documento', {'fields': ('imagen', 'archivo')}),
        ('Configuración de visualización', {'fields': ('activo', 'destacado', 'orden', 'fecha_publicacion')}),
        ('Auditoría', {'fields': ('creado', 'actualizado'), 'classes': ('collapse',)}),
    )

    @admin.display(description='Imagen')
    def miniatura(self, obj):
        if not obj.imagen:
            return '—'
        return format_html('<img src="{}" style="height:40px;width:auto;border-radius:4px;">', obj.imagen.url)
