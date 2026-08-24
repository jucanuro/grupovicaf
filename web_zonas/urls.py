from django.urls import path

from . import views

app_name = 'web_zonas'

urlpatterns = [
    path('zonas/', views.zonas_list_view, name='zonas_list'),
    path('zonas/<slug:slug>/', views.zona_detalle_view, name='zona_detalle'),
]
