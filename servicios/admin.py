from django.contrib import admin
from .models import (
    CategoriaServicio,
    Subcategoria,
    Norma,
    Metodo,
    CatalogoCondicionSeccion,
    CatalogoCondicionItem,
)


@admin.register(CategoriaServicio)
class CategoriaServicioAdmin(admin.ModelAdmin):
    list_display = ('nombre',)
    search_fields = ('nombre',)
    ordering = ('nombre',)


@admin.register(Subcategoria)
class SubcategoriaAdmin(admin.ModelAdmin):
    list_display = ('nombre',)
    search_fields = ('nombre',)
    ordering = ('nombre',)


@admin.register(Norma)
class NormaAdmin(admin.ModelAdmin):
    list_display = ('codigo', 'nombre')
    search_fields = ('codigo', 'nombre')
    ordering = ('codigo',)


@admin.register(Metodo)
class MetodoAdmin(admin.ModelAdmin):
    list_display = ('codigo', 'nombre')
    search_fields = ('codigo', 'nombre')
    ordering = ('codigo',)


@admin.register(CatalogoCondicionSeccion)
class CatalogoCondicionSeccionAdmin(admin.ModelAdmin):
    list_display = (
        'orden',
        'codigo',
        'titulo',
        'tipo',
        'es_obligatoria',
        'activo',
    )
    list_editable = (
        'titulo',
        'tipo',
        'es_obligatoria',
        'activo',
    )
    list_filter = (
        'tipo',
        'activo',
        'es_obligatoria',
    )
    search_fields = (
        'codigo',
        'titulo',
    )
    ordering = (
        'orden',
        'id',
    )
    list_per_page = 50


@admin.register(CatalogoCondicionItem)
class CatalogoCondicionItemAdmin(admin.ModelAdmin):
    list_display = (
        'id',
        'seccion',
        'tipo_nodo',
        'titulo_corto',
        'orden',
        'nivel',
        'seleccionado_por_defecto',
        'es_obligatorio',
        'editable_en_cotizacion',
        'activo',
    )
    list_filter = (
        'seccion',
        'tipo_nodo',
        'activo',
        'es_obligatorio',
        'editable_en_cotizacion',
        'seleccionado_por_defecto',
    )
    search_fields = (
        'titulo',
        'texto',
        'seccion__titulo',
        'seccion__codigo',
    )
    ordering = (
        'seccion__orden',
        'orden',
        'id',
    )
    autocomplete_fields = (
        'seccion',
    )
    list_per_page = 100

    fieldsets = (
        ('Relación y estructura', {
            'fields': (
                'seccion',
                'tipo_nodo',
                'nivel',
                'orden',
            )
        }),
        ('Contenido', {
            'fields': (
                'titulo',
                'texto',
            )
        }),
        ('Configuración', {
            'fields': (
                'activo',
                'seleccionado_por_defecto',
                'editable_en_cotizacion',
                'es_obligatorio',
            )
        }),
    )

    def titulo_corto(self, obj):
        if obj.titulo:
            return obj.titulo
        return (obj.texto[:60] + '...') if len(obj.texto) > 60 else obj.texto

    titulo_corto.short_description = 'Título / Texto'