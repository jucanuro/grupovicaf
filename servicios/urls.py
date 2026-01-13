from django.urls import path
from . import views
from .views import generar_pdf_cotizacion

app_name = 'servicios'

urlpatterns = [
    # Rutas para la gestión de SERVICIOS (CRUD)
    
    path('', views.lista_servicios, name='lista_servicios'),
    
    path('crear/', views.crear_editar_servicio, name='crear_servicio'),
    path('editar/<int:pk>/', views.crear_editar_servicio, name='editar_servicio'),
    
    path('eliminar/<int:pk>/', views.eliminar_servicio, name='eliminar_servicio'),

    
    path('cotizaciones/', views.lista_cotizaciones, name='lista_cotizaciones'),
    
    path('cotizaciones/crear/', views.crear_cotizacion, name='crear_cotizacion'),
    path('cotizaciones/editar/<int:pk>/', views.editar_cotizacion, name='editar_cotizacion'),
    
    path('cotizaciones/detalle/<int:pk>/', views.detalle_cotizacion, name='detalle_cotizacion'),
    path('cotizaciones/eliminar/<int:pk>/', views.eliminar_cotizacion, name='eliminar_cotizacion'),
    
    path('cotizaciones/<int:pk>/pdf/', views.generar_pdf_cotizacion, name='ver_pdf_cotizacion'),
    path('cotizaciones/<int:pk>/aprobar/', views.aprobar_cotizacion, name='aprobar_cotizacion'), 

    
    path('api/ver/<int:pk>/', views.obtener_detalle_servicio_api, name='obtener_detalle_servicio_api'),
    
    path('api/buscar/', views.buscar_servicios_api, name='buscar_servicios_api'),


    path('cotizaciones/api/buscar/', views.buscar_cotizaciones_api, name='buscar_cotizaciones_api'),
    
    path(
        'cotizaciones/api/servicios/<int:pk>/', 
        views.obtener_detalle_servicio_api, 
        name='obtener_detalle_servicio_para_cotizacion_api'
    ),
]