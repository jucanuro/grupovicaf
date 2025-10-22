from django.contrib import admin
from django.db import models
from django.forms import Textarea
# Importamos el modelo intermedio clave para registrarlo en el admin
from .models import (
    Proyecto, 
    Muestra, 
    TipoEnsayo, # <-- Modelo Catálogo
    SolicitudEnsayo, 
    DetalleEnsayo, 
    AsignacionTipoEnsayo, # <-- Modelo Intermedio Clave
    ResultadoEnsayo, 
    DocumentoFinal
)

# =======================================================
# 1. Asignación de Tipo Ensayo (Inline para DetalleEnsayo)
# =======================================================

class AsignacionTipoEnsayoInline(admin.TabularInline):
    """
    Permite asignar múltiples Tipos de Ensayos a una Tarea (DetalleEnsayo)
    y, crucialmente, asignar un Técnico a cada Tipo de Ensayo individual.
    """
    model = AsignacionTipoEnsayo
    extra = 1
    verbose_name = "Asignación de Ensayo/Técnico"
    verbose_name_plural = "Asignaciones de Ensayos a Técnicos"
    fields = ('tipo_ensayo', 'tecnico_asignado',)
    autocomplete_fields = ['tipo_ensayo', 'tecnico_asignado']
    
# =======================================================
# 2. Resultados de Ensayo (Inline para DetalleEnsayo)
# =======================================================

class ResultadoEnsayoInline(admin.StackedInline):
    """Permite el registro del resultado asociado a una línea de trabajo (DetalleEnsayo)."""
    model = ResultadoEnsayo
    max_num = 1
    can_delete = False
    
    # Widgets para mejorar la apariencia del JSONField/TextField grande
    formfield_overrides = {
        models.JSONField: {'widget': Textarea(attrs={'rows': 5, 'cols': 80})},
    }

    fieldsets = (
        ('Registro de Datos', {
            'fields': ('tecnico_registro', 'fecha_realizacion', 'resultados_data', 'observaciones',),
        }),
        ('Validación y Verificación', {
            'fields': ('es_valido', 'verificado_por', 'fecha_verificacion',),
        }),
    )
    # Ya no hay 'muestra' como campo directo.
    readonly_fields = ('creado_en',) 


# =======================================================
# 3. Detalle de Ensayo (Inline para SolicitudEnsayo)
# =======================================================

class DetalleEnsayoInline(admin.StackedInline): # Cambiado a StackedInline para mejor vista de inlines anidados
    """Las líneas de trabajo (tareas) que componen una Solicitud."""
    model = DetalleEnsayo
    extra = 0
    # Quitamos 'tecnico_asignado' de fields y list_display
    fields = (
        'tipo_ensayo_descripcion', 
        'norma_aplicable', 
        'metodo_aplicable',
        'fecha_limite_ejecucion',
        'estado_detalle',
    )
    # list_display no se usa en inlines, pero usamos fields para el orden
    autocomplete_fields = ['detalle_cotizacion'] # Quitamos 'tecnico_asignado'
    inlines = [AsignacionTipoEnsayoInline, ResultadoEnsayoInline] # Incluimos los dos sub-inlines


# =======================================================
# 4. Solicitud de Ensayo (Inline para Muestra)
# =======================================================

class SolicitudEnsayoInline(admin.StackedInline):
    """La Solicitud de Ensayo (la Orden) asociada a una muestra."""
    model = SolicitudEnsayo
    max_num = 1
    can_delete = False
    
    fieldsets = (
        ('Datos de la Solicitud', {
            'fields': ('codigo_solicitud', 'fecha_solicitud', 'generada_por', 'estado'),
        }),
    )
    readonly_fields = ('estado', 'fecha_solicitud')
    autocomplete_fields = ['generada_por']
    inlines = [DetalleEnsayoInline]


# =======================================================
# 5. Muestra (Inline para Proyecto)
# =======================================================

class MuestraInline(admin.StackedInline):
    """Las muestras asociadas a un proyecto."""
    model = Muestra
    extra = 1
    fieldsets = (
        ('Identificación y Estado', {
            'fields': (
                ('codigo_muestra', 'id_lab', 'tipo_muestra'), 
                'tecnico_responsable_muestra',
                ('estado', 'fecha_recepcion'),
            )
        }),
        ('Detalles y Fechas', {
            'fields': ('descripcion_muestra', 'masa_aprox_kg', 'fecha_fabricacion', 'fecha_ensayo_rotura'),
        }),
    )
    search_fields = ('codigo_muestra',)
    autocomplete_fields = ['tecnico_responsable_muestra']
    inlines = [SolicitudEnsayoInline]


# =======================================================
# 6. Documento Final (Inline para Proyecto)
# =======================================================

class DocumentoFinalInline(admin.StackedInline):
    """El informe o documento final del proyecto."""
    model = DocumentoFinal
    max_num = 1
    can_delete = False
    
    fieldsets = (
        ('Emisión', {
            'fields': ('titulo', 'fecha_emision', 'archivo_original'),
        }),
        ('Asistencia IA (Opcional)', {
            'fields': ('resumen_ejecutivo_ia', 'analisis_detallado_ia', 'recomendaciones_ia'),
            'classes': ('collapse',),
        }),
        ('Firmas', {
            'fields': ('firma_supervisor', 'firma_cliente'),
        })
    )


# =======================================================
# 7. Registro de Modelos en el Admin
# =======================================================

