from django.urls import path

from . import views

app_name = 'web_contacto'

urlpatterns = [
    path('', views.contacto_view, name='contacto'),
    path('cotizacion/', views.solicitud_cotizacion_view, name='solicitud_cotizacion'),
]
