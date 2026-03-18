import os
from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse

@login_required
def dashboard_actividades(request):
    return render(request, 'actividades/calendario_actividades.html')