"""Buscador acotado en el encabezado para las listas del LIMS.

Ver static/js/lista_buscador.js y templates/cabecera_base.html.

La vista solo tiene que exponer en el contexto:

    header_search = {'id': ..., 'placeholder': ...}
    query          = <término actual>   # para precargar el input

y filtrar su queryset por `request.GET.get('q')`. La plantilla marca el input
con [data-lista-buscador] y envuelve la tabla en
[data-lista-contenedor][data-lista-url="{% url ... %}"].

El JS re-consulta esa URL con `?q=` en vivo; si la vista devuelve la página
completa, el JS extrae el contenedor. Devolver solo el parcial de la tabla en
peticiones AJAX es una optimización opcional por página.
"""


class HeaderSearchMixin:
    """Para ListView: define `header_search = {'id', 'placeholder'}`."""

    header_search = None

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.setdefault("header_search", self.header_search)
        context.setdefault("query", self.request.GET.get("q", ""))
        return context
