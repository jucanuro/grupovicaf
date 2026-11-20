"""Etiqueta de tipo de archivo (PDF, Excel, Word…) en adjuntos y lista."""
from django.template import Context, Template
from django.test import SimpleTestCase

from .tipos_archivo import tipo_de


class TipoDeArchivoTests(SimpleTestCase):
    def test_por_extension(self):
        casos = {
            'cotizacion.PDF': ('pdf', 'PDF'), 'precios.xlsx': ('excel', 'XLS'), 'datos.csv': ('excel', 'XLS'),
            'carta.docx': ('word', 'DOC'), 'oferta.pptx': ('ppt', 'PPT'), 'foto.JPG': ('imagen', 'IMG'),
            'todo.zip': ('zip', 'ZIP'), 'factura.xml': ('xml', 'XML'), 'plano.dwg': ('cad', 'CAD'),
        }
        for nombre, esperado in casos.items():
            self.assertEqual(tipo_de(nombre), esperado, nombre)

    def test_sin_extension_usa_el_mime(self):
        self.assertEqual(tipo_de('adjunto-1', 'application/pdf'), ('pdf', 'PDF'))
        self.assertEqual(tipo_de('hoja', 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'), ('excel', 'XLS'))
        self.assertEqual(tipo_de('doc', 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'), ('word', 'DOC'))

    def test_desconocido(self):
        self.assertEqual(tipo_de('raro.abc'), ('otro', 'ABC'))
        self.assertEqual(tipo_de('sinextension'), ('otro', 'ARCH'))
        self.assertEqual(tipo_de('largo.extensionlarga'), ('otro', 'ARCH'))

    def test_etiqueta_en_plantilla(self):
        html = Template("{% load correo_tags %}{% tipo_archivo n m %}").render(Context({'n': 'a.xlsx', 'm': ''}))
        self.assertIn('tipo--excel', html)
        self.assertIn('>XLS<', html)
