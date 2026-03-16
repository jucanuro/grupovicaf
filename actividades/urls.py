from django.urls import path
from . import views


app_name = 'actividades'

urlpatterns = [
    path('calendario/', views.dashboard_actividades  , name='calendario'),
]