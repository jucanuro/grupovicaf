from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from .models import Proyecto, TipoMuestra, RecepcionMuestra, MuestraDetalle

class MuestraDetalleInline(admin.TabularInline):
    model = MuestraDetalle
    extra = 1
    # El código se genera en el save(), así que lo protegemos aquí
    readonly_fields = ('codigo_laboratorio',)
    fields = ('tipo_muestra', 'codigo_laboratorio', 'descripcion', 'masa_aprox', 'cantidad', 'unidad')


@admin.register(RecepcionMuestra)
class RecepcionMuestraAdmin(admin.ModelAdmin):
    # 1. Agregamos el método del cliente a readonly para que aparezca en el formulario
    readonly_fields = ('get_cliente_display',)

    # Organizado por secciones para mayor orden
    fieldsets = (
        ('Origen y Cotización', {
            'fields': ('cotizacion', 'get_cliente_display', 'responsable_recepcion')
        }),
        ('Información del Cliente (En Muestreo)', {
            'fields': ('procedencia', 'responsable_cliente', 'telefono'),
            'description': 'Datos proporcionados al momento de la entrega.'
        }),
        ('Cronograma Técnico', {
            'fields': (
                ('fecha_recepcion', 'fecha_fabricacion'), 
                ('fecha_muestreo', 'fecha_ensayo_programado')
            ),
        }),
    )
    
    list_display = ('get_custom_id', 'get_cliente', 'procedencia', 'fecha_recepcion', 'get_conteo_muestras')
    list_filter = ('fecha_recepcion', 'cotizacion__cliente', 'procedencia')
    search_fields = ('cotizacion__numero_oferta', 'cotizacion__cliente__razon_social', 'responsable_cliente')
    inlines = [MuestraDetalleInline]
    autocomplete_fields = ['cotizacion'] 
    date_hierarchy = 'fecha_recepcion'

    # --- MÉTODOS PARA EL FORMULARIO (Detalle) ---

    def get_cliente_display(self, obj):
        """Muestra el cliente en el formulario de edición"""
        if obj.id and obj.cotizacion and obj.cotizacion.cliente:
            return format_html('<b>{}</b>', obj.cotizacion.cliente.razon_social)
        return "Se asignará al guardar"
    get_cliente_display.short_description = 'Cliente Asociado'

    # --- MÉTODOS PARA LA LISTA (Table) ---

    def get_custom_id(self, obj):
        """Corrige el error de format code 'd' asegurando que el ID sea entero"""
        if obj.id:
            return format_html('<b>REC-{:04d}</b>', int(obj.id))
        return "Nvo"
    get_custom_id.short_description = 'Folio'

    def get_cliente(self, obj):
        """Muestra el cliente en la tabla principal"""
        try:
            return obj.cotizacion.cliente.razon_social
        except AttributeError:
            return "-"
    get_cliente.short_description = 'Cliente'

    def get_conteo_muestras(self, obj):
        """Badge visual para cantidad de muestras"""
        count = obj.muestras.count()
        return format_html(
            '<span style="background: #4f46e5; color: white; padding: 2px 8px; border-radius: 10px; font-weight: bold;">{}</span>', 
            count
        )
    get_conteo_muestras.short_description = 'Cant.'

@admin.register(Proyecto)
class ProyectoAdmin(admin.ModelAdmin):
    list_display = ('codigo_proyecto', 'nombre_proyecto', 'get_estado_color', 'get_progreso_visual')
    readonly_fields = ('codigo_proyecto', 'numero_muestras_registradas', 'creado_en', 'modificado_en')
    list_filter = ('estado', 'cliente')
    
    def get_estado_color(self, obj):
        colores = {
            'PENDIENTE': '#94a3b8',
            'EN_CURSO': '#3b82f6',
            'FINALIZADO': '#10b981',
            'CANCELADO': '#ef4444',
        }
        return format_html(
            '<b style="color: white; background: {}; padding: 2px 8px; border-radius: 4px;">{}</b>',
            colores.get(obj.estado, '#000'), obj.get_estado_display()
        )
    get_estado_color.short_description = 'Estado'

    def get_progreso_visual(self, obj):
        total = obj.numero_muestras
        actual = obj.muestras_registradas_reales
        porcentaje = (actual / total * 100) if total > 0 else 0
        return format_html(
            '''
            <div style="width: 100px; background: #e2e8f0; border-radius: 4px; height: 12px;">
                <div style="width: {}px; background: #4f46e5; height: 12px; border-radius: 4px;"></div>
            </div>
            <small>{} de {}</small>
            ''',
            porcentaje, actual, total
        )
    get_progreso_visual.short_description = 'Avance'

@admin.register(TipoMuestra)
class TipoMuestraAdmin(admin.ModelAdmin):
    list_display = ('sigla', 'nombre')
    search_fields = ('sigla', 'nombre')

@admin.register(MuestraDetalle)
class MuestraDetalleAdmin(admin.ModelAdmin):
    list_display = ('codigo_laboratorio', 'tipo_muestra', 'get_link_recepcion', 'descripcion', 'masa_aprox')
    readonly_fields = ('codigo_laboratorio',)
    
    def get_link_recepcion(self, obj):
        url = reverse('admin:proyectos_recepcionmuestra_change', args=[obj.recepcion.id])
        return format_html('<a href="{}">Ir a Recepción #{}</a>', url, obj.recepcion.id)
    get_link_recepcion.short_description = 'Documento Origen'