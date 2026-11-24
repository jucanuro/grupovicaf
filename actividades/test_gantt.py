"""Gantt de ensayos (HU-LIMS-22): estado, avance real, atraso y entrega."""
from datetime import timedelta

from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from actividades.gantt_ensayos import estado_y_avance
from proyectos.models import DetalleSolicitudEnsayo, FotoEnsayo, ResultadoEnsayo
from proyectos.tests import SolicitudBaseMixin
from trabajadores.testing import crear_trabajador, rol_con_permisos


@override_settings(ROOT_URLCONF='grupovicaf.urls_lab')
class GanttEnsayosTest(SolicitudBaseMixin, TestCase):

    def setUp(self):
        super().setUp()
        self.hoy = timezone.localdate()
        self.detalle = self.solicitud.detalles.get()
        self.solicitud.fecha_solicitud = self.hoy - timedelta(days=10)
        self.solicitud.save(update_fields=['fecha_solicitud'])
        rol = rol_con_permisos('Jefe Gantt', 'gantt.ver', 'ensayos.ver', 'ensayos.ver_todos')
        self.jefe, _ = crear_trabajador('jefe.gantt', rol)

    def _json(self, user=None):
        self.client.force_login(user or self.jefe)
        resp = self.client.get(reverse('actividades:gantt_actividades_json'), {'ensayos': 'true'})
        self.assertEqual(resp.status_code, 200)
        return [x for x in resp.json() if x['tipo'] == 'ensayo']

    def _programar(self, dias):
        DetalleSolicitudEnsayo.objects.filter(pk=self.detalle.pk).update(
            fecha_entrega_programada=self.hoy + timedelta(days=dias))

    # REQ-LIMS-75
    def test_sin_resultado_es_sin_empezar_y_cero(self):
        self.assertEqual(estado_y_avance(None), ('sin_empezar', 0))

    def test_terminado_y_aprobado_son_cien(self):
        r = ResultadoEnsayo(detalle=self.detalle, estado=ResultadoEnsayo.ESTADO_TERMINADO)
        self.assertEqual(estado_y_avance(r), ('terminado', 100))
        r.estado = ResultadoEnsayo.ESTADO_APROBADO
        self.assertEqual(estado_y_avance(r), ('aprobado', 100))

    def test_en_registro_cuenta_datos_y_fotos_cargados(self):
        r = ResultadoEnsayo.objects.create(detalle=self.detalle, plantilla=ResultadoEnsayo.PLANTILLA_GENERAL)
        self.assertEqual(estado_y_avance(r), ('registro', 5))  # nada cargado: el mínimo
        r.fecha_ensayo = self.hoy
        r.resumen = 'Listo'
        r.save()
        total = 3 + len(FotoEnsayo.tipos_de(ResultadoEnsayo.PLANTILLA_GENERAL))
        self.assertEqual(estado_y_avance(r), ('registro', round(2 * 100 / total)))

    def test_devuelto_por_el_revisor(self):
        r = ResultadoEnsayo.objects.create(detalle=self.detalle, observacion_revision='Revisar')
        self.assertEqual(estado_y_avance(r)[0], 'devuelto')

    # REQ-LIMS-76, 77
    def test_linea_atrasada_trae_dias_y_grupo(self):
        self._programar(-4)
        ResultadoEnsayo.objects.create(detalle=self.detalle, fecha_ensayo=self.hoy)
        (linea,) = self._json()
        self.assertEqual(linea['grupo'], 'proc')
        self.assertEqual(linea['estado_linea'], 'registro')
        self.assertEqual(linea['atraso_dias'], 4)
        self.assertTrue(linea['esta_vencido'])
        self.assertEqual(linea['programada'], (self.hoy - timedelta(days=4)).isoformat())

    def test_linea_terminada_no_tiene_atraso(self):
        self._programar(-4)
        ResultadoEnsayo.objects.create(detalle=self.detalle, estado=ResultadoEnsayo.ESTADO_TERMINADO,
                                       fecha_ensayo=self.hoy)
        (linea,) = self._json()
        self.assertEqual(linea['grupo'], 'ok')
        self.assertEqual(linea['avance'], 100)
        self.assertEqual(linea['atraso_dias'], 0)
        self.assertTrue(linea['terminado_mes'])

    def test_programada_antes_de_la_solicitud_no_invierte_la_barra(self):
        self._programar(-20)  # la solicitud es de hace 10 días
        (linea,) = self._json()
        self.assertEqual(linea['start'], linea['end'])
        self.assertEqual(linea['atraso_dias'], 20)

    # REQ-LIMS-78
    def test_entrega_de_la_solicitud_es_la_ultima_fecha_de_sus_lineas(self):
        self._programar(2)
        otra = DetalleSolicitudEnsayo.objects.create(
            solicitud=self.solicitud, muestra=self.detalle.muestra, servicio_cotizado=self.detalle.servicio_cotizado,
            descripcion_ensayo='CBR', norma='MTC E 132', fecha_entrega_programada=self.hoy + timedelta(days=9),
        )
        lineas = self._json()
        self.assertEqual({l['entrega_solicitud'] for l in lineas}, {(self.hoy + timedelta(days=9)).isoformat()})
        self.assertEqual({l['servicio'] for l in lineas}, {'Proctor Modificado', 'CBR'})
        self.assertIn(reverse('proyectos:resultados_solicitud', args=[self.solicitud.pk]), lineas[0]['url_resultados'])
        self.assertTrue(any(l['db_id'] == otra.pk for l in lineas))

    # REQ-LIMS-82
    def test_tecnico_ve_solo_sus_lineas_y_el_codigo_confidencial(self):
        rol = rol_con_permisos('Técnico Gantt', 'gantt.ver', 'ensayos.ver')
        tecnico, perfil = crear_trabajador('tec.gantt', rol)
        otro, _ = crear_trabajador('tec.otro', rol)
        DetalleSolicitudEnsayo.objects.filter(pk=self.detalle.pk).update(tecnico_asignado=perfil)

        (linea,) = self._json(tecnico)
        cliente = self.solicitud.cotizacion.cliente
        self.assertEqual(linea['cliente'], cliente.codigo_confidencial or '')
        self.assertNotIn('Constructora de Prueba SAC', str(linea))
        self.assertEqual(self._json(otro), [])

    def test_la_pantalla_carga_su_css_y_js(self):
        self.client.force_login(self.jefe)
        resp = self.client.get(reverse('actividades:gantt_dashboard'))
        self.assertContains(resp, 'css/gantt.css')
        self.assertContains(resp, 'js/gantt.js')
        self.assertContains(resp, 'id="gantt-app"')

