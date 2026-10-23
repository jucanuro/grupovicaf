"""Pruebas de las certificaciones (specs/WEB v4, T18-T20; cabeceras de v3, T15)."""
import importlib
import io
import json
import os
import re
import shutil
import tempfile
from datetime import date, timedelta

from django.core.cache import cache
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import RequestFactory, TestCase, override_settings
from django.urls import clear_url_caches, resolve, reverse
from django.utils import timezone
from PIL import Image

from .models import Acreditacion, Certificacion, validar_archivo
from .views import servir_certificado_dev

PDF_MINIMO = b'%PDF-1.4\n1 0 obj<<>>endobj\ntrailer<<>>\n%%EOF\n'


def _png_minimo():
    buffer = io.BytesIO()
    Image.new('RGB', (2, 1), 'white').save(buffer, 'PNG')
    return buffer.getvalue()


PNG_MINIMO = _png_minimo()


def pdf(nombre='certificado.pdf', contenido=PDF_MINIMO):
    return SimpleUploadedFile(nombre, contenido, content_type='application/pdf')


def png(nombre='certificado.png', contenido=PNG_MINIMO):
    return SimpleUploadedFile(nombre, contenido, content_type='image/png')


class MediaTemporalMixin:
    """MEDIA_ROOT en un directorio temporal para no ensuciar mediafiles/."""

    @classmethod
    def setUpClass(cls):
        cls._media = tempfile.mkdtemp()
        override_media = override_settings(MEDIA_ROOT=cls._media)
        override_media.enable()
        # Como class cleanup y antes de super(): el override_settings de clase
        # también se deshace con addClassCleanup y restaura los settings que vio
        # al activarse; en orden LIFO se deshace primero el suyo y luego este.
        cls.addClassCleanup(shutil.rmtree, cls._media, ignore_errors=True)
        cls.addClassCleanup(override_media.disable)
        super().setUpClass()

    # El footer cachea las líneas del catálogo (web_catalogo.context_processors);
    # sin limpiar, otras pruebas heredan objetos leídos con este MEDIA_ROOT.
    def setUp(self):
        super().setUp()
        cache.clear()

    def tearDown(self):
        cache.clear()
        super().tearDown()

    def crear_certificacion(self, **campos):
        datos = {
            'titulo': 'Certificación ISO 9001:2015',
            'descripcion': 'Sistema de Gestión de la Calidad certificado por AENOR.',
            'tipo': Certificacion.TIPO_ISO,
            'institucion': 'AENOR CONFIA S.A.U.',
            'vigencia_hasta': timezone.localdate() + timedelta(days=365),
            'archivo': pdf(),
            'orden': 10,
        }
        datos.update(campos)
        return Certificacion.objects.create(**datos)


