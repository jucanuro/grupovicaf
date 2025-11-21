# servicios/admin.py

from django.contrib import admin
from django.utils.html import format_html
from decimal import Decimal
from .models import (
    Servicio,
    DetalleServicio,
    Cotizacion,
    CotizacionDetalle,
    Voucher,
    Norma,
    Metodo,
    CategoriaServicio
)

# ================================================================
# 1. INLINES (Detalles Anidados)
# ================================================================

class CotizacionDetalleInline(admin.TabularInline):
    model = CotizacionDetalle
    extra = 1
    
    fields = [
        'servicio', 
        'norma', 
        'metodo', 
        'descripcion_especifica', 
        'unidad_medida', 
        'cantidad', 
        'precio_unitario',
        'total_detalle'
    ]
    
    readonly_fields = ['total_detalle'] 


class DetalleServicioInline(admin.StackedInline):
    model = DetalleServicio
    extra = 1
    verbose_name = "Detalle para Web/Portal"
    verbose_name_plural = "Detalles para Web/Portal"


# ================================================================
# 2. ADMINISTRACIÓN DE MODELOS
# ================================================================

@admin.register(CotizacionDetalle)
class CotizacionDetalleAdmin(admin.ModelAdmin):
    search_fields = (
        'cotizacion__numero_oferta', 
        'servicio__nombre', 
        'norma'
    )
    
    list_display = (
        'cotizacion', 
        'servicio', 
        'cantidad', 
        'precio_unitario'
    )
    list_filter = ('cotizacion__estado',)
    

@admin.register(Cotizacion)
class CotizacionAdmin(admin.ModelAdmin):
    list_display = (
        'numero_oferta', 
        'cliente', 
        'servicio_general', 
        'asunto_servicio', 
        'trabajador_responsable',
        'subtotal', 
        'impuesto_igv', 
        'monto_total',  
        'estado', 
        'fecha_creacion'
    )
    list_filter = ('estado', 'forma_pago', 'fecha_creacion', 'servicio_general')
    search_fields = ('numero_oferta', 'cliente__razon_social', 'asunto_servicio')
    date_hierarchy = 'fecha_creacion'

    fieldsets = (
        ('INFORMACIÓN PRINCIPAL', {
            'fields': (
                ('numero_oferta', 'estado'), 
                ('cliente', 'trabajador_responsable'),
                'servicio_general',
                'asunto_servicio',
                'proyecto_asociado',
            )
        }),
        ('DATOS DE CONTACTO Y CONDICIONES', {
            'fields': (
                ('persona_contacto', 'correo_contacto', 'telefono_contacto'),
                ('plazo_entrega_dias', 'forma_pago', 'validez_oferta_dias'),
                'observaciones_condiciones',
            )
        }),
        ('RESUMEN FINANCIERO', {
            'fields': (
                'tasa_igv', 
                'subtotal', 
                'impuesto_igv', 
                'monto_total'
            ),
            'classes': ('collapse',),
        }),
    )

    readonly_fields = [
        'subtotal', 
        'impuesto_igv', 
        'monto_total'
    ]

    inlines = [CotizacionDetalleInline]
    
    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)
        
    def save_formset(self, request, form, formset, change):
        super().save_formset(request, form, formset, change)
        
        if formset.model == CotizacionDetalle and change:
            cotizacion = form.instance
            if cotizacion.pk:
                cotizacion.calcular_totales()
                cotizacion.save()
                
    def display_monto_total(self, obj):
        return f"S/. {obj.monto_total:.2f}"
    display_monto_total.short_description = 'Monto Total'


@admin.register(CategoriaServicio)
class CategoriaAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'descripcion')
    search_fields = ('nombre',)


@admin.register(Servicio)
class ServicioAdmin(admin.ModelAdmin):
    inlines = [DetalleServicioInline]
    
    list_display = (
        'categoria',
        'codigo_facturacion', 
        'nombre', 
        'precio_base_display', 
        'unidad_base',
        'esta_acreditado_icon',
        'get_normas', 
        'get_metodos',
    )
    
    list_filter = ('categoria','esta_acreditado', 'normas', 'metodos')
    search_fields = ('codigo_facturacion', 'nombre', 'descripcion')
    filter_horizontal = ('normas', 'metodos')

    fieldsets = (
        ('I. IDENTIFICACIÓN Y TARIFARIO', {
            'fields': (
                'categoria',
                'codigo_facturacion', 
                'nombre', 
                'descripcion',
                ('precio_base', 'unidad_base'),
                ('esta_acreditado'),
                'imagen',
            )
        }),
        ('II. DATOS TÉCNICOS (Para OTE)', {
            'fields': ('normas', 'metodos'),
            'description': 'Seleccione las normas y métodos asociados a este ensayo.'
        }),
    )

    def get_normas(self, obj):
        return ", ".join([norma.codigo for norma in obj.normas.all()])
    get_normas.short_description = "Normas (Códigos)"
    
    def get_metodos(self, obj):
        return ", ".join([metodo.codigo for metodo in obj.metodos.all()])
    get_metodos.short_description = "Métodos"

    def precio_base_display(self, obj):
        return f"S/ {obj.precio_base:,.2f}"
    precio_base_display.short_description = "P. Base (S/)"

    def esta_acreditado_icon(self, obj):
        if obj.esta_acreditado:
            return format_html('<span style="color: green;">✔</span>')
        return format_html('<span style="color: red;">✘</span>')
    esta_acreditado_icon.short_description = 'Acreditado'


@admin.register(Norma)
class NormaAdmin(admin.ModelAdmin):
    list_display = ('codigo', 'nombre')
    search_fields = ('codigo', 'nombre')

@admin.register(Metodo)
class MetodoAdmin(admin.ModelAdmin):
    list_display = ('codigo', 'nombre')
    search_fields = ('codigo', 'nombre')

@admin.register(Voucher)
class VoucherAdmin(admin.ModelAdmin):
    list_display = ('codigo', 'cotizacion', 'monto_pagado', 'fecha_subida', 'get_cliente_razon_social')
    search_fields = ('codigo', 'cotizacion__numero_oferta', 'cotizacion__cliente__razon_social')
    readonly_fields = ('fecha_subida',)

    def get_cliente_razon_social(self, obj):
        return obj.cotizacion.cliente.razon_social
    get_cliente_razon_social.short_description = 'Cliente'