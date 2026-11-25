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

from django import forms as _forms
from .models import PlantillaFormulario


class PlantillaFormularioForm(_forms.ModelForm):
    class Meta:
        model = PlantillaFormulario
        fields = '__all__'
        widgets = {'campos': _forms.Textarea(attrs={'rows': 18, 'style': 'font-family: monospace; width: 100%'})}


EJEMPLO_CAMPOS = (
    '[{"clave": "humedad", "etiqueta": "Contenido de humedad", "tipo": "numero", "unidad": "%", '
    '"requerido": true, "grupo": "Resultados"}, '
    '{"clave": "cumple_secado", "etiqueta": "Secado a masa constante", "tipo": "cumple", "grupo": "Verificaciones"}]'
)


@admin.register(PlantillaFormulario)
class PlantillaFormularioAdmin(admin.ModelAdmin):
    """Formulario de resultados por servicio: los campos del formato en papel, sin programar."""
    form = PlantillaFormularioForm
    list_display = ('nombre', 'activo', 'total_campos', 'actualizado_en')
    list_filter = ('activo',)
    search_fields = ('nombre', 'servicios__nombre', 'servicios__codigo_facturacion')
    filter_horizontal = ('servicios',)
    fieldsets = (
        (None, {'fields': ('nombre', 'activo', 'servicios', 'instrucciones')}),
        ('Campos del formulario', {
            'fields': ('campos',),
            'description': ('Lista JSON de campos. Tipos: numero, texto, texto_largo, fecha, si_no, cumple, seleccion '
                            '(con «opciones»). Ejemplo: ' + EJEMPLO_CAMPOS),
        }),
    )

    @admin.display(description='Campos')
    def total_campos(self, obj):
        return len(obj.campos or [])
