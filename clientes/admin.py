from django.contrib import admin

from .models import Cliente


@admin.register(Cliente)
class ClienteAdmin(admin.ModelAdmin):
    """Registro mínimo requerido para que web_catalogo.ClienteDestacado
    pueda usar autocomplete_fields hacia Cliente (regla 8 de CLAUDE.md:
    publicar un cliente en la web es buscarlo aquí, nunca reescribirlo).
    """

    list_display = ('codigo_confidencial', 'razon_social', 'ruc', 'activo', 'creado_en')
    list_filter = ('activo',)
    search_fields = ('razon_social', 'ruc', 'codigo_confidencial')
    ordering = ('-creado_en',)
    readonly_fields = ('codigo_confidencial', 'creado_en', 'actualizado_en')
