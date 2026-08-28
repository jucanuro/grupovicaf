from django.contrib.auth.models import User
from django.core.cache import cache
from django.test import TestCase
from django.test.utils import CaptureQueriesContext
from django.db import connection
from django.urls import reverse

from clientes.models import Cliente
from servicios.models import CategoriaServicio, Metodo, Norma, Servicio
from trabajadores.models import RolTrabajador, TrabajadorProfile

from .cache import KEY_CLIENTES_LIST, KEY_EQUIPO_LIST, KEY_SERVICIOS_LIST
from .models import ClienteDestacado, MiembroEquipoPublicado, ServicioPublicado
from .sitemaps import ServicioPublicadoSitemap

# Campos que jamás deben aparecer en el SQL de una vista pública (regla 3 de
# CLAUDE.md + "NUNCA muestres precios" del encargo F5).
CAMPOS_PROHIBIDOS = ('codigo_confidencial', 'ruc', 'firma_electronica', 'precio_base')


class CatalogoPublicoTestCase(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.categoria = CategoriaServicio.objects.create(nombre='Suelos')
        cls.norma = Norma.objects.create(codigo='ASTM D1883', nombre='CBR de suelos')
        cls.metodo = Metodo.objects.create(codigo='M-01', nombre='Método de laboratorio')
        cls.servicio = Servicio.objects.create(
            codigo_facturacion='ES011-TEST',
            nombre='CBR',
            norma=cls.norma,
            metodo=cls.metodo,
            esta_acreditado=True,
        )
        cls.publicado = ServicioPublicado.objects.create(
            servicio=cls.servicio,
            categoria=cls.categoria,
            slug='ensayo-cbr-test',
            titulo_publico='Ensayo CBR',
            resumen='Resumen del ensayo CBR.',
            contenido='Contenido completo del ensayo CBR.',
            activo=True,
        )

        cls.cliente = Cliente.objects.create(
            ruc='20123456789', razon_social='Constructora Test SAC',
            persona_contacto='Juan Perez', celular_contacto='999999999',
            correo_contacto='juan@example.com',
        )
        cls.cliente_destacado = ClienteDestacado.objects.create(cliente=cls.cliente, activo=True)

        cls.rol = RolTrabajador.objects.create(nombre='Ingeniero de Ensayos')
        cls.user = User.objects.create_user(username='tecnico_test', password='x')
        cls.perfil = TrabajadorProfile.objects.create(
            user=cls.user, rol=cls.rol, nombre_completo='Ana Lopez',
            correo_contacto='ana@example.com',
        )
        cls.miembro = MiembroEquipoPublicado.objects.create(perfil=cls.perfil, activo=True)

    def setUp(self):
        cache.clear()

    def tearDown(self):
        cache.clear()


class FugaCamposConfidencialesTests(CatalogoPublicoTestCase):
    def _assert_sql_limpio(self, url):
        with CaptureQueriesContext(connection) as ctx:
            response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        sql_completo = ' '.join(q['sql'] for q in ctx.captured_queries)
        for campo in CAMPOS_PROHIBIDOS:
            self.assertNotIn(campo, sql_completo, f'{campo} no debería aparecer en el SQL de {url}')

    def test_servicios_list_no_filtra_campos_confidenciales(self):
        self._assert_sql_limpio(reverse('web_catalogo:servicios_list'))

    def test_servicio_detalle_no_filtra_campos_confidenciales(self):
        self._assert_sql_limpio(
            reverse('web_catalogo:servicio_detalle', kwargs={'slug': self.publicado.slug})
        )

    def test_clientes_list_no_filtra_campos_confidenciales(self):
        self._assert_sql_limpio(reverse('web_catalogo:clientes_list'))

    def test_equipo_list_no_filtra_campos_confidenciales(self):
        self._assert_sql_limpio(reverse('web_catalogo:equipo_list'))


class CacheListadosTests(CatalogoPublicoTestCase):
    def test_segunda_carga_de_servicios_no_repite_la_consulta_de_listado(self):
        url = reverse('web_catalogo:servicios_list')

        self.assertIsNone(cache.get(KEY_SERVICIOS_LIST))
        self.client.get(url)
        self.assertIsNotNone(cache.get(KEY_SERVICIOS_LIST))

        with CaptureQueriesContext(connection) as ctx:
            self.client.get(url)
        sql_completo = ' '.join(q['sql'] for q in ctx.captured_queries)
        self.assertNotIn('web_catalogo_serviciopublicado', sql_completo)

    def test_guardar_servicio_publicado_invalida_la_cache(self):
        self.client.get(reverse('web_catalogo:servicios_list'))
        self.assertIsNotNone(cache.get(KEY_SERVICIOS_LIST))

        self.publicado.save()

        self.assertIsNone(cache.get(KEY_SERVICIOS_LIST))

    def test_guardar_cliente_destacado_invalida_su_cache(self):
        self.client.get(reverse('web_catalogo:clientes_list'))
        self.assertIsNotNone(cache.get(KEY_CLIENTES_LIST))

        self.cliente_destacado.save()

        self.assertIsNone(cache.get(KEY_CLIENTES_LIST))

    def test_guardar_miembro_equipo_invalida_su_cache(self):
        self.client.get(reverse('web_catalogo:equipo_list'))
        self.assertIsNotNone(cache.get(KEY_EQUIPO_LIST))

        self.miembro.save()

        self.assertIsNone(cache.get(KEY_EQUIPO_LIST))


class ServicioDetalleTests(CatalogoPublicoTestCase):
    def test_h1_y_canonical(self):
        response = self.client.get(
            reverse('web_catalogo:servicio_detalle', kwargs={'slug': self.publicado.slug})
        )
        contenido = response.content.decode()
        self.assertContains(response, '<h1', count=1)
        self.assertIn('Ensayo CBR en Cajamarca', contenido)
        self.assertIn('rel="canonical"', contenido)
        self.assertNotIn('precio_base', contenido)

    def test_servicio_inactivo_da_404(self):
        self.publicado.activo = False
        self.publicado.save()
        response = self.client.get(
            reverse('web_catalogo:servicio_detalle', kwargs={'slug': self.publicado.slug})
        )
        self.assertEqual(response.status_code, 404)


class SitemapTests(CatalogoPublicoTestCase):
    def test_incluye_publicados_y_excluye_inactivos(self):
        inactivo = ServicioPublicado.objects.create(
            categoria=self.categoria, slug='inactivo-test', titulo_publico='Inactivo',
            resumen='r', contenido='c', activo=False,
        )
        items = list(ServicioPublicadoSitemap().items())
        self.assertIn(self.publicado, items)
        self.assertNotIn(inactivo, items)

    def test_sitemap_xml_incluye_url_de_servicio(self):
        response = self.client.get('/sitemap.xml')
        self.assertContains(response, reverse(
            'web_catalogo:servicio_detalle', kwargs={'slug': self.publicado.slug}
        ))
