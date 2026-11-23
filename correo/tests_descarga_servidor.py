"""CORREO_R2_DESCARGA=servidor: con R2, el adjunto sale por Django y no por URL prefirmada."""
from unittest import mock

from django.test import override_settings

from . import almacen
from .enlaces import url_adjunto
from .tests_paso3 import R2, _AlmacenFalso
from .tests_plataforma import HOST, BasePlataforma


@override_settings(ROOT_URLCONF='grupovicaf.urls_lab', SITE_ROLE='lab', CORREO_R2_DESCARGA='servidor', **R2)
class DescargaPorServidorTests(BasePlataforma):
    def test_adjunto_se_entrega_por_el_servidor_sin_redirigir_a_r2(self):
        adjunto = self.m.adjuntos.get()
        falso = _AlmacenFalso(almacen.almacen_correo._wrapped)
        with mock.patch.object(almacen, 'almacen_correo', falso):
            respuesta = self.client.get(url_adjunto(adjunto), HTTP_HOST=HOST)
        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(falso.pedidas, [])  # no se pidió ninguna URL prefirmada
        self.assertIn('attachment', respuesta['Content-Disposition'])
        self.assertIn('planos.pdf', respuesta['Content-Disposition'])
        self.assertEqual(respuesta['X-Content-Type-Options'], 'nosniff')
