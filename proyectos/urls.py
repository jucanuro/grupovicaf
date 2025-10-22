# proyectos/urls.py

from django.urls import path
from . import views

app_name = 'proyectos'

urlpatterns = [
  
    path('pendientes/', views.lista_proyectos_pendientes, name='lista_proyectos_pendientes'),
    
    path('crear-muestra/', views.crear_muestra, name='crear_muestra'), 
    path('muestras/<int:proyecto_id>/', views.muestras_del_proyecto, name='muestras_del_proyecto'),
    
   
]

