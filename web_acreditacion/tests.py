"""Pruebas del certificado ISO 9001 en /acreditacion/ (specs/WEB v3, T13-T16)."""
import importlib
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

from .models import Certificacion, validar_pdf
from .views import servir_certificado_dev

PDF_MINIMO = b'%PDF-1.4\n1 0 obj<<>>endobj\ntrailer<<>>\n%%EOF\n'


def pdf(nombre='certificado.pdf', contenido=PDF_MINIMO):
    return SimpleUploadedFile(nombre, contenido, content_type='application/pdf')


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
            'norma': 'ISO 9001:2015',
            'sistema': 'Sistema de Gestión de la Calidad',
            'numero_certificado': 'ER-TEST/2026',
            'organismo': 'AENOR CONFIA S.A.U.',
            'alcance': 'Servicios de estudios de mecánica de suelos.',
            'sede': 'Jr. Los Topacios 440, Cajamarca (Perú)',
            'fecha_emision': date(2026, 4, 1),
            'vigencia_hasta': timezone.localdate() + timedelta(days=365),
            'archivo': pdf(),
        }
        datos.update(campos)
        return Certificacion.objects.create(**datos)


class CertificacionModelTests(MediaTemporalMixin, TestCase):
    def setUp(self):
        super().setUp()
        # La migración 0003 siembra ER-0146/2026 sin PDF; no debe estar publicada.
        self.semilla = Certificacion.objects.get(numero_certificado='ER-0146/2026')

    def test_semilla_con_los_datos_del_pdf_y_sin_publicar(self):
        self.assertEqual(self.semilla.norma, 'ISO 9001:2015')
        self.assertEqual(self.semilla.organismo, 'AENOR CONFIA S.A.U.')
        self.assertEqual(self.semilla.vigencia_hasta, date(2029, 4, 1))
        self.assertFalse(self.semilla.archivo)
        self.assertNotIn(self.semilla, Certificacion.objects.publicadas())

    def test_publicadas_aplica_rn15(self):
        # REQ-WEB-31: activa + con PDF + vigencia sin pasar; el último día cuenta.
        hoy = timezone.localdate()
        vigente = self.crear_certificacion(numero_certificado='A')
        ultimo_dia = self.crear_certificacion(numero_certificado='B', vigencia_hasta=hoy)
        vencida = self.crear_certificacion(numero_certificado='C', vigencia_hasta=hoy - timedelta(days=1))
        inactiva = self.crear_certificacion(numero_certificado='D', activo=False)
        sin_pdf = self.crear_certificacion(numero_certificado='E', archivo='')

        publicadas = set(Certificacion.objects.publicadas())
        self.assertEqual(publicadas, {vigente, ultimo_dia})
        self.assertTrue(ultimo_dia.publicada)
        for certificacion in (vencida, inactiva, sin_pdf):
            self.assertFalse(certificacion.publicada, certificacion.numero_certificado)

    def test_publicadas_con_fecha_explicita(self):
        cert = self.crear_certificacion(vigencia_hasta=date(2029, 4, 1))
        self.assertIn(cert, Certificacion.objects.publicadas(hoy=date(2029, 4, 1)))
        self.assertNotIn(cert, Certificacion.objects.publicadas(hoy=date(2029, 4, 2)))

    def test_validar_pdf_rechaza_lo_que_no_es_pdf(self):
        # REQ-WEB-36: firma %PDF- y máximo 10 MB.
        validar_pdf(pdf())
        with self.assertRaises(ValidationError):
            validar_pdf(pdf('falso.pdf', b'<html>no soy un pdf</html>'))
        grande = pdf()
        grande.size = 10 * 1024 * 1024 + 1
        with self.assertRaises(ValidationError):
            validar_pdf(grande)

    def test_full_clean_exige_extension_pdf_y_alt_del_sello(self):
        cert = Certificacion(
            norma='ISO 9001:2015', numero_certificado='X', organismo='AENOR',
            alcance='Alcance', vigencia_hasta=date(2029, 4, 1), archivo=pdf('certificado.exe'),
        )
        with self.assertRaises(ValidationError) as error:
            cert.full_clean()
        self.assertIn('archivo', error.exception.message_dict)

        cert.archivo = pdf()
        cert.sello = SimpleUploadedFile('sello.png', b'x', content_type='image/png')
        with self.assertRaises(ValidationError) as error:
            cert.clean()
        self.assertIn('sello_alt', error.exception.message_dict)


