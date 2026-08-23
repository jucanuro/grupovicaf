from django.urls import path

from . import views

app_name = 'web_catalogo'

urlpatterns = [
    path('servicios/', views.servicios_list_view, name='servicios_list'),
    path('servicios/<slug:slug>/', views.servicio_detalle_view, name='servicio_detalle'),
    path('clientes/', views.clientes_list_view, name='clientes_list'),
    path('equipo/', views.equipo_list_view, name='equipo_list'),
]
