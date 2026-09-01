from decimal import Decimal

from django.core.cache import cache
from django.test import TestCase
from django.urls import reverse

from clientes.models import Cliente
from servicios.models import CategoriaServicio, Cotizacion, Servicio
from web_catalogo.models import LineaServicio, ServicioPublicado

from .models import MensajeContacto, SolicitudCotizacionWeb
from .utils import RATE_LIMIT_MAX_INTENTOS


class SolicitudCotizacionTestCase(TestCase):
    @classmethod
    def setUpTestData(cls):
        categoria = CategoriaServicio.objects.create(nombre='Suelos')
        cls.servicio = Servicio.objects.create(
            codigo_facturacion='ES011-TEST', nombre='CBR', precio_base=Decimal('150.00'), unidad_base='Ensayo',
        )
        cls.publicado = ServicioPublicado.objects.create(
            servicio=cls.servicio, categoria=categoria, slug='ensayo-cbr-test',
            titulo_publico='Ensayo CBR', resumen='r', contenido='c', activo=True,
        )
        # ServicioPublicado sin vínculo al LIMS: nunca debe poder cotizarse desde la web.
        cls.publicado_sin_servicio = ServicioPublicado.objects.create(
            servicio=None, categoria=categoria, slug='sin-servicio-test',
            titulo_publico='Sin vínculo LIMS', resumen='r', contenido='c', activo=True,
        )
    def setUp(self):
        cache.clear()

    def _datos_validos(self, **overrides):
        datos = {
            'ruc': '20123456789',
            'razon_social': 'Constructora Test SAC',
            'persona_contacto': 'Juan Perez',
            'correo_contacto': 'juan@example.com',
            'telefono_contacto': '999999999',
            'necesidad': 'Necesito CBR para un proyecto vial.',
            'servicios': [self.publicado.slug],
            f'cantidad_{self.publicado.slug}': '2',
            'origen': '/servicios/ensayo-cbr-test/',
        }
        datos.update(overrides)
        return datos

    def test_envio_crea_cliente_cotizacion_y_detalle(self):
        response = self.client.post(
            reverse('web_contacto:solicitud_cotizacion'), self._datos_validos(), follow=True,
        )
        self.assertEqual(response.status_code, 200)

        cliente = Cliente.objects.get(ruc='20123456789')
        self.assertEqual(cliente.origen, 'web')
        self.assertFalse(cliente.activo)
        self.assertIsNone(cliente.creado_por)

        solicitud = SolicitudCotizacionWeb.objects.get(ruc='20123456789')
        self.assertEqual(solicitud.cliente, cliente)
        self.assertIsNotNone(solicitud.cotizacion)
        self.assertEqual(solicitud.origen, '/servicios/ensayo-cbr-test/')

        cotizacion = solicitud.cotizacion
        self.assertEqual(cotizacion.estado, 'Pendiente')
        self.assertEqual(cotizacion.cliente, cliente)

        detalles = list(cotizacion.detalles_cotizacion)
        self.assertEqual(len(detalles), 1)
        self.assertEqual(detalles[0].servicio, self.servicio)
        self.assertEqual(detalles[0].cantidad, 2)
        self.assertEqual(cotizacion.subtotal, Decimal('300.00'))

    def test_cotizacion_queda_marcada_como_origen_web_con_pagina_de_origen(self):
        self.client.post(reverse('web_contacto:solicitud_cotizacion'), self._datos_validos())

        cotizacion = Cotizacion.objects.get()
        self.assertEqual(cotizacion.cliente.origen, 'web')
        self.assertEqual(cotizacion.solicitud_web.origen, '/servicios/ensayo-cbr-test/')

    def test_dos_envios_con_mismo_ruc_no_duplican_cliente(self):
        self.client.post(reverse('web_contacto:solicitud_cotizacion'), self._datos_validos())
        self.client.post(
            reverse('web_contacto:solicitud_cotizacion'),
            self._datos_validos(razon_social='Constructora Test SAC (repetido)'),
        )

        self.assertEqual(Cliente.objects.filter(ruc='20123456789').count(), 1)
        self.assertEqual(Cotizacion.objects.count(), 2)
        self.assertEqual(SolicitudCotizacionWeb.objects.count(), 2)

    def test_no_se_puede_cotizar_un_servicio_publicado_sin_vinculo_al_lims(self):
        response = self.client.post(
            reverse('web_contacto:solicitud_cotizacion'),
            self._datos_validos(servicios=[self.publicado_sin_servicio.slug]),
            follow=True,
        )
        self.assertEqual(response.status_code, 200)
        self.assertFalse(Cliente.objects.filter(ruc='20123456789').exists())

    def test_honeypot_relleno_no_crea_nada(self):
        self.client.post(
            reverse('web_contacto:solicitud_cotizacion'),
            self._datos_validos(sitio_web_empresa='http://spam.example.com'),
        )
        self.assertFalse(SolicitudCotizacionWeb.objects.exists())

    def test_rate_limit_bloquea_tras_el_maximo_de_intentos(self):
        url = reverse('web_contacto:solicitud_cotizacion')
        for _ in range(RATE_LIMIT_MAX_INTENTOS):
            self.client.post(url, self._datos_validos(ruc='20999999999'))

        SolicitudCotizacionWeb.objects.all().delete()
        Cliente.objects.all().delete()

        self.client.post(url, self._datos_validos(ruc='20888888888'))

        self.assertFalse(SolicitudCotizacionWeb.objects.exists())
        self.assertFalse(Cliente.objects.filter(ruc='20888888888').exists())


