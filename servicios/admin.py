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
    Metodo
)

# ================================================================
# 1. INLINES (Detalles Anidados)
# ================================================================
@admin.register(CotizacionDetalle)
class CotizacionDetalleAdmin(admin.ModelAdmin):
    # Esto es lo más importante: definir campos de búsqueda.
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
    

class CotizacionDetalleInline(admin.TabularInline):
    """
    Permite editar los detalles de la cotización directamente en la página 
    de edición de la cotización principal.
    """
    model = CotizacionDetalle
    extra = 1 # Número de formularios vacíos para agregar
    
    # Campos que el usuario puede editar en el detalle
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
    
    # 'total_detalle' es un campo que se calcula automáticamente en el save() del modelo,
    # por lo que lo hacemos de solo lectura para evitar ediciones manuales accidentales.
    readonly_fields = ['total_detalle'] 


@admin.register(Cotizacion)
class CotizacionAdmin(admin.ModelAdmin):
    # ================================================================
    # 2. Configuración de la Lista (List View)
    # ================================================================
    list_display = (
        'numero_oferta', 
        'cliente', 
        'asunto_servicio', 
        'trabajador_responsable',
        'subtotal', # Campo para verificar el cálculo
        'impuesto_igv', # Campo para verificar el cálculo
        'monto_total',  # Campo para verificar el cálculo
        'estado', 
        'fecha_creacion'
    )
    list_filter = ('estado', 'forma_pago', 'fecha_creacion')
    search_fields = ('numero_oferta', 'cliente__razon_social', 'asunto_servicio')
    date_hierarchy = 'fecha_creacion'

    # ================================================================
    # 3. Configuración del Formulario (Change/Add View)
    # ================================================================
    fieldsets = (
        ('INFORMACIÓN PRINCIPAL', {
            'fields': (
                ('numero_oferta', 'estado'), 
                ('cliente', 'trabajador_responsable'),
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
            # Estos campos deben ser de solo lectura para reflejar los cálculos
            'fields': (
                'tasa_igv', 
                'subtotal', 
                'impuesto_igv', 
                'monto_total'
            ),
            'classes': ('collapse',), # Opcional: para que esta sección esté plegada por defecto
        }),
    )

    readonly_fields = [
        'subtotal', 
        'impuesto_igv', 
        'monto_total'
    ]

    inlines = [CotizacionDetalleInline]
    
    # ================================================================
    # 4. Lógica de Recálculo en el Admin
    # ================================================================
    def save_model(self, request, obj, form, change):
        """ 
        Llamado justo antes de guardar el objeto principal. 
        Garantizamos que la función calcular_totales se ejecute al guardar.
        """
        super().save_model(request, obj, form, change)
        
    def save_formset(self, request, form, formset, change):
        """ 
        Llamado después de guardar el inline formset.
        Es CRÍTICO volver a calcular los totales del padre después de guardar los detalles.
        """
        super().save_formset(request, form, formset, change)
        
        # Si estamos editando una Cotizacion existente, forzamos el recalculo
        if formset.model == CotizacionDetalle and change:
            cotizacion = form.instance
            if cotizacion.pk:
                cotizacion.calcular_totales()
                cotizacion.save() # Llama a save que recalcula y guarda los montos
                
    # Opcional: Asegúrate de que los campos de moneda se muestren con dos decimales
    def display_monto_total(self, obj):
        return f"S/. {obj.monto_total:.2f}"
    display_monto_total.short_description = 'Monto Total'



class DetalleServicioInline(admin.StackedInline):
    """
    Permite editar los detalles web del servicio dentro de la vista de Servicio.
    """
    model = DetalleServicio
    extra = 1
    verbose_name = "Detalle para Web/Portal"
    verbose_name_plural = "Detalles para Web/Portal"


# ================================================================
# 2. MODELADMINS (Vistas Principales)
# ================================================================
@admin.register(Servicio)
class ServicioAdmin(admin.ModelAdmin):
    inlines = [DetalleServicioInline]
    
    list_display = (
        'codigo_facturacion', 
        'nombre', 
        'precio_base_display', 
        'unidad_base',
        'esta_acreditado_icon',
        'get_normas', 
        'get_metodos',
    )
    
    list_filter = ('esta_acreditado', 'normas', 'metodos')
    search_fields = ('codigo_facturacion', 'nombre', 'descripcion')
    filter_horizontal = ('normas', 'metodos') # Para campos ManyToMany, mejora UX

    # Organización de la vista de detalle
    fieldsets = (
        ('I. IDENTIFICACIÓN Y TARIFARIO', {
            'fields': (
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

    # Métodos Display
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


# ================================================================
# 3. REGISTROS SIMPLES
# ================================================================

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

# El modelo DetalleServicio ya está en línea, no necesita registro individual.
# admin.site.register(DetalleServicio) # Comentado, ya se usa como inline