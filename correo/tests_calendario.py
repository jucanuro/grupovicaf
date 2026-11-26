"""Icono del calendario del LIMS en la barra superior del correo."""
from django.test import override_settings

from .tests_plataforma import HOST, BasePlataforma, ruta


@override_settings(ROOT_URLCONF='grupovicaf.urls_lab', SITE_ROLE='lab')
class IconoCalendarioTests(BasePlataforma):
    def test_la_barra_del_correo_enlaza_al_calendario_del_lims(self):
        self.entrar(self.gestor)
        respuesta = self.client.get(ruta('bandeja'), HTTP_HOST=HOST)
        self.assertContains(respuesta, 'aria-label="Calendario de actividades (abre en otra pestaña)"')
        self.assertContains(respuesta, '/actividades/calendario/')
        self.assertContains(respuesta, 'target="_blank" rel="noopener" aria-label="Calendario de actividades')

