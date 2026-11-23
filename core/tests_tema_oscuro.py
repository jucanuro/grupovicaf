"""Modo claro / oscuro del LIMS y del correo (core/tema_oscuro.py, static/js/tema.js)."""
from io import StringIO
from pathlib import Path

from django.conf import settings
from django.contrib.auth.models import User
from django.core.management import call_command
from django.test import TestCase, SimpleTestCase

from core.tema_oscuro import CLASE_RE, color_oscuro, generar_css


class GeneradorTemaOscuroTests(SimpleTestCase):
    def test_hoja_generada_esta_al_dia(self):
        # Si falla: alguien agregó clases de color en una plantilla del LIMS.
        # Solución: python manage.py generar_tema_oscuro (y commitear el CSS).
        call_command('generar_tema_oscuro', '--comprobar', stdout=StringIO())

    def test_grises_se_invierten_y_colores_pasan_a_velo(self):
        self.assertEqual(color_oscuro('bg', 'white', None, 1.0), 'rgb(17 26 43)')
        self.assertEqual(color_oscuro('text', 'slate', '900', 1.0), 'rgb(241 245 249)')
        # Fondo pastel → velo translúcido del mismo tono; texto oscuro → tono claro.
        self.assertEqual(color_oscuro('bg', 'blue', '50', 1.0), 'rgb(59 130 246 / 0.12)')
        self.assertEqual(color_oscuro('text', 'emerald', '700', 1.0), 'rgb(110 231 183)')
        # Lo saturado o ya claro no cambia (botones bg-blue-600 con texto blanco).
        self.assertEqual(color_oscuro('bg', 'blue', '600', 1.0), 'rgb(37 99 235)')
        self.assertEqual(color_oscuro('text', 'white', None, 1.0), 'rgb(255 255 255)')
        # Velos blancos casi transparentes sobre fondos oscuros: sin cambio.
        self.assertEqual(color_oscuro('bg', 'white', None, 0.1), 'rgb(255 255 255 / 0.1)')

    def test_reconoce_variantes_y_no_confunde_palabras(self):
        clases = [m.group(0) for m in CLASE_RE.finditer(
            'class="hover:bg-slate-50 md:text-slate-700 bg-white/80 group-hover:text-blue-600 '
            'text-[#1c5cab]" data-x="background-white texto-slate-500"')]
        self.assertEqual(clases, ['hover:bg-slate-50', 'md:text-slate-700', 'bg-white/80',
                                  'group-hover:text-blue-600', 'text-[#1c5cab]'])

    def test_reglas_solo_bajo_html_dark_y_respetan_el_papel(self):
        css = generar_css()
        self.assertIn('html.dark .bg-white:not(.tema-claro *) {', css)
        self.assertIn('html.dark .hover\\:bg-blue-600:not(.tema-claro *):hover {', css)
        for linea in css.splitlines():
            if '{' in linea and not linea.startswith('@media'):
                self.assertTrue(linea.lstrip().startswith('html.dark '), linea)


class PlantillasConTemaTests(TestCase):
    def test_lims_carga_tema_antes_de_pintar_y_tiene_el_boton(self):
        usuario = User.objects.create_superuser('tema.admin', 'tema@e2e.invalid', 'x-clave-larga-123')
        self.client.force_login(usuario)
        respuesta = self.client.get('/dashboard/')
        html = respuesta.content.decode()
        cabeza = html.split('</head>')[0]
        self.assertIn('js/tema.js', cabeza)
        # Sin defer ni async: corre antes de pintar (evita el parpadeo blanco).
        etiqueta = cabeza[cabeza.index('js/tema.js') - 40: cabeza.index('js/tema.js') + 40]
        self.assertNotIn('defer', etiqueta)
        self.assertIn('css/tema_oscuro.css', cabeza)
        self.assertIn('css/tema_oscuro_utilidades.css', cabeza)
        self.assertIn('data-tema-alternar', html)

    def test_correo_carga_tema_desde_archivo_propio(self):
        base = (Path(settings.BASE_DIR) / 'correo/templates/correo/base.html').read_text(encoding='utf-8')
        self.assertIn("{% static 'js/tema.js' %}", base)
        self.assertNotIn('<script>', base)  # CSP del correo: nada en línea
        app = (Path(settings.BASE_DIR) / 'correo/templates/correo/_app.html').read_text(encoding='utf-8')
        self.assertIn('data-tema-alternar', app)
