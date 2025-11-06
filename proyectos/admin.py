from django.contrib import admin
from django.db import models
from django.forms import Textarea
from .models import (
    Proyecto, 
    Muestra, 
    TipoEnsayo, 
    SolicitudEnsayo, 
    DetalleEnsayo, 
    AsignacionTipoEnsayo, 
    ResultadoEnsayo, 
    DocumentoFinal,
    ReporteIncidencia 
)
# Se asume que estos modelos ya están enlazados en proyectos/models.py
from servicios.models import Norma, Metodo, Cotizacion, CotizacionDetalle 

class AsignacionTipoEnsayoInline(admin.TabularInline):
    model = AsignacionTipoEnsayo
    extra = 1
    verbose_name = "Asignación de Ensayo/Técnico"
    verbose_name_plural = "Asignaciones de Ensayos a Técnicos"
    fields = ('tipo_ensayo', 'tecnico_asignado',)
    raw_id_fields = ['tipo_ensayo', 'tecnico_asignado'] 
    
class ResultadoEnsayoInline(admin.StackedInline):
    model = ResultadoEnsayo
    max_num = 1
    can_delete = False
    
    formfield_overrides = {
        models.JSONField: {'widget': Textarea(attrs={'rows': 6, 'cols': 90})},
        models.TextField: {'widget': Textarea(attrs={'rows': 3, 'cols': 90})},
    }

    fieldsets = (
        ('Registro de Datos', {
            'fields': ('tecnico_registro', 'fecha_realizacion', 'resultados_data', 'observaciones',),
        }),
        ('Validación y Verificación (Jefe/Supervisor)', {
            'fields': ('es_valido', 'verificado_por', 'fecha_verificacion',),
            'classes': ('collapse',),
        }),
    )
    raw_id_fields = ('tecnico_registro', 'verificado_por')


class ReporteIncidenciaInline(admin.StackedInline):
    model = ReporteIncidencia
    extra = 0
    verbose_name = "Incidencia"
    verbose_name_plural = "Reporte de Incidencias"
    
    fieldsets = (
        (None, {
            'fields': ('tipo_incidencia', 'fecha_ocurrencia', 'detalle_incidencia'),
        }),
        ('Firmas y Responsables', {
            'fields': ('representante_cliente', 'responsable_laboratorio'),
        }),
    )
    raw_id_fields = ['responsable_laboratorio'] 

class DetalleEnsayoInline(admin.StackedInline): 
    model = DetalleEnsayo
    extra = 0
    
    fieldsets = (
        ('Identificación de Tarea', {
            'fields': (
                'tipo_ensayo_descripcion', 
                ('norma', 'metodo'), 
                'detalle_cotizacion', 
            )
        }),
        ('Seguimiento y Cierre', {
            'fields': (
                ('fecha_limite_ejecucion', 'fecha_entrega_real'),
                ('estado_detalle', 'firma_tecnico'),
                'observaciones_detalle'
            ),
        }),
    )
    # Corrección E002: raw_id_fields para el inline
    raw_id_fields = ['detalle_cotizacion', 'norma', 'metodo', 'firma_tecnico'] 
    inlines = [AsignacionTipoEnsayoInline, ResultadoEnsayoInline] 


class SolicitudEnsayoInline(admin.StackedInline):
    model = SolicitudEnsayo
    max_num = 1
    can_delete = False
    
    fieldsets = (
        ('Datos de la Solicitud (Cabecera)', {
            'fields': (
                # Se mantiene 'cotizacion' aquí para que se muestre como campo de solo lectura
                ('codigo_solicitud', 'cotizacion'), 
                ('fecha_solicitud', 'fecha_entrega_programada'),
                ('fecha_entrega_real', 'estado'),
                ('generada_por', 'firma_jefe_laboratorio'),
            ),
        }),
    )
    # CORRECCIÓN CLAVE: Quitamos 'cotizacion' de raw_id_fields
    raw_id_fields = ['generada_por', 'firma_jefe_laboratorio'] 
    # CORRECCIÓN CLAVE: Agregamos 'cotizacion' a readonly_fields
    readonly_fields = ('estado', 'fecha_solicitud', 'cotizacion')
    inlines = [DetalleEnsayoInline, ReporteIncidenciaInline] 


class MuestraInline(admin.StackedInline):
    model = Muestra
    extra = 1
    fieldsets = (
        ('Identificación y Estado', {
            'fields': (
                ('codigo_muestra', 'id_lab', 'tipo_muestra'), 
                ('estado', 'fecha_recepcion'),
                'tecnico_responsable_muestra',
            )
        }),
        ('Detalles y Fechas', {
            'fields': ('descripcion_muestra', 'masa_aprox_kg', 'fecha_fabricacion', 'fecha_ensayo_rotura'),
        }),
    )
    search_fields = ('codigo_muestra',)
    raw_id_fields = ['tecnico_responsable_muestra']
    inlines = [SolicitudEnsayoInline]


class DocumentoFinalInline(admin.StackedInline):
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
        ('Datos del Proyecto', {
            'fields': ('codigo_proyecto', 'nombre_proyecto', 'cliente', 'descripcion_proyecto', 'estado'),
        }),
        ('Información de Origen', {
            'fields': ('cotizacion', 'monto_cotizacion', 'codigo_voucher'),
            'description': 'Información generada automáticamente desde la Cotización aprobada.'
        }),
        ('Metas y Plazos', {
            'fields': ('fecha_inicio', 'fecha_entrega_estimada', ('numero_muestras', 'numero_muestras_registradas')),
        }),
    )
    readonly_fields = ('cotizacion', 'monto_cotizacion', 'codigo_voucher', 'numero_muestras_registradas')
    raw_id_fields = ['cliente', 'cotizacion']
    inlines = [MuestraInline, DocumentoFinalInline]


