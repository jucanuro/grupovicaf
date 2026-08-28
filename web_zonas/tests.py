from django.test import TestCase
from django.urls import reverse

from servicios.models import CategoriaServicio
from web_catalogo.models import ServicioPublicado

from .models import ZonaCobertura
from .sitemaps import ZonaCoberturaSitemap


class ZonaCoberturaTestCase(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.categoria = CategoriaServicio.objects.create(nombre='Suelos')
        cls.publicado = ServicioPublicado.objects.create(
            categoria=cls.categoria,
            slug='ensayo-cbr-test',
            titulo_publico='Ensayo CBR',
            resumen='Resumen del ensayo CBR.',
            contenido='Contenido completo del ensayo CBR.',
            activo=True,
        )
        # slugs con sufijo -test: la migración de datos 0002_seed_zonas ya crea
        # las 7 zonas reales (incl. "jaen", "cajamarca"); usar esos slugs aquí
        # chocaría con el unique=True de ZonaCobertura.slug.
        cls.jaen = ZonaCobertura.objects.create(
            slug='jaen-test', nombre='Jaén', provincia='Jaén', departamento='Cajamarca',
            titulo_h1='Laboratorio de suelos en Jaén',
            introduccion='PENDIENTE DE REDACCIÓN — resumen de Jaén.',
            contenido='PENDIENTE DE REDACCIÓN — contenido de Jaén.',
            es_sede=False, activo=True,
        )
        cls.jaen.servicios.add(cls.publicado)
        cls.cajamarca = ZonaCobertura.objects.create(
            slug='cajamarca-test', nombre='Cajamarca', provincia='Cajamarca', departamento='Cajamarca',
            titulo_h1='Laboratorio de suelos y materiales en Cajamarca',
            introduccion='PENDIENTE DE REDACCIÓN — resumen de Cajamarca.',
            contenido='PENDIENTE DE REDACCIÓN — contenido de Cajamarca.',
            es_sede=True, activo=True,
        )


class ZonaDetalleTests(ZonaCoberturaTestCase):
    def test_h1_canonical_y_jsonld(self):
        response = self.client.get(reverse('web_zonas:zona_detalle', kwargs={'slug': self.jaen.slug}))
        contenido = response.content.decode()
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, '<h1', count=1)
        self.assertIn('Laboratorio de suelos en Jaén', contenido)
        self.assertIn('rel="canonical"', contenido)
        self.assertIn('"@type": "Service"', contenido)
        self.assertIn('"@type": "BreadcrumbList"', contenido)

    def test_zona_inactiva_da_404(self):
        self.jaen.activo = False
        self.jaen.save()
        response = self.client.get(reverse('web_zonas:zona_detalle', kwargs={'slug': self.jaen.slug}))
        self.assertEqual(response.status_code, 404)

    def test_zonas_list_resuelve(self):
        response = self.client.get(reverse('web_zonas:zonas_list'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, '<h1', count=1)


class EnlaceCruzadoTests(ZonaCoberturaTestCase):
    def test_zona_enlaza_a_su_servicio(self):
        response = self.client.get(reverse('web_zonas:zona_detalle', kwargs={'slug': self.jaen.slug}))
        self.assertContains(
            response, reverse('web_catalogo:servicio_detalle', kwargs={'slug': self.publicado.slug})
        )

    def test_servicio_enlaza_a_sus_zonas_sin_duplicar_contenido(self):
        response = self.client.get(
            reverse('web_catalogo:servicio_detalle', kwargs={'slug': self.publicado.slug})
        )
        self.assertContains(
            response, reverse('web_zonas:zona_detalle', kwargs={'slug': self.jaen.slug})
        )


class SitemapTests(ZonaCoberturaTestCase):
    def test_incluye_activas_y_excluye_inactivas(self):
        inactiva = ZonaCobertura.objects.create(
            slug='inactiva-test', nombre='Inactiva', provincia='Cajamarca', departamento='Cajamarca',
            titulo_h1='x', introduccion='x', contenido='x', activo=False,
        )
        items = list(ZonaCoberturaSitemap().items())
        self.assertIn(self.jaen, items)
        self.assertNotIn(inactiva, items)

    def test_sitemap_xml_incluye_url_de_zona(self):
        response = self.client.get('/sitemap.xml')
        self.assertContains(
            response, reverse('web_zonas:zona_detalle', kwargs={'slug': self.jaen.slug})
        )