@override_settings(ROOT_URLCONF='grupovicaf.urls_web')
class AcreditacionPaginaTests(MediaTemporalMixin, TestCase):
    def get_html(self):
        respuesta = self.client.get(reverse('web_acreditacion:acreditacion'))
        self.assertEqual(respuesta.status_code, 200)
        return respuesta.content.decode()

    def test_tarjeta_con_los_datos_del_certificado(self):
        # REQ-WEB-30
        cert = self.crear_certificacion(vigencia_hasta=date(2099, 4, 1))
        html = self.get_html()
        for texto in (
            'Sistema de gestión certificado', 'ISO 9001:2015', 'Sistema de Gestión de la Calidad',
            'N.º ER-TEST/2026', 'AENOR CONFIA S.A.U.', 'Servicios de estudios de mecánica de suelos.',
            'Jr. Los Topacios 440, Cajamarca (Perú)', 'Emitido el 01/04/2026', 'vigente hasta el 01/04/2099',
        ):
            self.assertIn(texto, html)
        self.assertEqual(html.count('<h1'), 1)

        # REQ-WEB-35: el botón es un enlace real a pestaña nueva (sin JS y en móvil).
        self.assertIn(f'href="{cert.archivo.url}" target="_blank" rel="noopener"', html)
        self.assertIn('data-cert-pdf-open', html)

    def test_modal_accesible_y_js_solo_con_certificaciones(self):
        # REQ-WEB-32 y 34
        self.crear_certificacion()
        html = self.get_html()
        self.assertEqual(html.count('id="modal-certificado-pdf"'), 1)
        self.assertIn('role="dialog" aria-modal="true" aria-labelledby="modal-certificado-pdf-titulo"', html)
        self.assertIn('data-cert-pdf-visor', html)
        self.assertIn('data-cert-pdf-descargar', html)
        self.assertEqual(html.count('data-cert-pdf-cerrar'), 2)  # × y "Cerrar"
        self.assertIn('web/js/certificado-pdf.js', html)
        # El iframe no carga el PDF con la página (regla 17).
        self.assertNotIn('<iframe data-cert-pdf-visor title="Certificado (PDF)" class="w-full flex-1 bg-slate-100" src=', html)

    def test_sello_con_alt_o_distintivo_de_texto(self):
        cert = self.crear_certificacion()
        html = self.get_html()
        self.assertNotIn('<img src="/media/certificaciones/sellos/', html)
        self.assertIn('<span class="mono-tag mt-1 text-xs font-bold">ISO 9001</span>', html)

        # PNG 1x1 válido para que ImageField pueda leer ancho y alto.
        png = (
            b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00'
            b'\x00\x1f\x15\xc4\x89\x00\x00\x00\rIDATx\x9cc\xf8\x0f\x00\x00\x01\x01\x00\x05\x18\xd8N'
            b'\x00\x00\x00\x00IEND\xaeB`\x82'
        )
        cert.sello = SimpleUploadedFile('sello.png', png, content_type='image/png')
        cert.sello_alt = 'Sello AENOR Gestión de la Calidad ISO 9001'
        cert.save()
        html = self.get_html()
        self.assertIn('alt="Sello AENOR Gestión de la Calidad ISO 9001"', html)
        self.assertIn('loading="lazy"', html)
        self.assertIn('width="1" height="1"', html)

    def test_vencida_inactiva_o_sin_pdf_no_se_muestran(self):
        # REQ-WEB-31: ni tarjeta, ni modal, ni JS.
        hoy = timezone.localdate()
        self.crear_certificacion(numero_certificado='VENCIDA', vigencia_hasta=hoy - timedelta(days=1))
        self.crear_certificacion(numero_certificado='INACTIVA', activo=False)
        self.crear_certificacion(numero_certificado='SINPDF', archivo='')
        html = self.get_html()
        for texto in ('VENCIDA', 'INACTIVA', 'SINPDF', 'ER-0146/2026', 'modal-certificado-pdf',
                      'certificado-pdf.js', 'Sistema de gestión certificado'):
            self.assertNotIn(texto, html)
        # La acreditación INACAL sigue ahí.
        self.assertIn('modal-certificado-inacal', html)


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
        # REQ-WEB-38
        cert = self.crear_certificacion(
            numero_certificado='ER-0146/2026-T', vigencia_hasta=date(2099, 4, 1),
            organismo='AENOR </script> & CONFIA',
        )
        for pagina in ('web_contacto:contacto', 'web_acreditacion:acreditacion'):
            with self.subTest(pagina=pagina):
                negocio = self.local_business(pagina)
                self.assertIn('hasCredential', negocio)  # INACAL intacto
                self.assertEqual(negocio['hasCertification'], [{
                    '@type': 'Certification',
                    'name': 'ISO 9001:2015 · Sistema de Gestión de la Calidad',
                    'certificationIdentification': 'ER-0146/2026-T',
                    'issuedBy': {'@type': 'Organization', 'name': 'AENOR </script> & CONFIA'},
                    'expires': '2099-04-01',
                    'certificationStatus': 'https://schema.org/CertificationActive',
                    'url': f'https://www.grupovicaf.com{cert.archivo.url}',
                    'validFrom': '2026-04-01',
                }])

    def test_sin_certificaciones_publicadas_no_hay_has_certification(self):
        # REQ-WEB-31: la semilla sin PDF y una vencida no se declaran.
        self.crear_certificacion(vigencia_hasta=timezone.localdate() - timedelta(days=1))
        self.assertNotIn('hasCertification', self.local_business())