class PreseleccionDeLineaTestCase(TestCase):
    """CTA de linea_detalle.html: /contacto/?linea=<slug> debe llegar hasta el
    formulario para que el JS (linea-detalle.js / contacto.html) marque los
    checkboxes de esa línea."""

    @classmethod
    def setUpTestData(cls):
        categoria = CategoriaServicio.objects.create(nombre='Suelos')
        cls.linea = LineaServicio.objects.create(
            slug='mecanica-de-suelos-test', nombre='Mecánica de Suelos', titulo_h1='x',
            resumen='r', contenido='c', activo=True,
        )
        servicio = Servicio.objects.create(codigo_facturacion='ES011-TEST', nombre='CBR')
        cls.publicado = ServicioPublicado.objects.create(
            servicio=servicio, categoria=categoria, linea=cls.linea, slug='ensayo-cbr-test',
            titulo_publico='Ensayo CBR', resumen='r', contenido='c', activo=True,
        )

    def setUp(self):
        cache.clear()

    def test_query_param_linea_llega_al_html_como_data_attribute(self):
        response = self.client.get(reverse('web_contacto:contacto'), {'linea': self.linea.slug})
        self.assertContains(response, f'data-linea-preseleccionada="{self.linea.slug}"')
        self.assertContains(response, f'data-linea-slug="{self.linea.slug}"')

    def test_sin_query_param_el_atributo_queda_vacio(self):
        response = self.client.get(reverse('web_contacto:contacto'))
        self.assertContains(response, 'data-linea-preseleccionada=""')


class MensajeContactoTestCase(TestCase):
    def setUp(self):
        cache.clear()

    def _datos_validos(self, **overrides):
        datos = {
            'nombre': 'Ana Lopez',
            'correo': 'ana@example.com',
            'telefono': '999999999',
            'asunto': 'Consulta sobre ensayos',
            'mensaje': 'Quisiera más información.',
            'origen': '/nosotros/',
        }
        datos.update(overrides)
        return datos

    def test_envio_crea_mensaje_contacto(self):
        response = self.client.post(reverse('web_contacto:contacto'), self._datos_validos(), follow=True)
        self.assertEqual(response.status_code, 200)

        mensaje = MensajeContacto.objects.get()
        self.assertEqual(mensaje.estado, 'nuevo')
        self.assertEqual(mensaje.origen, '/nosotros/')

    def test_honeypot_relleno_no_crea_nada(self):
        self.client.post(
            reverse('web_contacto:contacto'),
            self._datos_validos(sitio_web_empresa='http://spam.example.com'),
        )
        self.assertFalse(MensajeContacto.objects.exists())

    def test_rate_limit_bloquea_tras_el_maximo_de_intentos(self):
        url = reverse('web_contacto:contacto')
        for _ in range(RATE_LIMIT_MAX_INTENTOS):
            self.client.post(url, self._datos_validos())

        MensajeContacto.objects.all().delete()
        self.client.post(url, self._datos_validos())

        self.assertFalse(MensajeContacto.objects.exists())
