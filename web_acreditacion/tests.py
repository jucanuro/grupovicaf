"""Pruebas del certificado ISO 9001 en /acreditacion/ (specs/WEB v3, T13-T16)."""
import shutil
import tempfile
from datetime import date, timedelta

from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.utils import timezone

from .models import Certificacion, validar_pdf

PDF_MINIMO = b'%PDF-1.4\n1 0 obj<<>>endobj\ntrailer<<>>\n%%EOF\n'


def pdf(nombre='certificado.pdf', contenido=PDF_MINIMO):
    return SimpleUploadedFile(nombre, contenido, content_type='application/pdf')


class MediaTemporalMixin:
    """MEDIA_ROOT en un directorio temporal para no ensuciar mediafiles/."""

    @classmethod
    def setUpClass(cls):
        cls._media = tempfile.mkdtemp()
        cls._override_media = override_settings(MEDIA_ROOT=cls._media)
        cls._override_media.enable()
        super().setUpClass()

    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        cls._override_media.disable()
        shutil.rmtree(cls._media, ignore_errors=True)

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
