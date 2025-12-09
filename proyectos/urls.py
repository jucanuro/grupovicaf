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

    
]

