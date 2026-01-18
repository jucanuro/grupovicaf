from django.urls import path
from .views import (
    lista_trabajadores,
    buscar_trabajadores_api,
    crear_trabajador,
    editar_trabajador,
    eliminar_trabajador,
    crear_rol_ajax,
    lista_roles,
    crear_rol,
    editar_rol,
    eliminar_rol
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
    path('roles/crear-ajax/', crear_rol_ajax, name='crear_rol_ajax'),
    path('roles/', lista_roles, name='lista_roles'),
    path('roles/crear/', crear_rol, name='crear_rol'),
    path('roles/editar/<int:pk>/', editar_rol, name='editar_rol'),
    path('roles/eliminar/<int:pk>/', eliminar_rol, name='eliminar_rol'),
]