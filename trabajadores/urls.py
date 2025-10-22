from django.urls import path
from .views import (
    lista_trabajadores,
    buscar_trabajadores_api,
    crear_trabajador,
    editar_trabajador,
    eliminar_trabajador,
)

app_name = 'trabajadores'

urlpatterns = [
    # Gestión de la lista de trabajadores
    path('', lista_trabajadores, name='lista_trabajadores'),
    
    # API para búsqueda asíncrona
    path('api/buscar/', buscar_trabajadores_api, name='buscar_trabajadores_api'),

    # Vistas de CRUD
    path('crear/', crear_trabajador, name='crear_trabajador'),
    path('editar/<int:pk>/', editar_trabajador, name='editar_trabajador'),
    path('eliminar/<int:pk>/', eliminar_trabajador, name='eliminar_trabajador'),
]