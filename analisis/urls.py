from django.urls import path

from . import views

app_name = 'analisis'

urlpatterns = [
    path('', views.analisis_view, name='analisis'),
    path('datos/<slug:clave>/', views.datos_view, name='datos'),
    path('vistas/', views.vistas_view, name='vistas'),
    path('vistas/<int:pk>/eliminar/', views.eliminar_vista_view, name='eliminar_vista'),
]