class CertificacionModelTests(MediaTemporalMixin, TestCase):
    def test_migracion_pasa_inacal_e_iso9001_al_modelo_unico(self):
        # REQ-WEB-41: la 0005 convierte la semilla ISO 9001 de v3 y crea INACAL.
        inacal = Certificacion.objects.get(tipo=Certificacion.TIPO_ACREDITACION)
        self.assertEqual(inacal.titulo, 'Acreditación INACAL LE-230')
        self.assertEqual(inacal.institucion, 'Instituto Nacional de Calidad (INACAL)')
        self.assertIn('LE-230', inacal.descripcion)
        self.assertEqual(inacal.vigencia_hasta, date(2027, 5, 27))
        self.assertEqual(inacal.archivo.name, 'certificaciones/inacal-le-230.webp')
        self.assertFalse(inacal.es_pdf)
        self.assertEqual(inacal.orden, 0)

        iso = Certificacion.objects.get(tipo=Certificacion.TIPO_ISO)
        self.assertEqual(iso.titulo, 'Certificación ISO 9001:2015')
        self.assertEqual(iso.institucion, 'AENOR CONFIA S.A.U.')
        self.assertEqual(
            iso.descripcion,
            'Sistema de Gestión de la Calidad certificado por AENOR CONFIA. Certificado N.º ER-0146/2026.',
        )
        self.assertEqual(iso.vigencia_hasta, date(2029, 4, 1))
        self.assertEqual(iso.orden, 1)
        # La semilla de v3 no traía PDF: no se publica hasta que se suba.
        self.assertFalse(iso.archivo)
        self.assertFalse(iso.publicada)

    def test_publicadas_aplica_rn15(self):
        # REQ-WEB-42: activa + con archivo + vigencia vacía o sin pasar; el último día cuenta.
        Certificacion.objects.all().delete()
        hoy = timezone.localdate()
        vigente = self.crear_certificacion(titulo='A')
        sin_vigencia = self.crear_certificacion(titulo='B', vigencia_hasta=None)
        ultimo_dia = self.crear_certificacion(titulo='C', vigencia_hasta=hoy)
        vencida = self.crear_certificacion(titulo='D', vigencia_hasta=hoy - timedelta(days=1))
        inactiva = self.crear_certificacion(titulo='E', activo=False)
        sin_archivo = self.crear_certificacion(titulo='F', archivo='')

        self.assertEqual(set(Certificacion.objects.publicadas()), {vigente, sin_vigencia, ultimo_dia})
        for certificacion in (vigente, sin_vigencia, ultimo_dia):
            self.assertTrue(certificacion.publicada, certificacion.titulo)
        for certificacion in (vencida, inactiva, sin_archivo):
            self.assertFalse(certificacion.publicada, certificacion.titulo)

    def test_publicadas_con_fecha_explicita(self):
        cert = self.crear_certificacion(vigencia_hasta=date(2029, 4, 1))
        self.assertIn(cert, Certificacion.objects.publicadas(hoy=date(2029, 4, 1)))
        self.assertNotIn(cert, Certificacion.objects.publicadas(hoy=date(2029, 4, 2)))

    def test_es_pdf_por_extension(self):
        self.assertTrue(self.crear_certificacion().es_pdf)
        self.assertFalse(self.crear_certificacion(archivo=png()).es_pdf)
        self.assertFalse(Certificacion(archivo='').es_pdf)

    def test_validar_archivo_acepta_pdf_e_imagen_reales(self):
        # REQ-WEB-40: firma %PDF-, imagen que Pillow abre y máximo 10 MB.
        validar_archivo(pdf())
        validar_archivo(png())
        for archivo in (
            pdf('falso.pdf', b'<html>no soy un pdf</html>'),
            png('falso.png', b'%PDF-1.4 no soy una imagen'),
            png('falso.webp', b'nada'),
        ):
            with self.subTest(archivo=archivo.name), self.assertRaises(ValidationError):
                validar_archivo(archivo)
        grande = pdf()
        grande.size = 10 * 1024 * 1024 + 1
        with self.assertRaises(ValidationError):
            validar_archivo(grande)

    def test_full_clean_exige_campos_y_extension_permitida(self):
        cert = Certificacion(archivo=png('certificado.gif'))
        with self.assertRaises(ValidationError) as error:
            cert.full_clean()
        for campo in ('titulo', 'descripcion', 'institucion', 'archivo'):
            self.assertIn(campo, error.exception.message_dict)
        self.assertNotIn('vigencia_hasta', error.exception.message_dict)  # opcional

        cert = Certificacion(
            titulo='Otro', descripcion='Corta.', tipo='otro', institucion='X', archivo=png(),
        )
        cert.full_clean()

    def test_tipos_del_admin(self):
        self.assertEqual(
            [etiqueta for _, etiqueta in Certificacion.TIPOS],
            ['Acreditación', 'Certificación ISO', 'Otro'],
        )