@admin.register(Proyecto)
class ProyectoAdmin(admin.ModelAdmin):
    list_display = (
        'codigo_proyecto', 'nombre_proyecto', 'cliente', 'monto_cotizacion', 
        'estado', 'fecha_inicio', 'numero_muestras', 'numero_muestras_registradas'
    )
    list_filter = ('estado', 'fecha_inicio', 'cliente')
    search_fields = ('codigo_proyecto', 'nombre_proyecto', 'cliente__razon_social', 'codigo_voucher')
    ordering = ('-fecha_inicio',)
    
    fieldsets = (
        ('Información de Origen', {
            'fields': ('cotizacion', 'monto_cotizacion', 'codigo_voucher'),
            'description': 'Información generada automáticamente desde la Cotización aprobada.'
        }),
        ('Datos del Proyecto', {
            'fields': ('codigo_proyecto', 'nombre_proyecto', 'cliente', 'descripcion_proyecto', 'estado'),
        }),
        ('Metas y Plazos', {
            'fields': ('fecha_inicio', 'fecha_entrega_estimada', ('numero_muestras', 'numero_muestras_registradas')),
        }),
    )
    readonly_fields = ('cotizacion', 'monto_cotizacion', 'codigo_voucher', 'numero_muestras_registradas')
    autocomplete_fields = ['cliente', 'cotizacion']
    inlines = [MuestraInline, DocumentoFinalInline]


@admin.register(Muestra)
class MuestraAdmin(admin.ModelAdmin):
    list_display = ('codigo_muestra', 'proyecto', 'tipo_muestra', 'estado', 'tecnico_responsable_muestra', 'fecha_recepcion')
    list_filter = ('estado', 'tipo_muestra', 'proyecto__cliente')
    search_fields = ('codigo_muestra', 'id_lab', 'proyecto__codigo_proyecto')
    autocomplete_fields = ['proyecto', 'tecnico_responsable_muestra']
    inlines = [SolicitudEnsayoInline]
    
    fieldsets = (
        ('Identificación de la Muestra', {
            'fields': ('proyecto', 'codigo_muestra', 'id_lab', 'tipo_muestra', 'descripcion_muestra', 'masa_aprox_kg'),
        }),
        ('Logística y Responsabilidad', {
            'fields': ('tecnico_responsable_muestra', 'estado', 'fecha_recepcion', 'fecha_fabricacion', 'fecha_ensayo_rotura'),
        }),
    )


@admin.register(TipoEnsayo) # Registro del nuevo Catálogo
class TipoEnsayoAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'codigo_interno', 'descripcion')
    search_fields = ('nombre', 'codigo_interno')


@admin.register(SolicitudEnsayo)
class SolicitudEnsayoAdmin(admin.ModelAdmin):
    list_display = ('codigo_solicitud', 'muestra', 'estado', 'generada_por', 'fecha_solicitud')
    list_filter = ('estado', 'fecha_solicitud')
    search_fields = ('codigo_solicitud', 'muestra__codigo_muestra')
    autocomplete_fields = ['muestra', 'generada_por']
    inlines = [DetalleEnsayoInline]
    readonly_fields = ('estado',)

@admin.register(DetalleEnsayo)
class DetalleEnsayoAdmin(admin.ModelAdmin):
    # Quitamos 'tecnico_asignado' de list_display
    list_display = ('solicitud', 'tipo_ensayo_descripcion', 'fecha_limite_ejecucion', 'estado_detalle')
    # Quitamos 'tecnico_asignado' de list_filter. El técnico ahora se filtra por la tabla intermedia.
    list_filter = ('estado_detalle', ) 
    search_fields = ('tipo_ensayo_descripcion', 'solicitud__codigo_solicitud')
    # Quitamos 'tecnico_asignado' de autocomplete_fields
    autocomplete_fields = ['solicitud', 'detalle_cotizacion'] 
    inlines = [AsignacionTipoEnsayoInline, ResultadoEnsayoInline] # Aseguramos los dos inlines

@admin.register(ResultadoEnsayo)
class ResultadoEnsayoAdmin(admin.ModelAdmin):
    # Quitamos 'muestra' de list_display.
    def get_muestra_codigo(self, obj):
        return obj.detalle_ensayo.solicitud.muestra.codigo_muestra
    get_muestra_codigo.short_description = "Muestra"

    list_display = ('detalle_ensayo', 'get_muestra_codigo', 'tecnico_registro', 'es_valido', 'verificado_por', 'fecha_realizacion')
    list_filter = ('es_valido', 'fecha_realizacion', 'tecnico_registro')
    # Ajustamos el search para buscar la muestra a través de la relación correcta
    search_fields = ('detalle_ensayo__solicitud__codigo_solicitud', 'detalle_ensayo__solicitud__muestra__codigo_muestra')
    # Quitamos 'muestra' de autocomplete_fields
    autocomplete_fields = ['detalle_ensayo', 'tecnico_registro', 'verificado_por']


@admin.register(DocumentoFinal)
class DocumentoFinalAdmin(admin.ModelAdmin):
    list_display = ('proyecto', 'titulo', 'fecha_emision')
    search_fields = ('proyecto__codigo_proyecto', 'titulo')
    autocomplete_fields = ['proyecto']
    readonly_fields = ('resumen_ejecutivo_ia', 'analisis_detallado_ia', 'recomendaciones_ia')
