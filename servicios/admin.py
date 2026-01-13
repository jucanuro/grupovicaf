from django.contrib import admin
from .models import (
    Servicio,
    CategoriaServicio,
    Subcategoria,
    Norma,
    Metodo,
    Cotizacion,
    CotizacionGrupo,
    CotizacionDetalle,
    Voucher
)

class CotizacionDetalleInline(admin.TabularInline):
    model = CotizacionDetalle
    extra = 1
    fields = [
        'servicio', 
        'norma_manual', 
        'metodo_manual', 
        'descripcion_especifica', 
        'unidad_medida', 
        'cantidad', 
        'precio_unitario',
        'total_detalle'
    ]
    readonly_fields = ['total_detalle']

@admin.register(CotizacionGrupo)
class CotizacionGrupoAdmin(admin.ModelAdmin):
    list_display = ('nombre_grupo', 'cotizacion', 'orden')
    list_filter = ('cotizacion',)
    inlines = [CotizacionDetalleInline]

class CotizacionGrupoInline(admin.StackedInline):
    model = CotizacionGrupo
    extra = 1
    show_change_link = True

@admin.register(Cotizacion)
class CotizacionAdmin(admin.ModelAdmin):
    list_display = (
        'numero_oferta', 
        'cliente', 
        'asunto_servicio', 
        'monto_total',  
        'estado', 
        'fecha_generacion'
    )
    list_filter = ('estado', 'forma_pago', 'fecha_generacion')
    search_fields = ('numero_oferta', 'cliente__razon_social', 'asunto_servicio')
    date_hierarchy = 'fecha_generacion'
    readonly_fields = ['subtotal', 'impuesto_igv', 'monto_total', 'fecha_creacion', 'fecha_actualizacion']
    
    inlines = [CotizacionGrupoInline]

    fieldsets = (
        ('INFORMACIÓN DE CABECERA', {
            'fields': (
                ('numero_oferta', 'fecha_generacion', 'estado'),
                ('cliente', 'trabajador_responsable'),
            )
        }),
        ('DETALLES DEL PROYECTO', {
            'fields': ('asunto_servicio', 'proyecto_asociado', 'persona_contacto', 'correo_contacto', 'telefono_contacto')
        }),
        ('CONDICIONES COMERCIALES', {
            'fields': (('plazo_entrega_dias', 'validez_oferta_dias', 'forma_pago'), 'observaciones_condiciones')
        }),
        ('RESUMEN ECONÓMICO', {
            'fields': (('subtotal', 'tasa_igv'), ('impuesto_igv', 'monto_total')),
            'description': 'Los montos se recalculan automáticamente al guardar.'
        }),
    )

    def save_related(self, request, form, formsets, change):
        super().save_related(request, form, formsets, change)
        instance = form.instance
        instance.calcular_totales()
        instance.save()

@admin.register(Servicio)
class ServicioAdmin(admin.ModelAdmin):
    list_display = ('codigo_facturacion', 'nombre', 'norma', 'metodo', 'precio_base', 'esta_acreditado')
    list_filter = ('esta_acreditado', 'unidad_base')
    search_fields = ('nombre', 'codigo_facturacion', 'norma__codigo')
    
    fieldsets = (
        ('IDENTIFICACIÓN', {
            'fields': (('codigo_facturacion', 'esta_acreditado'), 'nombre')
        }),
        ('DATOS TÉCNICOS', {
            'fields': (('norma', 'metodo'),)
        }),
        ('DATOS COMERCIALES', {
            'fields': (('precio_base', 'unidad_base'),)
        }),
    )

@admin.register(CategoriaServicio)
class CategoriaAdmin(admin.ModelAdmin):
    list_display = ('nombre',)
    search_fields = ('nombre',)

@admin.register(Subcategoria)
class SubcategoriaAdmin(admin.ModelAdmin):
    list_display = ('nombre',)
    search_fields = ('nombre',)

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
    list_display = ('codigo', 'cotizacion', 'monto_pagado', 'fecha_subida')
    readonly_fields = ('fecha_subida',)