@override_settings(ROOT_URLCONF='grupovicaf.urls_web')
class AcreditacionPaginaTests(MediaTemporalMixin, TestCase):
    def get_html(self):
        respuesta = self.client.get(reverse('web_acreditacion:acreditacion'))
        self.assertEqual(respuesta.status_code, 200)
        return respuesta.content.decode()

    def test_grilla_debajo_del_hero_con_cards(self):
        # REQ-WEB-43 y 44
        cert = self.crear_certificacion(titulo='Certificación ISO 9001:2015')
        Acreditacion.objects.create(numero_acreditacion='LE-230', alcance='Ensayos de suelos.')
        html = self.get_html()
        self.assertEqual(html.count('<h1'), 1)
        hero_fin = html.index('</h1>')
        grilla = html.index('id="certificaciones"')
        self.assertLess(hero_fin, grilla)
        self.assertLess(grilla, html.index('Alcance de acreditación'))
        self.assertIn('grid grid-cols-1 gap-6 sm:grid-cols-2 lg:grid-cols-4', html)
        for texto in (
            'Acreditaciones y certificaciones', 'Certificación ISO 9001:2015',
            'Sistema de Gestión de la Calidad certificado por AENOR.', 'AENOR CONFIA S.A.U.',
            '>Certificación ISO</span>', 'Acreditación INACAL LE-230', '>Acreditación</span>',
        ):
            self.assertIn(texto, html)
        # Una card = un enlace real al archivo, en pestaña nueva sin JS (REQ-WEB-46).
        self.assertIn(
            f'href="{cert.archivo.url}" target="_blank" rel="noopener" data-cert-open '
            f'data-cert-tipo="pdf" data-cert-titulo="Certificación ISO 9001:2015"', html,
        )
        self.assertIn('data-cert-tipo="imagen" data-cert-titulo="Acreditación INACAL LE-230"', html)
        self.assertIn('after:absolute after:inset-0', html)
        # Sin el certificado grande al lado: ninguna imagen de certificado en la página.
        self.assertNotIn('GRUPO-VICAF-CERTIFICADO', html)
        self.assertNotIn('<img src="/media/certificaciones/', html)

    def test_orden_del_admin(self):
        self.crear_certificacion(titulo='Primero del admin', orden=0, tipo='otro')
        html = self.get_html()
        self.assertLess(html.index('Primero del admin'), html.index('Acreditación INACAL LE-230'))

    def test_modal_unico_accesible_y_js_solo_con_certificaciones(self):
        # REQ-WEB-47 y 48
        html = self.get_html()
        self.assertEqual(html.count('id="modal-certificacion"'), 1)
        self.assertIn('role="dialog" aria-modal="true" aria-labelledby="modal-certificacion-titulo"', html)
        self.assertIn('data-cert-contenido', html)
        self.assertIn('data-cert-descargar href="#" download', html)
        self.assertIn('Descargar', html)
        self.assertEqual(html.count('data-cert-cerrar'), 2)  # × y "Cerrar"
        self.assertIn('web/js/certificaciones.js', html)
        # Nada se carga con la página (regla 17): el img/iframe lo crea el JS.
        self.assertNotIn('<iframe', html)
        # Los modales de v3 ya no existen.
        for viejo in ('modal-certificado-inacal', 'modal-certificado-pdf', 'certificado-pdf.js', 'modal-certificado.js'):
            self.assertNotIn(viejo, html)

    def test_acceso_inacal_del_hero_abre_la_acreditacion(self):
        # REQ-WEB-50
        html = self.get_html()
        hero = html[:html.index('id="certificaciones"')]
        self.assertIn('data-cert-titulo="Acreditación INACAL LE-230"', hero)

        Certificacion.objects.filter(tipo=Certificacion.TIPO_ACREDITACION).update(activo=False)
        hero = self.get_html().split('</h1>')[1].split('</section>')[0]
        self.assertIn('href="#certificaciones"', hero)
        self.assertNotIn('data-cert-open', hero)

    def test_vencidas_inactivas_o_sin_archivo_no_se_muestran(self):
        # REQ-WEB-42: ni card, ni modal, ni JS.
        Certificacion.objects.all().delete()
        hoy = timezone.localdate()
        self.crear_certificacion(titulo='VENCIDA', vigencia_hasta=hoy - timedelta(days=1))
        self.crear_certificacion(titulo='INACTIVA', activo=False)
        self.crear_certificacion(titulo='SINARCHIVO', archivo='')
        html = self.get_html()
        for texto in ('VENCIDA', 'INACTIVA', 'SINARCHIVO', 'id="certificaciones"', 'modal-certificacion',
                      'certificaciones.js', 'data-cert-open'):
            self.assertNotIn(texto, html)
        # La sección de alcance (modelo Acreditacion) sigue ahí.
        self.assertIn('href="#certificaciones"', html)


