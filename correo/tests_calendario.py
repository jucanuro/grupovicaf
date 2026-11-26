"""Icono del calendario del LIMS en la barra superior del correo."""
from django.test import override_settings

from .tests_plataforma import HOST, BasePlataforma, ruta


@override_settings(ROOT_URLCONF='grupovicaf.urls_lab', SITE_ROLE='lab')
class IconoCalendarioTests(BasePlataforma):
    def test_la_barra_del_correo_enlaza_al_calendario_del_lims(self):
        self.entrar(self.gestor)
        respuesta = self.client.get(ruta('bandeja'), HTTP_HOST=HOST)
        self.assertContains(respuesta, 'aria-label="Calendario de actividades"')
        self.assertContains(respuesta, '/actividades/calendario/')
        # Se abre en la misma pestaña: ya hay iconos para ir y volver.
        self.assertNotContains(respuesta, 'aria-label="Calendario de actividades (abre en otra pestaña)"')


@override_settings(ROOT_URLCONF='grupovicaf.urls_lab', SITE_ROLE='lab')
class CalendarioLateralTests(BasePlataforma):
    def test_el_calendario_lateral_enlaza_al_calendario_del_lims(self):
        self.entrar(self.gestor)
        respuesta = self.client.get(ruta('bandeja'), HTTP_HOST=HOST)
        self.assertContains(respuesta, 'data-mini-cal data-url="')
        self.assertContains(respuesta, 'href="http')  # el título del mini calendario lleva al LIMS

    def test_solo_la_cuenta_personal_viene_desplegada(self):
        from .models import AccesoCuenta
        self.lab.personal = True
        self.lab.save(update_fields=['personal'])
        AccesoCuenta.objects.create(usuario=self.gestor, cuenta=self.lab, rol=AccesoCuenta.GESTIONA)
        self.entrar(self.gestor)
        html = self.client.get(ruta('bandeja'), HTTP_HOST=HOST).content.decode()
        bloques = html.split('<details class="grupo-cuenta"')[1:]
        abiertas = [b for b in bloques if b.lstrip().startswith('open')]
        self.assertEqual(len(bloques), 2)
        self.assertEqual(len(abiertas), 1)
        self.assertIn('data-cuenta="laboratorio"', abiertas[0].split('>')[0])


@override_settings(ROOT_URLCONF='grupovicaf.urls_lab', SITE_ROLE='lab')
class IconoDashboardTests(BasePlataforma):
    def test_la_barra_enlaza_al_dashboard_del_lims_en_otra_pestana(self):
        self.entrar(self.gestor)
        html = self.client.get(ruta('bandeja'), HTTP_HOST=HOST).content.decode()
        self.assertIn('aria-label="Dashboard del sistema LIMS (abre en otra pestaña)"', html)
        enlace = html.split('aria-label="Dashboard del sistema LIMS')[0].rsplit('<a ', 1)[1]
        self.assertIn('/dashboard/', enlace)
        self.assertIn('target="_blank"', enlace)
