from django.urls import path
from . import views
from .views import lista_clientes, crear_editar_cliente, confirmar_eliminar_cliente, buscar_clientes_api

app_name = 'clientes'

urlpatterns = [
    path('', lista_clientes, name='lista_clientes'),
    
    path('crear/', crear_editar_cliente, name='crear_cliente'),
    
    path('editar/<int:pk>/', crear_editar_cliente, name='editar_cliente'),
    
    path('eliminar/<int:pk>/', confirmar_eliminar_cliente, name='eliminar_cliente'),

    path('buscar-api/', buscar_clientes_api, name='buscar_clientes_api'),
    
    path('crear-ajax/', views.crear_cliente_ajax, name='crear_cliente_ajax'),
]