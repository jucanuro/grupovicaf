from django.contrib import admin
from django.utils.html import format_html
from .models import Proyecto, RecepcionMuestraLote, MuestraItem

# --- INLINES ---

class MuestraItemInline(admin.TabularInline):
    """Líneas de muestras con diseño compacto estilo Excel"""
    model = MuestraItem
    extra = 1
    classes = ['collapse'] # Permite esconder/mostrar para limpieza visual
    fields = (
        'servicio', 'cantidad', 'unidad', 
        'descripcion', 'masa_aproximada', 
        'codigo_vicaf', 'es_adicional'
    )
    readonly_fields = ('codigo_vicaf',)
    # Autocomplete requiere search_fields en el destino (ver paso 1)
    autocomplete_fields = ['servicio', 'categoria', 'subcategoria']

class RecepcionMuestraLoteInline(admin.TabularInline):
    """Muestra un resumen de recepciones dentro del Proyecto"""
    model = RecepcionMuestraLote
    extra = 0
    fields = ('numero_registro', 'fecha_recepcion', 'responsable_entrega')
    readonly_fields = fields
    show_change_link = True
    can_delete = False

# --- CONFIGURACIONES PRINCIPALES ---

@admin.register(Proyecto)
class ProyectoAdmin(admin.ModelAdmin):
    list_display = ('id_display', 'nombre_proyecto', 'cliente_link', 'status_badge', 'muestras_count')
    list_filter = ('estado', 'creado_en')
    search_fields = ('codigo_proyecto', 'nombre_proyecto', 'cliente__razon_social')
    raw_id_fields = ('cliente', 'cotizacion')
    inlines = [RecepcionMuestraLoteInline]
    
    # Estética: Badge de colores para el estado
    def status_badge(self, obj):
        colors = {
            'PENDIENTE': '#64748b',
            'EN_CURSO': '#0284c7',
            'FINALIZADO': '#16a34a',
            'CANCELADO': '#dc2626',
        }
        return format_html(
            '<span style="background: {}; color: white; padding: 3px 10px; border-radius: 12px; font-size: 10px; font-weight: bold;">{}</span>',
            colors.get(obj.estado, '#000'), obj.get_estado_display()
        )
    status_badge.short_description = "Estado"

    def id_display(self, obj):
        return obj.codigo_proyecto
    id_display.short_description = "Código"

    def cliente_link(self, obj):
        return obj.cliente.razon_social
    cliente_link.short_description = "Cliente"

    def muestras_count(self, obj):
        return obj.muestras_registradas_reales
    muestras_count.short_description = "Muestras"

@admin.register(RecepcionMuestraLote)
class RecepcionMuestraLoteAdmin(admin.ModelAdmin):
    list_display = ('numero_registro', 'proyecto', 'fecha_recepcion', 'recepcionado_por')
    list_filter = ('fecha_recepcion', 'recepcionado_por')
    search_fields = ('numero_registro', 'proyecto__nombre_proyecto', 'responsable_entrega')
    raw_id_fields = ('proyecto', 'recepcionado_por')
    inlines = [MuestraItemInline]
    
    fieldsets = (
        ('Identificación del Lote (VCF-LAB-FOR-022)', {
            'fields': (('numero_registro', 'proyecto'),)
        }),
        ('Información del Cliente', {
            'fields': (('responsable_entrega', 'telefono_entrega'),)
        }),
        ('Información de Recepción', {
            'fields': (('fecha_recepcion', 'hora_recepcion'), ('fecha_muestreo', 'recepcionado_por'))
        }),
    )

@admin.register(MuestraItem)
class MuestraItemAdmin(admin.ModelAdmin):
    list_display = ('codigo_vicaf', 'lote_link', 'servicio', 'cantidad', 'es_adicional_icon')
    list_filter = ('es_adicional', 'unidad')
    search_fields = ('codigo_vicaf', 'descripcion', 'codigo_cliente')
    autocomplete_fields = ['servicio', 'categoria', 'subcategoria']

    def lote_link(self, obj):
        return obj.lote.numero_registro
    lote_link.short_description = "Registro Lote"

    def es_adicional_icon(self, obj):
        return format_html('<b style="color:red;">SÍ</b>' if obj.es_adicional else 'No')
    es_adicional_icon.short_description = "Adicional"