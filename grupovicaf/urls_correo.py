"""URLconf del host del correo (email.<dominio>).

Lo activa correo.middleware.CorreoHostMiddleware en el rol 'lab'. No incluye
admin/ ni ninguna ruta del LIMS.
"""
from django.urls import path

from correo import views_correo

urlpatterns = [
    path('', views_correo.bandeja, name='bandeja'),
    path('c/<slug:cuenta>/bandeja/', views_correo.bandeja, name='bandeja_cuenta'),
    path('entrar/', views_correo.entrar, name='entrar'),
    path('login/', views_correo.ir_al_login, name='login'),
    path('salir/', views_correo.salir, name='salir'),
]