@admin.register(Muestra)
class MuestraAdmin(admin.ModelAdmin):
    list_display = ('codigo_muestra', 'proyecto', 'tipo_muestra', 'estado', 'tecnico_responsable_muestra', 'fecha_recepcion')
    list_filter = ('estado', 'tipo_muestra', 'proyecto__cliente')
    search_fields = ('codigo_muestra', 'id_lab', 'proyecto__codigo_proyecto')
    raw_id_fields = ['proyecto', 'tecnico_responsable_muestra']
    inlines = [SolicitudEnsayoInline]
    
    fieldsets = (
        ('Identificación de la Muestra', {
            'fields': ('proyecto', 'codigo_muestra', 'id_lab', 'tipo_muestra', 'descripcion_muestra', 'masa_aprox_kg'),
        }),
        ('Logística y Responsabilidad', {
            'fields': ('tecnico_responsable_muestra', 'estado', 'fecha_recepcion', 'fecha_fabricacion', 'fecha_ensayo_rotura'),
        }),
    )


@admin.register(TipoEnsayo) 
class TipoEnsayoAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'codigo_interno', 'descripcion')
    search_fields = ('nombre', 'codigo_interno')


@admin.register(SolicitudEnsayo)
class SolicitudEnsayoAdmin(admin.ModelAdmin):
    list_display = ('codigo_solicitud', 'muestra', 'cotizacion', 'estado', 'generada_por', 'fecha_solicitud')
    list_filter = ('estado', 'fecha_solicitud')
    search_fields = ('codigo_solicitud', 'muestra__codigo_muestra')
    # CORRECCIÓN: 'cotizacion' ya no es raw_id_field, es read-only.
    raw_id_fields = ['muestra', 'generada_por', 'firma_jefe_laboratorio'] 
    inlines = [DetalleEnsayoInline, ReporteIncidenciaInline]
    # CORRECCIÓN: 'cotizacion' es read-only.
    readonly_fields = ('estado', 'fecha_solicitud', 'cotizacion') 
    
    fieldsets = (
        ('Información de Cabecera', {
            'fields': (
                ('codigo_solicitud', 'muestra'), 
                ('fecha_solicitud', 'generada_por'),
                'estado',
                'cotizacion' # Se muestra aquí como read-only
            )
        }),
        ('Plazos y Aprobación', {
            'fields': (
                ('fecha_entrega_programada', 'fecha_entrega_real'),
                'firma_jefe_laboratorio',
            )
        }),
    )


@admin.register(DetalleEnsayo)
class DetalleEnsayoAdmin(admin.ModelAdmin):
    # Ya corregido y activado: requiere que 'estado_detalle' y 'detalle_cotizacion' existan en el modelo.
    list_display = ('solicitud', 'tipo_ensayo_descripcion', 'get_norma_display', 'get_metodo_display', 'fecha_limite_ejecucion', 'estado_detalle') 
    list_filter = ('estado_detalle', 'norma', 'metodo') 
    search_fields = ('tipo_ensayo_descripcion', 'solicitud__codigo_solicitud')
    raw_id_fields = ['solicitud', 'detalle_cotizacion', 'norma', 'metodo', 'firma_tecnico'] 
    inlines = [AsignacionTipoEnsayoInline, ResultadoEnsayoInline] 
    
    def get_norma_display(self, obj):
        return obj.norma.nombre if obj.norma else "N/A"
    get_norma_display.short_description = "Norma"

    def get_metodo_display(self, obj):
        return obj.metodo.nombre if obj.metodo else "N/A"
    get_metodo_display.short_description = "Método"


@admin.register(ResultadoEnsayo)
class ResultadoEnsayoAdmin(admin.ModelAdmin):
    def get_muestra_codigo(self, obj):
        return obj.detalle_ensayo.solicitud.muestra.codigo_muestra
    get_muestra_codigo.short_description = "Muestra"

    list_display = ('detalle_ensayo', 'get_muestra_codigo', 'tecnico_registro', 'es_valido', 'verificado_por', 'fecha_realizacion')
    list_filter = ('es_valido', 'fecha_realizacion', 'tecnico_registro')
    search_fields = ('detalle_ensayo__solicitud__codigo_solicitud', 'detalle_ensayo__solicitud__muestra__codigo_muestra')
    raw_id_fields = ['detalle_ensayo', 'tecnico_registro', 'verificado_por']


@admin.register(DocumentoFinal)
class DocumentoFinalAdmin(admin.ModelAdmin):
    list_display = ('proyecto', 'titulo', 'fecha_emision')
    search_fields = ('proyecto__codigo_proyecto', 'titulo')
    raw_id_fields = ['proyecto']
    readonly_fields = ('resumen_ejecutivo_ia', 'analisis_detallado_ia', 'recomendaciones_ia')
    
    fieldsets = (
        (None, {
            'fields': ('proyecto', 'titulo', 'fecha_emision', 'archivo_original'),
        }),
        ('Firmas', {
            'fields': ('firma_supervisor', 'firma_cliente'),
        }),
    )


@admin.register(ReporteIncidencia)
class ReporteIncidenciaAdmin(admin.ModelAdmin):
    list_display = ('solicitud', 'tipo_incidencia', 'fecha_ocurrencia', 'representante_cliente', 'responsable_laboratorio')
    list_filter = ('tipo_incidencia', 'fecha_ocurrencia')
    search_fields = ('detalle_incidencia', 'solicitud__codigo_solicitud', 'representante_cliente')
    raw_id_fields = ['solicitud', 'responsable_laboratorio']
