import tempfile
from io import StringIO

from django.contrib.auth.models import User
from django.core.management import CommandError, call_command
from django.test import TestCase, override_settings

from proyectos.models import InformeFinal, SolicitudEnsayo
from web_catalogo.models import ServicioPublicado

from .models import Correlativo, siguiente_correlativo


class SiguienteCorrelativoTests(TestCase):
    def test_serie_nueva_empieza_en_uno(self):
        self.assertEqual(siguiente_correlativo('INF-2026-'), 1)
        self.assertEqual(siguiente_correlativo('INF-2026-'), 2)

    def test_continua_desde_el_mayor_numero_existente(self):
        # El Max() de texto devolvía "999" por encima de "1000".
        existentes = ['VCF-OTE-2026-999', 'VCF-OTE-2026-1000', 'VCF-OTE-2026-050']
        self.assertEqual(siguiente_correlativo('VCF-OTE-2026-', existentes), 1001)

    def test_codigos_existentes_solo_se_leen_la_primera_vez(self):
        siguiente_correlativo('SOL-001-2026', ['SOL-001-2026-005'])
        self.assertEqual(siguiente_correlativo('SOL-001-2026', ['SOL-001-2026-900']), 7)

    def test_series_independientes(self):
        siguiente_correlativo('INF-2026-')
        self.assertEqual(siguiente_correlativo('INF-2027-'), 1)
        self.assertEqual(Correlativo.objects.count(), 2)

    def test_ignora_codigos_sin_numero_final(self):
        self.assertEqual(siguiente_correlativo('X-', ['X-abc', None, 'X-3']), 4)


@override_settings(DEBUG=True, MEDIA_ROOT=tempfile.mkdtemp())
class SembrarE2ETests(TestCase):
    """Datos fijos de Playwright (e2e/datos.js depende de estos valores)."""

    def test_es_idempotente(self):
        call_command('sembrar_e2e', stdout=StringIO())
        call_command('sembrar_e2e', stdout=StringIO())

        self.assertEqual(User.objects.filter(username__startswith='e2e.').count(), 3)
        self.assertEqual(SolicitudEnsayo.objects.filter(codigo_solicitud='SOL-E2E-0001').count(), 1)
        informe = InformeFinal.objects.get()
        self.assertEqual(str(informe.slug_validacion), 'e2e00000-0000-4000-8000-000000000001')
        self.assertTrue(ServicioPublicado.objects.publicados().filter(slug='e2e-proctor-modificado').exists())

    @override_settings(DEBUG=False)
    def test_no_corre_con_debug_false(self):
        with self.assertRaises(CommandError):
            call_command('sembrar_e2e')
        self.assertFalse(User.objects.filter(username__startswith='e2e.').exists())
