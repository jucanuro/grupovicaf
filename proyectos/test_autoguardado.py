"""Guardado automático del registro de ensayo (HU-LIMS-26, REQ-LIMS-103 a 108):
lo escrito queda guardado sin pulsar «Guardar» y el ensayo se puede continuar."""
from datetime import date, timedelta
from decimal import Decimal

from django.urls import reverse

from proyectos.models import CambioResultado, ResultadoEnsayo
from proyectos.test_compresion import CompresionBase


class AutoGuardadoTests(CompresionBase):

    def autoguardar(self, detalle, **datos):
        datos.setdefault('fecha_ensayo', (date.today() - timedelta(days=1)).isoformat())
        return self.client.post(self.url_registro(detalle), {'accion': 'autoguardar', **datos})

    def test_guarda_lo_escrito_sin_terminar_ni_pedir_sesion(self):
        """REQ-LIMS-103."""
        self.client.force_login(self.user_tec)
        r = self.autoguardar(self.mia, masa_g='3914', d1='102.12', d2='101.82')
        self.assertEqual(r.status_code, 200, r.content)
        self.assertTrue(r.json()['ok'])
        e = ResultadoEnsayo.objects.get(detalle=self.mia)
        self.assertEqual(e.masa_g, Decimal('3914'))
        self.assertEqual(e.d1, Decimal('102.12'))
        self.assertFalse(e.terminado)
        self.assertEqual(e.estado, ResultadoEnsayo.ESTADO_BORRADOR)

    def test_lo_invalido_se_salta_y_lo_demas_se_guarda(self):
        """REQ-LIMS-104: un 10 en diámetro (mínimo 20) no impide guardar la masa."""
        self.client.force_login(self.user_tec)
        r = self.autoguardar(self.mia, masa_g='3914', d1='10')
        self.assertEqual(r.status_code, 200)
        self.assertTrue(any('D1' in o or 'd1' in o.lower() for o in r.json()['omitidos']), r.json())
        e = ResultadoEnsayo.objects.get(detalle=self.mia)
        self.assertEqual(e.masa_g, Decimal('3914'))
        self.assertIsNone(e.d1)

    def test_vuelve_a_la_pantalla_con_lo_guardado(self):
        """REQ-LIMS-105: al reabrir el ensayo aparece lo que se escribió."""
        self.client.force_login(self.user_tec)
        self.autoguardar(self.mia, masa_g='3914', l1='205.3')
        r = self.client.get(self.url_registro(self.mia))
        self.assertContains(r, 'value="3914')
        self.assertContains(r, 'data-autoguardado')

    def test_corregir_un_dato_ya_guardado_queda_en_la_trazabilidad(self):
        """REQ-LIMS-106: el primer guardado no es corrección; el cambio sí."""
        self.client.force_login(self.user_tec)
        self.autoguardar(self.mia, masa_g='3941')
        self.assertFalse(CambioResultado.objects.filter(resultado__detalle=self.mia, campo='masa_g').exists())
        self.autoguardar(self.mia, masa_g='3914')
        cambio = CambioResultado.objects.get(resultado__detalle=self.mia, campo='masa_g')
        self.assertIn('3941', cambio.anterior)
        self.assertIn('3914', cambio.nuevo)

    def test_un_ensayo_terminado_no_se_toca(self):
        self.client.force_login(self.user_tec)
        ResultadoEnsayo.objects.create(detalle=self.mia, plantilla=ResultadoEnsayo.PLANTILLA_COMPRESION,
                                       estado=ResultadoEnsayo.ESTADO_TERMINADO, masa_g=Decimal('3900'))
        r = self.autoguardar(self.mia, masa_g='1')
        self.assertEqual(r.status_code, 409)
        self.assertEqual(ResultadoEnsayo.objects.get(detalle=self.mia).masa_g, Decimal('3900'))

    def test_otro_tecnico_no_guarda_lo_ajeno(self):
        self.client.force_login(self.user_tec)
        self.assertEqual(self.autoguardar(self.ajena, masa_g='3914').status_code, 404)
        self.assertFalse(ResultadoEnsayo.objects.filter(detalle=self.ajena).exists())

    def test_plantilla_general_guarda_resumen_y_observaciones(self):
        self.client.force_login(self.user_tec)
        r = self.autoguardar(self.proctor, resumen='Máxima densidad 1,95', observaciones='Muestra húmeda')
        self.assertEqual(r.status_code, 200, r.content)
        e = ResultadoEnsayo.objects.get(detalle=self.proctor)
        self.assertEqual(e.resumen, 'Máxima densidad 1,95')
        self.assertEqual(e.observaciones, 'Muestra húmeda')
        self.assertFalse(e.terminado)

    def test_la_lista_marca_el_ensayo_en_curso_y_ofrece_continuar(self):
        """REQ-LIMS-107."""
        self.client.force_login(self.user_tec)
        r = self.client.get(reverse('proyectos:mis_ensayos_compresion'))
        self.assertNotContains(r, 'data-continuar')
        self.autoguardar(self.mia, masa_g='3914')
        r = self.client.get(reverse('proyectos:mis_ensayos_compresion'))
        self.assertContains(r, 'data-en-curso')
        self.assertContains(r, 'data-continuar-enlace')
        self.assertContains(r, self.mia.muestra.codigo_laboratorio)


class AutoGuardadoMedidasTests(CompresionBase):

    def setUp(self):
        super().setUp()
        self.url = reverse('proyectos:medidas_solicitud', args=[self.mia.solicitud_id])

    def datos(self, **extra):
        d = {'autoguardar': '1', 'fecha_ensayo': (date.today() - timedelta(days=1)).isoformat()}
        d.update(extra)
        return d

    def test_guarda_las_medidas_escritas_aunque_falten_otras(self):
        """REQ-LIMS-108."""
        self.client.force_login(self.user_sup)
        r = self.client.post(self.url, self.datos(**{f'masa_g-{self.mia.pk}': '3914', f'd1-{self.mia.pk}': '102.1'}))
        self.assertEqual(r.status_code, 200, r.content)
        self.assertTrue(r.json()['ok'])
        e = ResultadoEnsayo.objects.get(detalle=self.mia)
        self.assertEqual(e.masa_g, Decimal('3914'))
        self.assertEqual(e.d1, Decimal('102.1'))
        self.assertFalse(ResultadoEnsayo.objects.filter(detalle=self.ajena).exists())

    def test_no_crea_resultados_vacios_y_salta_lo_invalido(self):
        self.client.force_login(self.user_sup)
        r = self.client.post(self.url, self.datos(**{f'masa_g-{self.mia.pk}': '', f'd1-{self.ajena.pk}': '5'}))
        self.assertEqual(r.status_code, 200)
        self.assertFalse(ResultadoEnsayo.objects.exists())
        self.assertTrue(r.json()['omitidos'])
