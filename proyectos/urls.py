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
     
     path('recepciones/', 
         views.RecepcionMuestraListView.as_view(), 
         name='lista_recepciones'
    ),
     
     path('tipo-muestra/crear-ajax/', views.crear_tipo_muestra_ajax, name='crear_tipo_muestra_ajax'),
     
       
]

