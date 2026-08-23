from django.urls import path

from . import views

app_name = 'web_acreditacion'

urlpatterns = [
    path('', views.acreditacion_view, name='acreditacion'),
]
