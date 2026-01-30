# proyectos/urls.py

from django.urls import path
from . import views

app_name = 'proyectos'

urlpatterns = [
  
     path('pendientes/', 
          views.lista_proyectos_pendientes, 
          name='lista_proyectos_pendientes'
     ),
     path('recepcion/<int:proyecto_id>/registrar/', 
         views.registrar_recepcion_lote, 
         name='registrar_recepcion_lote'),       
]

