from django.contrib import admin
from django.db import models
from django.forms import Textarea

from .models import (
    Proyecto,
    Muestra,
    TipoEnsayo,
    EnsayoParametro,      # Agregado
    SolicitudEnsayo,
    DetalleEnsayo,
    AsignacionTipoEnsayo,
    ResultadoEnsayo,
    ResultadoEnsayoValor,
    DocumentoFinal,
    ReporteIncidencia,
    TipoMuestra,
    Laboratorio,
)

# --- INLINES ---

class MuestraInline(admin.StackedInline):
    model = Muestra
    extra = 1
    raw_id_fields = ('tecnico_responsable_muestra',)


class DetalleEnsayoInline(admin.StackedInline):
    model = DetalleEnsayo
    extra = 0
    raw_id_fields = ('detalle_cotizacion', 'norma', 'metodo', 'firma_tecnico')

    fieldsets = (
        ('Ensayo', {
            'fields': (
                'tipo_ensayo_descripcion',
                ('norma', 'metodo'),
                'detalle_cotizacion',
            )
        }),
        ('Ejecución', {
            'fields': (
                ('fecha_limite_ejecucion', 'fecha_entrega_real'),
                ('estado_detalle', 'firma_tecnico'),
                'observaciones_detalle',
            )
        }),
    )


class EnsayoParametroInline(admin.TabularInline):
    """Permite configurar parámetros directamente desde el Tipo de Ensayo"""
    model = EnsayoParametro
    extra = 1
    fields = ('nombre', 'unidad', 'es_numerico', 'orden')


class ResultadoEnsayoValorInline(admin.TabularInline):
    model = ResultadoEnsayoValor
    extra = 0
    can_delete = False
    readonly_fields = ('parametro',)
    fields = ('parametro', 'valor_numerico', 'valor_texto', 'cumple')


class ReporteIncidenciaInline(admin.StackedInline):
    model = ReporteIncidencia
    extra = 0
    raw_id_fields = ('responsable_laboratorio',)


class DocumentoFinalInline(admin.StackedInline):
    model = DocumentoFinal
    max_num = 1
    can_delete = False


# --- CONFIGURACIONES ADMIN (CATÁLOGOS) ---

@admin.register(Laboratorio)
class LaboratorioAdmin(admin.ModelAdmin):
    list_display = ('nombre',)


@admin.register(TipoMuestra)
class TipoMuestraAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'prefijo_codigo')


@admin.register(TipoEnsayo)
class TipoEnsayoAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'codigo_interno')
    search_fields = ('nombre', 'codigo_interno')
    inlines = [EnsayoParametroInline]


@admin.register(EnsayoParametro)
class EnsayoParametroAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'tipo_ensayo', 'unidad', 'es_numerico', 'orden')
    list_filter = ('tipo_ensayo', 'es_numerico')
    search_fields = ('nombre', 'tipo_ensayo__nombre')


# --- CONFIGURACIONES ADMIN (PROCESOS OPERATIVOS) ---

@admin.register(Proyecto)
class ProyectoAdmin(admin.ModelAdmin):
    list_display = ('codigo_proyecto', 'nombre_proyecto', 'cliente', 'estado')
    raw_id_fields = ('cliente', 'cotizacion')
    inlines = [MuestraInline, DocumentoFinalInline]


@admin.register(Muestra)
class MuestraAdmin(admin.ModelAdmin):
    list_display = ('codigo_muestra', 'proyecto', 'estado')
    raw_id_fields = ('proyecto', 'tecnico_responsable_muestra')
    search_fields = ('codigo_muestra', 'proyecto__nombre_proyecto')


@admin.register(SolicitudEnsayo)
class SolicitudEnsayoAdmin(admin.ModelAdmin):
    list_display = ('codigo_solicitud', 'muestra', 'estado', 'fecha_solicitud')
    raw_id_fields = ('muestra', 'generada_por', 'firma_jefe_laboratorio')
    readonly_fields = ('estado', 'fecha_solicitud', 'cotizacion')
    inlines = [DetalleEnsayoInline, ReporteIncidenciaInline]


@admin.register(DetalleEnsayo)
class DetalleEnsayoAdmin(admin.ModelAdmin):
    list_display = ('solicitud', 'tipo_ensayo_descripcion', 'estado_detalle')
    raw_id_fields = ('solicitud', 'detalle_cotizacion', 'norma', 'metodo', 'firma_tecnico')
    search_fields = ('solicitud__codigo_solicitud', 'tipo_ensayo_descripcion')


@admin.register(ResultadoEnsayo)
class ResultadoEnsayoAdmin(admin.ModelAdmin):
    inlines = [ResultadoEnsayoValorInline]

    list_display = (
        'detalle_ensayo',
        'tipo_ensayo',
        'estado',
        'tecnico_ejecutor',
        'fecha_inicio_ensayo',
    )

    list_filter = ('estado', 'es_reensayo', 'tipo_ensayo')

    raw_id_fields = (
        'detalle_ensayo',
        'tecnico_ejecutor',
        'supervisor_revisor',
        'norma_aplicada',
        'metodo_aplicado',
        'resultado_origen',
    )

    formfield_overrides = {
        models.JSONField: {'widget': Textarea(attrs={'rows': 6, 'cols': 90})},
        models.TextField: {'widget': Textarea(attrs={'rows': 3, 'cols': 90})},
    }


@admin.register(ResultadoEnsayoValor)
class ResultadoEnsayoValorAdmin(admin.ModelAdmin):
    list_display = ('resultado', 'parametro', 'valor_numerico', 'cumple')
    readonly_fields = ('resultado', 'parametro')


@admin.register(DocumentoFinal)
class DocumentoFinalAdmin(admin.ModelAdmin):
    list_display = ('proyecto', 'titulo', 'fecha_emision')
    raw_id_fields = ('proyecto',)


@admin.register(ReporteIncidencia)
class ReporteIncidenciaAdmin(admin.ModelAdmin):
    list_display = ('solicitud', 'tipo_incidencia', 'fecha_ocurrencia')
    raw_id_fields = ('solicitud', 'responsable_laboratorio')