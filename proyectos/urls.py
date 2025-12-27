# proyectos/urls.py

from django.urls import path
from . import views

app_name = 'proyectos'

urlpatterns = [
  
     path('pendientes/', 
          views.lista_proyectos_pendientes, 
          name='lista_proyectos_pendientes'
     ),

     path('proyectos/<int:pk>/gestion_muestras/<int:muestra_pk>/', 
          views.ProyectoMuestraGestionView.as_view(),
          name='gestion_muestras_proyecto'), 
    
     path('proyectos/<int:pk>/gestion_muestras/', 
          views.ProyectoMuestraGestionView.as_view(), 
          name='gestion_muestras_proyecto'), 
    
     path('muestra/<int:muestra_pk>/solicitud/gestion/', 
          views.GestionSolicitudEnsayoView.as_view(), 
          name='gestion_solicitud_ensayo'),
    
    
     path('solicitudes/lista/', 
     views.ListaSolicitudesEnsayoView.as_view(), 
     name='lista_solicitudes_ensayo'),

     path('solicitudes/lista/<int:muestra_pk>/', 
          views.ListaSolicitudesEnsayoView.as_view(), 
          name='lista_solicitudes_ensayo_por_muestra'),
          
     path('solicitudes/lista/<int:muestra_pk>/', views.ListaSolicitudesEnsayoView.as_view(), name='lista_solicitudes_ensayo'),
     
     path('muestra/<int:muestra_pk>/solicitudes/editar/<int:solicitud_pk>/', 
          views.GestionSolicitudEnsayoView.as_view(), 
          name='gestion_solicitud_ensayo_editar'),
          
     path('solicitudes/<int:pk>/pdf/', views.generar_pdf_solicitud_ensayo, name='ver_pdf_solicitud_ensayo'),
     
     path('resultados/', views.listar_resultado_ensayo, name='lista_resultados_ensayo'),
     
     path('ensayo/registrar/', views.registrar_resultado_ensayo, name='registrar_resultado_ensayo'),
          
]

