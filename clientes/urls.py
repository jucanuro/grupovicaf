from django.urls import path
# Importamos las vistas que creamos en el archivo views.py
from .views import lista_clientes, crear_editar_cliente, confirmar_eliminar_cliente, buscar_clientes_api

app_name = 'clientes'

urlpatterns = [
    # 1. LISTADO DE CLIENTES (Ruta Raíz de la app)
    path('', lista_clientes, name='lista_clientes'),
    
    # 2. CREAR NUEVO CLIENTE
    path('crear/', crear_editar_cliente, name='crear_cliente'),
    
    # 3. EDITAR CLIENTE (Usamos PK para identificar el registro)
    path('editar/<int:pk>/', crear_editar_cliente, name='editar_cliente'),
    
    # 4. ELIMINAR CLIENTE (Usamos PK para identificar el registro y confirmar)
    path('eliminar/<int:pk>/', confirmar_eliminar_cliente, name='eliminar_cliente'),

    # 5. RUTA DE API PARA BÚSQUEDA RÁPIDA (Usada en el listado/autocompletado)
    path('buscar-api/', buscar_clientes_api, name='buscar_clientes_api'),
]