from django.urls import path

from . import views

# Sin namespace ni app_name: 'web_home' se usa sin prefijo en toda la base de
# plantillas (header.html, footer.html, base.html) desde antes de esta app.
urlpatterns = [
    path('', views.inicio_view, name='web_home'),
]
