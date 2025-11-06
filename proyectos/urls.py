# proyectos/urls.py

from django.urls import path
from . import views

app_name = 'proyectos'

urlpatterns = [
  
    path('pendientes/', views.lista_proyectos_pendientes, name='lista_proyectos_pendientes'),
    
    path('crear-muestra/', views.crear_muestra, name='crear_muestra'), 
    path('muestras/<int:proyecto_id>/', views.muestras_del_proyecto, name='muestras_del_proyecto'),
    
    path('solicitudes/iniciar/<int:muestra_id>/', views.generar_o_redirigir_solicitud, name='iniciar_registro_solicitud'),
    path('solicitudes/registro/<int:solicitud_id>/', views.pagina_registro_solicitud, name='pagina_registro_solicitud'),
    path('solicitudes/actualizar-anidada/<int:solicitud_id>/', views.actualizar_solicitud_y_detalles, name='actualizar_solicitud_detalles'),
]

