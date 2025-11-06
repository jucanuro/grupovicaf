from django.urls import path
from . import views
from .views import generar_pdf_cotizacion

app_name = 'servicios'

urlpatterns = [
    # Rutas para la gestión de SERVICIOS (CRUD)
    
    path('', views.lista_servicios, name='lista_servicios'),
    
    # Se utiliza la vista única 'crear_editar_servicio'
    path('crear/', views.crear_editar_servicio, name='crear_servicio'),
    path('editar/<int:pk>/', views.crear_editar_servicio, name='editar_servicio'),
    
    path('eliminar/<int:pk>/', views.eliminar_servicio, name='eliminar_servicio'),

    # Rutas para la gestión de COTIZACIONES (CRUD y Negocio)
    
    path('cotizaciones/', views.lista_cotizaciones, name='lista_cotizaciones'),
    
    # Se utilizan los alias 'crear_cotizacion' y 'editar_cotizacion' que apuntan 
    # a la vista única 'crear_editar_cotizacion' en views.py
    path('cotizaciones/crear/', views.crear_cotizacion, name='crear_cotizacion'),
    path('cotizaciones/editar/<int:pk>/', views.editar_cotizacion, name='editar_cotizacion'),
    
    # Detalle y Operaciones
    path('cotizaciones/detalle/<int:pk>/', views.detalle_cotizacion, name='detalle_cotizacion'),
    path('cotizaciones/eliminar/<int:pk>/', views.eliminar_cotizacion, name='eliminar_cotizacion'),
    
    # Funcionalidades Clave de Negocio
    path('cotizaciones/<int:pk>/pdf/', views.generar_pdf_cotizacion, name='ver_pdf_cotizacion'),
    path('cotizaciones/<int:pk>/aprobar/', views.aprobar_cotizacion, name='aprobar_cotizacion'), 

    # APIs para Servicios y Cotizaciones
    
    # API de Servicios: Detalle (para modales)
    path('api/ver/<int:pk>/', views.obtener_detalle_servicio_api, name='obtener_detalle_servicio_api'),
    
    # API de Servicios: Búsqueda (para autocompletado en Cotizaciones)
    path('api/buscar/', views.buscar_servicios_api, name='buscar_servicios_api'),

    # API de Cotizaciones: Búsqueda dinámica
    path('cotizaciones/api/buscar/', views.buscar_cotizaciones_api, name='buscar_cotizaciones_api'),
    
    # API para obtener el detalle de un servicio específicamente para el formulario de cotización
    # NOTA: Esta ruta usa el nombre (name) que solicitaste, mapeado a la vista funcional: obtener_detalle_servicio_api
    path(
        'cotizaciones/api/servicios/<int:pk>/', 
        views.obtener_detalle_servicio_api, 
        name='obtener_detalle_servicio_para_cotizacion_api'
    ),
    path(
        'api/detalle/<int:pk>/', 
        views.obtener_datos_servicio_json, 
        name='servicio_detalle_api'
    ),
]