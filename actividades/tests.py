import json
from datetime import timedelta

from django.conf import settings
from django.test import Client, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from clientes.models import Cliente
from trabajadores.testing import crear_trabajador, rol_con_permisos

from .models import CalendarioActividad


@override_settings(ROOT_URLCONF='grupovicaf.urls_lab')
class GuardarActividadTest(TestCase):
    """El calendario no guardaba: el JS mandaba la cookie «csrftoken», que no
    existe (se llama gv_<rol>_csrftoken), y el 403 se perdía en silencio."""

    @classmethod
    def setUpTestData(cls):
        rol = rol_con_permisos('Agenda', 'calendario.ver', 'calendario.crear', 'calendario.editar')
        cls.user, _ = crear_trabajador('agenda', rol)
        cls.cliente = Cliente.objects.create(ruc='20111111111', razon_social='Cliente Agenda SAC')

    def payload(self, **cambios):
        inicio = timezone.now().replace(microsecond=0) + timedelta(hours=1)
        datos = {
            'titulo': 'Reunión con cliente',
            'clase': 'REUNION',
            'estado': 'PROGRAMADA',
            'prioridad': 'MEDIA',
            'fecha_inicio': inicio.isoformat(),
            'fecha_fin': (inicio + timedelta(hours=1)).isoformat(),
            'cliente_id': self.cliente.pk,
            'recordatorios': [{'minutos_antes': '30', 'tipo': 'APP'}],
        }
        datos.update(cambios)
        return datos

    def guardar(self, datos, client=None, token=None):
        client = client or self.client
        headers = {'HTTP_X_CSRFTOKEN': token} if token else {}
        return client.post(
            reverse('actividades:calendario_actividad_guardar_json'),
            data=json.dumps(datos), content_type='application/json', **headers,
        )

    def test_la_pagina_entrega_el_token_y_no_lee_la_cookie_csrftoken(self):
        self.client.force_login(self.user)
        html = self.client.get(reverse('actividades:calendario_dashboard')).content.decode()
        self.assertIn('const CSRF_TOKEN = ', html)
        self.assertNotIn("getCookie('csrftoken')", html)
        self.assertIn('novalidate', html)

    def test_guarda_con_el_token_de_la_pagina_y_csrf_activo(self):
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.user)
        client.get(reverse('actividades:calendario_dashboard'))
        token = client.cookies[settings.CSRF_COOKIE_NAME].value
        sin_token = self.guardar(self.payload(), client=client)
        self.assertEqual(sin_token.status_code, 403)
        resp = self.guardar(self.payload(), client=client, token=token)
        self.assertEqual(resp.status_code, 200, resp.content)
        self.assertTrue(resp.json()['success'])
        actividad = CalendarioActividad.objects.get(pk=resp.json()['id'])
        self.assertEqual(actividad.recordatorios.count(), 1)

    def test_tras_el_aviso_de_cliente_faltante_se_puede_guardar(self):
        self.client.force_login(self.user)
        falta = self.guardar(self.payload(cliente_id=None))
        self.assertEqual(falta.status_code, 400)
        self.assertIn('cliente', falta.json()['error'])
        ok = self.guardar(self.payload())
        self.assertEqual(ok.status_code, 200, ok.content)
        self.assertEqual(CalendarioActividad.objects.count(), 1)

    def test_valida_fechas_y_opciones_sin_guardar_a_medias(self):
        self.client.force_login(self.user)
        p = self.payload()
        invertidas = self.guardar(self.payload(fecha_inicio=p['fecha_fin'], fecha_fin=p['fecha_inicio']))
        self.assertEqual(invertidas.status_code, 400)
        self.assertEqual(self.guardar(self.payload(clase='INVENTADA')).status_code, 400)
        malos = self.guardar(self.payload(recordatorios=[{'minutos_antes': 'diez'}]))
        self.assertEqual(malos.status_code, 400)
        self.assertEqual(CalendarioActividad.objects.count(), 0)