class CabecerasPdfTests(MediaTemporalMixin, TestCase):
    def test_pdf_de_certificaciones_embebible_solo_desde_el_mismo_origen(self):
        # REQ-WEB-37: SAMEORIGIN para /media/certificaciones/ en dev.
        os.makedirs(os.path.join(self._media, 'certificaciones'))
        with open(os.path.join(self._media, 'certificaciones', 'cert.pdf'), 'wb') as archivo:
            archivo.write(PDF_MINIMO)
        respuesta = servir_certificado_dev(RequestFactory().get('/media/certificaciones/cert.pdf'), 'cert.pdf')
        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(respuesta['X-Frame-Options'], 'SAMEORIGIN')
        self.assertEqual(respuesta['Content-Type'], 'application/pdf')

    def test_urls_web_enruta_certificaciones_antes_del_static_generico(self):
        import grupovicaf.urls_web as urls_web
        try:
            with override_settings(DEBUG=True):
                importlib.reload(urls_web)
                clear_url_caches()
                coincidencia = resolve('/media/certificaciones/cert.pdf', urlconf=urls_web)
                self.assertEqual(coincidencia.func, servir_certificado_dev)
                self.assertNotEqual(resolve('/media/acreditacion/x.png', urlconf=urls_web).func, servir_certificado_dev)
        finally:
            importlib.reload(urls_web)
            clear_url_caches()

    def test_el_resto_de_la_web_sigue_en_deny(self):
        with override_settings(ROOT_URLCONF='grupovicaf.urls_web'):
            respuesta = self.client.get(reverse('web_acreditacion:acreditacion'))
        self.assertEqual(respuesta['X-Frame-Options'], 'DENY')


@override_settings(ROOT_URLCONF='grupovicaf.urls_web', SITE_URL='https://www.grupovicaf.com')
class JsonLdTests(MediaTemporalMixin, TestCase):
    def local_business(self, nombre_url='web_contacto:contacto'):
        html = self.client.get(reverse(nombre_url)).content.decode()
        bloques = re.findall(r'<script type="application/ld\+json">(.*?)</script>', html, re.S)
        for bloque in bloques:
            datos = json.loads(bloque)  # todo bloque debe seguir siendo JSON válido
            if isinstance(datos, dict) and datos.get('@type') == 'LocalBusiness':
                return datos
        self.fail('No hay JSON-LD LocalBusiness')

    def test_has_certification_en_todas_las_paginas(self):
        # REQ-WEB-51: ISO y Otro; INACAL sigue en hasCredential y no se repite.
        Certificacion.objects.all().delete()
        self.crear_certificacion(titulo='Acreditación INACAL', tipo='acreditacion')
        cert = self.crear_certificacion(
            vigencia_hasta=date(2099, 4, 1), institucion='AENOR </script> & CONFIA',
        )
        otro = self.crear_certificacion(titulo='Reconocimiento', tipo='otro', vigencia_hasta=None, archivo=png())
        for pagina in ('web_contacto:contacto', 'web_acreditacion:acreditacion'):
            with self.subTest(pagina=pagina):
                negocio = self.local_business(pagina)
                self.assertIn('hasCredential', negocio)  # INACAL intacto
                self.assertEqual(negocio['hasCertification'], [
                    {
                        '@type': 'Certification',
                        'name': 'Certificación ISO 9001:2015',
                        'description': 'Sistema de Gestión de la Calidad certificado por AENOR.',
                        'issuedBy': {'@type': 'Organization', 'name': 'AENOR </script> & CONFIA'},
                        'certificationStatus': 'https://schema.org/CertificationActive',
                        'url': f'https://www.grupovicaf.com{cert.archivo.url}',
                        'expires': '2099-04-01',
                    },
                    {
                        '@type': 'Certification',
                        'name': 'Reconocimiento',
                        'description': 'Sistema de Gestión de la Calidad certificado por AENOR.',
                        'issuedBy': {'@type': 'Organization', 'name': 'AENOR CONFIA S.A.U.'},
                        'certificationStatus': 'https://schema.org/CertificationActive',
                        'url': f'https://www.grupovicaf.com{otro.archivo.url}',
                    },
                ])

    def test_sin_certificaciones_publicadas_no_hay_has_certification(self):
        # REQ-WEB-42: la semilla ISO sin PDF, una vencida e INACAL (hasCredential) no se declaran.
        self.crear_certificacion(vigencia_hasta=timezone.localdate() - timedelta(days=1))
        self.assertNotIn('hasCertification', self.local_business())
