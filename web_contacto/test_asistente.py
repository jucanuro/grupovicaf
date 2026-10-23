"""Pruebas del asistente de WhatsApp (specs/WEB, T2-T4)."""
from datetime import datetime
from decimal import Decimal
from unittest import mock
from zoneinfo import ZoneInfo

from django.core.cache import cache
from django.test import TestCase
from django.urls import reverse

from servicios.models import CategoriaServicio, Servicio
from siteconfig.models import NegocioConfig
from web_catalogo.models import LineaServicio, ServicioPublicado

from .asistente import saludo_para

LIMA = ZoneInfo('America/Lima')


def lima(hora, minuto=0):
    # 2026-10-14 es miércoles.
    return datetime(2026, 10, 14, hora, minuto, tzinfo=LIMA)


class SaludoTests(TestCase):
    def test_franjas_del_saludo(self):
        casos = {
            (4, 59): 'Buenas noches', (5, 0): 'Buenos días', (11, 59): 'Buenos días',
            (12, 0): 'Buenas tardes', (18, 59): 'Buenas tardes', (19, 0): 'Buenas noches',
            (0, 0): 'Buenas noches',
        }
        for (hora, minuto), esperado in casos.items():
            with self.subTest(hora=f'{hora}:{minuto:02d}'):
                self.assertEqual(saludo_para(lima(hora, minuto)), esperado)

    def test_saludo_en_hora_de_lima_aunque_llegue_en_utc(self):
        # 16:00 UTC = 11:00 en Lima.
        self.assertEqual(saludo_para(datetime(2026, 10, 14, 16, 0, tzinfo=ZoneInfo('UTC'))), 'Buenos días')


class AsistenteEndpointTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        categoria = CategoriaServicio.objects.create(nombre='Suelos asistente')
        cls.servicio = Servicio.objects.create(
            codigo_facturacion='ES-ASIST-1', nombre='CBR interno', precio_base=Decimal('150.00'),
            unidad_base='Ensayo', esta_acreditado=True,
        )
        cls.linea = LineaServicio.objects.create(
            slug='suelos-asistente', nombre='Mecánica de Suelos', titulo_h1='h1',
            resumen='Estudios de suelos.', contenido='c', orden=1,
        )
        cls.linea_vacia = LineaServicio.objects.create(
            slug='canteras-asistente', nombre='Canteras', titulo_h1='h1',
            resumen='Evaluación de canteras.', contenido='c', orden=2,
        )
        LineaServicio.objects.create(
            slug='inactiva-asistente', nombre='Inactiva', titulo_h1='h1', resumen='r', contenido='c', activo=False,
        )
        ServicioPublicado.objects.create(
            servicio=cls.servicio, categoria=categoria, linea=cls.linea, slug='ensayo-cbr-asistente',
            titulo_publico='Ensayo CBR', resumen='Capacidad de soporte.', contenido='c', activo=True,
        )
        ServicioPublicado.objects.create(
            servicio=None, categoria=categoria, linea=cls.linea, slug='oculto-asistente',
            titulo_publico='Oculto', resumen='r', contenido='c', activo=False,
        )

    def setUp(self):
        cache.clear()
        self.negocio = NegocioConfig.objects.get(pk=1)
        self.negocio.whatsapp = '+51964326364'
        self.negocio.save()
        self.url = reverse('web_contacto:asistente_datos')

    def _get(self, momento):
        with mock.patch('django.utils.timezone.now', return_value=momento):
            return self.client.get(self.url)

    def test_payload_con_saludo_horario_y_numero(self):
        respuesta = self._get(lima(10, 0))
        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(respuesta['Cache-Control'], 'no-store')
        datos = respuesta.json()
        self.assertEqual(datos['saludo'], 'Buenos días')
        self.assertTrue(datos['abierto'])
        self.assertEqual(datos['whatsapp'], '51964326364')
        self.assertEqual(
            datos['horario'], 'lunes a viernes de 8:00 a 13:00 y de 15:00 a 18:00, sábados de 8:00 a 13:00',
        )

    def test_fuera_de_horario(self):
        datos = self._get(lima(13, 30)).json()
        self.assertEqual(datos['saludo'], 'Buenas tardes')
        self.assertFalse(datos['abierto'])

    def test_catalogo_solo_publicado_y_en_orden(self):
        # Las migraciones ya siembran las 8 líneas comerciales; aquí solo se miran las del test.
        lineas = {l['url']: l for l in self._get(lima(10, 0)).json()['lineas']}
        self.assertNotIn('/servicios/inactiva-asistente/', lineas)
        suelos = lineas['/servicios/suelos-asistente/']
        self.assertEqual(suelos['nombre'], 'Mecánica de Suelos')
        self.assertEqual(suelos['ensayos'], [{
            'titulo': 'Ensayo CBR', 'resumen': 'Capacidad de soporte.', 'url': '/servicios/ensayo-cbr-asistente/',
        }])
        self.assertEqual(lineas['/servicios/canteras-asistente/']['ensayos'], [])
        self.assertEqual(set(suelos), {'nombre', 'resumen', 'url', 'ensayos'})

    def test_no_expone_campos_privados(self):
        cuerpo = self._get(lima(10, 0)).content.decode()
        for prohibido in ('150', 'ES-ASIST-1', 'CBR interno', 'precio', 'codigo', 'acreditado', 'Oculto'):
            self.assertNotIn(prohibido, cuerpo)

    def test_sin_whatsapp_responde_404(self):
        self.negocio.whatsapp = ''
        self.negocio.save()
        self.assertEqual(self.client.get(self.url).status_code, 404)

    def test_solo_get(self):
        self.assertEqual(self.client.post(self.url).status_code, 405)


class BotonEnTodasLasPaginasTests(TestCase):
    def setUp(self):
        self.negocio = NegocioConfig.objects.get(pk=1)
        self.negocio.whatsapp = '+51 964 326 364'
        self.negocio.save()

    def test_boton_una_vez_en_cada_pagina(self):
        for nombre in ('web_home', 'web_catalogo:servicios_list', 'web_contacto:contacto'):
            with self.subTest(pagina=nombre):
                html = self.client.get(reverse(nombre)).content.decode()
                self.assertEqual(html.count('data-asistente-wa'), 1)
                self.assertIn('href="https://wa.me/51964326364"', html)
                self.assertIn('web/js/asistente-whatsapp.js', html)

    def test_sin_whatsapp_no_hay_boton(self):
        self.negocio.whatsapp = ''
        self.negocio.save()
        html = self.client.get(reverse('web_catalogo:servicios_list')).content.decode()
        self.assertNotIn('data-asistente-wa', html)
