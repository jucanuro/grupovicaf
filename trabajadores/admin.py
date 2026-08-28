from django.contrib import admin

from .models import TrabajadorProfile


@admin.register(TrabajadorProfile)
class TrabajadorProfileAdmin(admin.ModelAdmin):
    """Registro mínimo requerido para que web_catalogo.MiembroEquipoPublicado
    pueda usar autocomplete_fields hacia TrabajadorProfile (regla 8 de
    CLAUDE.md: publicar un miembro del equipo es buscarlo aquí, nunca
    reescribirlo).
    """

    list_display = ('nombre_completo', 'rol', 'titulo_profesional', 'creado_en')
    list_filter = ('rol',)
    search_fields = ('nombre_completo', 'user__username', 'correo_contacto')
    ordering = ('nombre_completo',)
    readonly_fields = ('creado_en', 'actualizado_en')
