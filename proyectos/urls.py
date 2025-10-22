# proyectos/urls.py

from django.urls import path
from . import views

app_name = 'proyectos'

urlpatterns = [
    # -------------------------------------------------------------
    # Rutas de Gestión de Proyectos (Existentes)
    # -------------------------------------------------------------
    path('', views.lista_proyectos, name='lista_proyectos'),
    path('crear/', views.crear_proyecto, name='crear_proyecto'),
    path('<int:pk>/editar/', views.editar_proyecto, name='editar_proyecto'),
    path('<int:pk>/eliminar/', views.eliminar_proyecto, name='eliminar_proyecto'),
    path('pendientes/', views.lista_proyectos_pendientes, name='lista_proyectos_pendientes'),
    
    # RUTA DE API/AJAX para edición de la tabla
    path('editar/<int:pk>/', views.editar_proyecto_view, name='editar_proyecto_api'),
    
    # RUTA AÑADIDA para resolver la referencia pendiente
    path('<int:pk>/', views.detalle_proyecto, name='detalle_proyecto'), 

    # ✅ CORRECCIÓN FINAL DE LA LÍNEA 25: Apuntando a views.crear_muestra
    path('crear-muestra/', views.crear_muestra, name='crear_muestra'), 
    path('muestras/<int:proyecto_id>/', views.muestras_del_proyecto, name='muestras_del_proyecto'),
    
    # RUTA AÑADIDA para resolver la referencia pendiente
    path('generar-ordenes/', views.generar_ordenes_de_ensayo, name='generar_ordenes_de_ensayo'),
    
    path('ordenes/registrar/<int:orden_id>/', views.orden_de_ensayo_form, name='orden_ensayo_form'), 
    path('documento/<int:pk>/', views.orden_de_ensayo_documento, name='orden_ensayo_documento'),
    path('resultados/registrar/<int:muestra_pk>/', views.registro_resultado_form, name='registro_resultado_form'),
]