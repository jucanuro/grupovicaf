from django.urls import path

from . import views

app_name = 'web_nosotros'

urlpatterns = [
    path('', views.nosotros_view, name='nosotros'),
]
