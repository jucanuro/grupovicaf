"""Firma con plantilla: datos → HTML de correo seguro."""
from django.test import SimpleTestCase

from . import firma_plantilla as fp
from .models import Firma
from .tests_plataforma import BasePlataforma

DATOS = dict(nombre='Gina Gestora', cargo='Jefa de Laboratorio', telefono='+51 976 000 000',
             correo='gina@grupovicaf.com', direccion='Jr. Lima 123', ciudad='Cajamarca',
             web='https://www.grupovicaf.com', facebook='', instagram='https://instagram.com/vicaf', tiktok='')


class GenerarHtmlTests(SimpleTestCase):
    def test_lleva_los_datos_y_solo_las_redes_llenas(self):
        html = fp.generar_html(fp.limpiar_datos(DATOS))
        for texto in ('Gina Gestora', 'Jefa de Laboratorio', 'mailto:gina@grupovicaf.com', 'tel:+51976000000',
                      'Jr. Lima 123, Cajamarca', 'https://instagram.com/vicaf', 'LogoF'):
            self.assertIn(texto, html)
        self.assertNotIn('Facebook', html)
        self.assertNotIn('TikTok', html)

    def test_escapa_el_texto_y_descarta_enlaces_no_https(self):
        datos = fp.limpiar_datos({**DATOS, 'nombre': '<script>alert(1)</script>', 'web': 'javascript:alert(1)',
                                  'facebook': 'http://facebook.com/x'})
        self.assertEqual(datos['web'], '')
        self.assertEqual(datos['facebook'], '')
        html = fp.generar_html(datos)
        self.assertNotIn('<script>', html)
        self.assertIn('&lt;script&gt;', html)

    def test_sin_cargo_ni_redes_sigue_siendo_una_firma_valida(self):
        html = fp.generar_html(fp.limpiar_datos({'nombre': 'Solo Nombre'}))
        self.assertIn('Solo Nombre', html)
        self.assertNotIn('<a href="https', html)


class FirmaPlantillaVistaTests(BasePlataforma):
    def test_guardar_con_plantilla_arma_el_html_y_guarda_los_datos(self):
        self.entrar(self.gestor)
        self.post('firma_nueva', modo='plantilla', nombre_firma='Completa', ambito='personal',
                  para_nuevos='1', **DATOS)
        firma = Firma.objects.get(usuario=self.gestor)
        self.assertEqual(firma.nombre, 'Completa')
        self.assertEqual(firma.plantilla['cargo'], 'Jefa de Laboratorio')
        self.assertIn('Gina Gestora', firma.html)
        self.assertIn('<table', firma.html)
        self.assertTrue(firma.para_nuevos)

    def test_editar_muestra_los_datos_guardados(self):
        firma = Firma.objects.create(usuario=self.gestor, nombre='Completa', html='<p>x</p>',
                                     plantilla=fp.limpiar_datos(DATOS))
        self.entrar(self.gestor)
        r = self.get('firma_editar', firma.pk)
        self.assertContains(r, 'value="Jefa de Laboratorio"')

    def test_enlace_de_red_sin_https_se_rechaza(self):
        self.entrar(self.gestor)
        self.post('firma_nueva', modo='plantilla', nombre_firma='Mala', ambito='personal',
                  **{**DATOS, 'facebook': 'http://facebook.com/x'})
        self.assertFalse(Firma.objects.filter(usuario=self.gestor).exists())

    def test_el_editor_libre_sigue_funcionando(self):
        self.entrar(self.gestor)
        self.post('firma_nueva', nombre='Libre', html='<p>G.</p>', ambito='personal')
        firma = Firma.objects.get(usuario=self.gestor)
        self.assertIsNone(firma.plantilla)
