from datetime import datetime, time
from zoneinfo import ZoneInfo

from django.test import TestCase

from .models import NegocioConfig

LIMA = ZoneInfo('America/Lima')


def lima(año, mes, dia, hora, minuto=0):
    return datetime(año, mes, dia, hora, minuto, tzinfo=LIMA)


class HorarioNegocioTests(TestCase):
    """Horario aprobado en D-VCF-004: L-V 8:00-13:00 y 15:00-18:00, sáb 8:00-13:00."""

    def setUp(self):
        self.negocio = NegocioConfig.objects.get(pk=1)
        self.negocio.whatsapp = '+51 964-326-364'
        self.negocio.horario_semana_apertura = time(8, 0)
        self.negocio.horario_semana_cierre = time(18, 0)
        self.negocio.horario_semana_receso_inicio = time(13, 0)
        self.negocio.horario_semana_receso_fin = time(15, 0)
        self.negocio.horario_sabado_apertura = time(8, 0)
        self.negocio.horario_sabado_cierre = time(13, 0)
        self.negocio.save()

    def test_seed_trae_el_receso_de_mediodia(self):
        fila = NegocioConfig.objects.get(pk=1)
        self.assertEqual(fila.horario_semana_receso_inicio, time(13, 0))
        self.assertEqual(fila.horario_semana_receso_fin, time(15, 0))

    def test_whatsapp_digitos(self):
        self.assertEqual(self.negocio.whatsapp_digitos, '51964326364')
        self.negocio.whatsapp = ''
        self.assertEqual(self.negocio.whatsapp_digitos, '')

    def test_horario_texto(self):
        self.assertEqual(
            self.negocio.horario_texto(),
            'lunes a viernes de 8:00 a 13:00 y de 15:00 a 18:00, sábados de 8:00 a 13:00',
        )

    def test_horario_semana_rango(self):
        self.assertEqual(self.negocio.horario_semana_rango, '08:00–13:00 y 15:00–18:00')
        self.negocio.horario_semana_receso_inicio = None
        self.assertEqual(self.negocio.horario_semana_rango, '08:00–18:00')

    def test_esta_abierto_entre_semana(self):
        # 2026-10-14 es miércoles.
        casos = {
            (7, 59): False, (8, 0): True, (12, 59): True, (13, 0): False,
            (14, 59): False, (15, 0): True, (17, 59): True, (18, 0): False,
        }
        for (hora, minuto), esperado in casos.items():
            with self.subTest(hora=f'{hora}:{minuto:02d}'):
                self.assertEqual(self.negocio.esta_abierto(lima(2026, 10, 14, hora, minuto)), esperado)

    def test_esta_abierto_sabado_y_domingo(self):
        self.assertTrue(self.negocio.esta_abierto(lima(2026, 10, 17, 12, 59)))   # sábado
        self.assertFalse(self.negocio.esta_abierto(lima(2026, 10, 17, 13, 0)))
        self.assertFalse(self.negocio.esta_abierto(lima(2026, 10, 18, 10, 0)))   # domingo

    def test_esta_abierto_usa_hora_de_lima(self):
        # 14:00 UTC = 09:00 en Lima (abierto); 18:30 UTC = 13:30 en Lima (receso).
        utc = ZoneInfo('UTC')
        self.assertTrue(self.negocio.esta_abierto(datetime(2026, 10, 14, 14, 0, tzinfo=utc)))
        self.assertFalse(self.negocio.esta_abierto(datetime(2026, 10, 14, 18, 30, tzinfo=utc)))
