from decimal import Decimal
from io import BytesIO

from django.contrib.auth.models import User
from django.core.cache import cache
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.test.utils import CaptureQueriesContext
from django.db import connection
from django.urls import reverse
from PIL import Image

from clientes.models import Cliente
from servicios.models import CategoriaServicio, Metodo, Norma, Servicio
from trabajadores.models import RolTrabajador, TrabajadorProfile

from .cache import KEY_CLIENTES_LIST, KEY_EQUIPO_LIST, KEY_SERVICIOS_LIST
from .models import ClienteDestacado, ImagenLinea, LineaServicio, MiembroEquipoPublicado, ServicioPublicado
from .sitemaps import LineaServicioSitemap, ServicioPublicadoSitemap


def _imagen_de_prueba(nombre='foto.png'):
    buffer = BytesIO()
    Image.new('RGB', (20, 10), color='blue').save(buffer, format='PNG')
    buffer.seek(0)
    return SimpleUploadedFile(nombre, buffer.read(), content_type='image/png')

# Campos que jamás deben aparecer en el SQL de una vista pública (regla 3 de
# CLAUDE.md + "NUNCA muestres precios" del encargo F5, "REGLA CRÍTICA" del
# encargo de líneas de servicio: precio_base y codigo_facturacion tampoco).
# 'ruc' va calificado con su tabla: desde F9, siteconfig.NegocioConfig tiene
# su propio 'ruc' (el de la propia empresa, dato público que sí se muestra en
# el footer de toda página) y viaja en el SQL de cualquier vista pública vía
# el context processor `negocio` — un match por substring lo confundiría con
# el de clientes.Cliente.ruc, que es el que esta regla debe seguir vetando.
CAMPOS_PROHIBIDOS = (
    'codigo_confidencial', 'clientes_cliente"."ruc', 'firma_electronica', 'precio_base', 'codigo_facturacion',
)


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
        cls.linea = LineaServicio.objects.create(
            slug='mecanica-de-suelos-test',
            nombre='Mecánica de Suelos Test',
            titulo_h1='Mecánica de suelos en Cajamarca (test)',
            resumen='Resumen de la línea de mecánica de suelos.',
            contenido='Contenido de la línea de mecánica de suelos.',
            activo=True,
        )
        cls.linea.ensayos.add(cls.servicio)

        cls.publicado = ServicioPublicado.objects.create(
            servicio=cls.servicio,
            categoria=cls.categoria,
            linea=cls.linea,
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

    def test_linea_detalle_no_filtra_campos_confidenciales(self):
        self._assert_sql_limpio(
            reverse('web_catalogo:servicio_detalle', kwargs={'slug': self.linea.slug})
        )

    def test_clientes_list_no_filtra_campos_confidenciales(self):
        self._assert_sql_limpio(reverse('web_catalogo:clientes_list'))

    def test_equipo_list_no_filtra_campos_confidenciales(self):
        self._assert_sql_limpio(reverse('web_catalogo:equipo_list'))


class PrecioNuncaEnHTMLTests(CatalogoPublicoTestCase):
    """REGLA CRÍTICA del encargo de líneas: precio_base y codigo_facturacion
    de servicios.Servicio nunca deben llegar al HTML renderizado, ni siquiera
    si algún día se agrega un campo nuevo al template sin pasar por .only()."""

    def setUp(self):
        super().setUp()
        self.servicio.precio_base = Decimal('1234.56')
        self.servicio.codigo_facturacion = 'ES011-SECRETO'
        self.servicio.save()

    def test_linea_detalle_no_expone_precio_ni_codigo_facturacion(self):
        response = self.client.get(
            reverse('web_catalogo:servicio_detalle', kwargs={'slug': self.linea.slug})
        )
        contenido = response.content.decode()
        self.assertEqual(response.status_code, 200)
        self.assertNotIn('1234.56', contenido)
        self.assertNotIn('ES011-SECRETO', contenido)
        # No se reutiliza el loop genérico de CAMPOS_PROHIBIDOS aquí: 'ruc'
        # como substring choca con palabras españolas legítimas que la propia
        # página necesita mostrar (p. ej. "Evaluación Estruct-RUC-tural" en el
        # sidebar de líneas). La garantía de que esos campos nunca salen del
        # ORM ya la cubre FugaCamposConfidencialesTests a nivel de SQL; esta
        # clase se queda con los dos valores concretos de la REGLA CRÍTICA.
        for campo in ('precio_base', 'codigo_facturacion'):
            self.assertNotIn(campo, contenido)

    def test_servicio_detalle_no_expone_precio_ni_codigo_facturacion(self):
        response = self.client.get(
            reverse('web_catalogo:servicio_detalle', kwargs={'slug': self.publicado.slug})
        )
        contenido = response.content.decode()
        self.assertEqual(response.status_code, 200)
        self.assertNotIn('1234.56', contenido)
        self.assertNotIn('ES011-SECRETO', contenido)
        # No se reutiliza el loop genérico de CAMPOS_PROHIBIDOS aquí: 'ruc'
        # como substring choca con palabras españolas legítimas que la propia
        # página necesita mostrar (p. ej. "Evaluación Estruct-RUC-tural" en el
        # sidebar de líneas). La garantía de que esos campos nunca salen del
        # ORM ya la cubre FugaCamposConfidencialesTests a nivel de SQL; esta
        # clase se queda con los dos valores concretos de la REGLA CRÍTICA.
        for campo in ('precio_base', 'codigo_facturacion'):
            self.assertNotIn(campo, contenido)


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

    def test_guardar_linea_servicio_invalida_la_cache(self):
        self.client.get(reverse('web_catalogo:servicios_list'))
        self.assertIsNotNone(cache.get(KEY_SERVICIOS_LIST))

        self.linea.save()

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


class LineaServicioDetalleTests(CatalogoPublicoTestCase):
    def test_h1_y_canonical(self):
        response = self.client.get(
            reverse('web_catalogo:servicio_detalle', kwargs={'slug': self.linea.slug})
        )
        contenido = response.content.decode()
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, '<h1', count=1)
        self.assertIn(self.linea.titulo_h1, contenido)
        self.assertIn('rel="canonical"', contenido)

    def test_linea_enlaza_al_ensayo_publicado(self):
        response = self.client.get(
            reverse('web_catalogo:servicio_detalle', kwargs={'slug': self.linea.slug})
        )
        self.assertContains(response, reverse(
            'web_catalogo:servicio_detalle', kwargs={'slug': self.publicado.slug}
        ))

    def test_ensayo_enlaza_de_vuelta_a_su_linea(self):
        response = self.client.get(
            reverse('web_catalogo:servicio_detalle', kwargs={'slug': self.publicado.slug})
        )
        self.assertContains(response, reverse(
            'web_catalogo:servicio_detalle', kwargs={'slug': self.linea.slug}
        ))

    def test_linea_inactiva_da_404(self):
        self.linea.activo = False
        self.linea.save()
        response = self.client.get(
            reverse('web_catalogo:servicio_detalle', kwargs={'slug': self.linea.slug})
        )
        self.assertEqual(response.status_code, 404)

    def test_slug_inexistente_da_404(self):
        response = self.client.get(
            reverse('web_catalogo:servicio_detalle', kwargs={'slug': 'no-existe-en-ningun-modelo'})
        )
        self.assertEqual(response.status_code, 404)

    def test_sidebar_enlaza_a_todas_las_lineas_activas_con_url_real(self):
        otra = LineaServicio.objects.create(
            slug='otra-linea-test', nombre='Otra Línea Test', titulo_h1='Otra línea',
            resumen='r', contenido='c', activo=True,
        )
        inactiva = LineaServicio.objects.create(
            slug='linea-inactiva-sidebar-test', nombre='Inactiva Sidebar', titulo_h1='x',
            resumen='r', contenido='c', activo=False,
        )
        response = self.client.get(
            reverse('web_catalogo:servicio_detalle', kwargs={'slug': self.linea.slug})
        )
        self.assertContains(response, reverse(
            'web_catalogo:servicio_detalle', kwargs={'slug': otra.slug}
        ))
        self.assertNotContains(response, reverse(
            'web_catalogo:servicio_detalle', kwargs={'slug': inactiva.slug}
        ))

    def test_galeria_muestra_8_visibles_y_oculta_el_resto(self):
        for i in range(10):
            ImagenLinea.objects.create(
                linea=self.linea, imagen=_imagen_de_prueba(f'foto{i}.png'),
                alt_text=f'Foto {i}', orden=i, activo=True,
            )
        response = self.client.get(
            reverse('web_catalogo:servicio_detalle', kwargs={'slug': self.linea.slug})
        )
        contenido = response.content.decode()
        self.assertEqual(contenido.count('galeria-item'), 10)
        self.assertEqual(contenido.count('galeria-item group relative block aspect-square '
                                          'overflow-hidden rounded-2xl border border-slate-200 '
                                          'bg-slate-100 hidden'), 2)
        self.assertIn('id="btn-ver-mas-galeria"', contenido)

    def test_galeria_oculta_fotos_inactivas(self):
        ImagenLinea.objects.create(
            linea=self.linea, imagen=_imagen_de_prueba(), alt_text='Visible', orden=0, activo=True,
        )
        ImagenLinea.objects.create(
            linea=self.linea, imagen=_imagen_de_prueba('oculta.png'), alt_text='Oculta', orden=1, activo=False,
        )
        response = self.client.get(
            reverse('web_catalogo:servicio_detalle', kwargs={'slug': self.linea.slug})
        )
        self.assertContains(response, 'Visible')
        self.assertNotContains(response, 'Oculta')

    def test_tabla_de_ensayos_no_expone_precio_ni_codigo_facturacion(self):
        self.servicio.precio_base = Decimal('999.99')
        self.servicio.codigo_facturacion = 'ES011-OCULTO'
        self.servicio.save()
        response = self.client.get(
            reverse('web_catalogo:servicio_detalle', kwargs={'slug': self.linea.slug})
        )
        contenido = response.content.decode()
        self.assertNotIn('999.99', contenido)
        self.assertNotIn('ES011-OCULTO', contenido)


class ImagenLineaTests(CatalogoPublicoTestCase):
    def test_alt_text_es_obligatorio(self):
        imagen = ImagenLinea(linea=self.linea, imagen=_imagen_de_prueba(), alt_text='')
        with self.assertRaises(ValidationError):
            imagen.full_clean()

    def test_alt_text_presente_pasa_la_validacion(self):
        imagen = ImagenLinea(linea=self.linea, imagen=_imagen_de_prueba(), alt_text='Ensayo en campo')
        imagen.full_clean()


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

    def test_lineaservicio_sitemap_incluye_activas_y_excluye_inactivas(self):
        inactiva = LineaServicio.objects.create(
            slug='inactiva-test', nombre='Inactiva', titulo_h1='Inactiva',
            resumen='r', contenido='c', activo=False,
        )
        items = list(LineaServicioSitemap().items())
        self.assertIn(self.linea, items)
        self.assertNotIn(inactiva, items)

    def test_sitemap_xml_incluye_url_de_linea(self):
        response = self.client.get('/sitemap.xml')
        self.assertContains(response, reverse(
            'web_catalogo:servicio_detalle', kwargs={'slug': self.linea.slug}
        ))
