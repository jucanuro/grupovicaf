from django.urls import path

from . import views

app_name = 'correo'

urlpatterns = [
    path('abrir/', views.abrir, name='abrir'),
]
