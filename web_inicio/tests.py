from django.test import TestCase

from servicios.models import Metodo, Norma, Servicio
from siteconfig.models import NegocioConfig

from .views import _metricas_credibilidad


def _valor(etiqueta):
    return next((m['valor'] for m in _metricas_credibilidad() if m['etiqueta'] == etiqueta), None)


class MetricaEnsayosAcreditadosTestCase(TestCase):
    @classmethod
    def setUpTestData(cls):
        norma = Norma.objects.create(codigo='NTP-TEST', nombre='Norma de prueba')
        metodo = Metodo.objects.create(codigo='M-TEST', nombre='Método de prueba')
        for i in range(3):
            Servicio.objects.create(
                codigo_facturacion=f'T{i:03d}', nombre=f'Ensayo {i}',
                norma=norma, metodo=metodo, esta_acreditado=True,
            )

    def test_numero_oficial_manda_sobre_el_conteo(self):
        NegocioConfig.objects.filter(pk=1).update(ensayos_acreditados=6)
        self.assertEqual(_valor('Ensayos acreditados'), '6')

    def test_sin_numero_oficial_cae_al_conteo(self):
        NegocioConfig.objects.filter(pk=1).update(ensayos_acreditados=None)
        self.assertEqual(_valor('Ensayos acreditados'), '3')
