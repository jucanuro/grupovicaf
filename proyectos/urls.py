# proyectos/urls.py

from django.urls import path
from . import views

app_name = 'proyectos'

urlpatterns = [
    
     path('pendientes/', 
          views.lista_proyectos_pendientes, 
          name='lista_proyectos_pendientes'
     ),
     
     path('recepcion/nueva/<int:proyecto_id>/', 
          views.gestionar_recepcion_muestra, 
          name='crear_recepcion_desde_proyecto'),
     
     path('recepcion/nueva/', 
          views.gestionar_recepcion_muestra, 
          name='crear_recepcion'
    ),
     path('recepcion/editar/<int:pk>/', 
          views.gestionar_recepcion_muestra, 
          name='editar_recepcion'
     ),
     
     path('recepcion/<int:recepcion_id>/muestras/', views.lista_muestras_recepcion, name='lista_muestras_recepcion'),
     
     path('recepcion/<int:recepcion_id>/pdf/', views.generar_pdf_recepcion, name='generar_pdf_recepcion'),

     path('recepciones/', 
          views.RecepcionMuestraListView.as_view(), 
          name='lista_recepciones'
    ),
     
     path('tipo-muestra/crear-ajax/', views.crear_tipo_muestra_ajax, name='crear_tipo_muestra_ajax'),
     
     path('recepcion/<int:recepcion_id>/whatsapp/', 
          views.generar_y_enviar_whatsapp, 
          name='enviar_recepcion_whatsapp'
     ),
     
     
     path('api/cotizacion-detalles/<int:cotizacion_id>/', views.api_obtener_detalles_cotizacion, name='api_cotizacion_detalles'),
     path('solicitudes/', views.lista_solicitudes, name='lista_solicitudes'),
     path('ensayo/nuevo/', views.gestionar_solicitud_ensayo, name='crear_solicitud'),
     path('ensayo/editar/<int:pk>/', views.gestionar_solicitud_ensayo, name='editar_solicitud'),
     path('solicitudes/estado/<int:pk>/<str:nuevo_estado>/', views.cambiar_estado_solicitud, name='cambiar_estado'),
     path('ensayo/<int:solicitud_id>/pdf/', views.generar_pdf_ensayo, name='generar_pdf_ensayo'),
]

