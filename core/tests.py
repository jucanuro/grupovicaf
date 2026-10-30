from django.test import TestCase

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
