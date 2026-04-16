from django.contrib import admin
from .models import TipoMuestra, UnidadMedida


@admin.register(TipoMuestra)
class TipoMuestraAdmin(admin.ModelAdmin):
    list_display = ('sigla', 'nombre')
    search_fields = ('sigla', 'nombre')
    ordering = ('sigla',)


@admin.register(UnidadMedida)
class UnidadMedidaAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'codigo', 'activo')
    search_fields = ('nombre', 'codigo')
    list_filter = ('activo',)
    ordering = ('codigo',)