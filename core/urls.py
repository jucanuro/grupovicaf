from django.urls import path
from . import views
from django.contrib.auth import views as auth_views
from django.contrib.auth.decorators import login_required

urlpatterns = [
    path('', views.CoreLoginView.as_view(), name='login'),
    path('logout/', auth_views.LogoutView.as_view(), name='logout'),
    path('cuenta/clave/', login_required(views.CambiarClaveView.as_view()), name='cambiar_clave'),
    path('dashboard/', views.dashboard_view, name='dashboard'),
    path('administracion/', views.dashboard_view_analitycs, name='administracion'),
]
