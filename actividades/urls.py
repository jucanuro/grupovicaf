from django.urls import path
from . import views

app_name = 'actividades'

urlpatterns = [
    path('calendario/', views.calendario_dashboard, name='calendario_dashboard'),
    path('calendario/eventos/', views.calendario_eventos_json, name='calendario_eventos_json'),
    path('calendario/evento/<int:pk>/', views.calendario_actividad_detalle_json, name='calendario_actividad_detalle_json'),
    path('calendario/evento/guardar/', views.calendario_actividad_guardar_json, name='calendario_actividad_guardar_json'),
    path('calendario/evento/<int:pk>/eliminar/', views.calendario_actividad_eliminar_json, name='calendario_actividad_eliminar_json'),
    path('calendario/categoria/crear/', views.calendario_categoria_crear_json, name='calendario_categoria_crear_json'),
    path('calendario/evento/<int:pk>/reprogramar/', views.calendario_actividad_reprogramar_json, name='calendario_actividad_reprogramar_json'),
    path('gantt/', views.gantt_dashboard, name='gantt_dashboard'),
    path('gantt/json/', views.gantt_actividades_json, name='gantt_actividades_json'),
]