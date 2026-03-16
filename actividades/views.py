import os
from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build
from django.http import JsonResponse



SCOPES = ['https://www.googleapis.com/auth/calendar.readonly']
CLIENT_SECRETS_FILE = 'credentials.json'

@login_required
def dashboard_actividades(request):
    flow = Flow.from_client_secrets_file(
        CLIENT_SECRETS_FILE,
        scopes=SCOPES,
        redirect_uri='http://localhost:8000/actividades/calendario/'
    )

    if 'credentials' in request.session:
        return render(request, 'actividades/calendario_actividades.html')

    if 'code' in request.GET:
        flow.fetch_token(code=request.GET.get('code'))
        request.session['credentials'] = flow.credentials.to_json()
        return redirect('calendario_actividades')

    authorization_url, state = flow.authorization_url(
        access_type='offline',
        include_granted_scopes='true'
    )
    
    return redirect(authorization_url)


def api_eventos(request):
    eventos = [
        {
            'title': 'Ensayo de Concreto C-20',
            'start': '2026-03-12T10:00:00',
            'end': '2026-03-12T12:00:00',
            'className': 'event-vicaf'
        }
    ]
    return JsonResponse(eventos, safe=False)