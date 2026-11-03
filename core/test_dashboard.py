"""Pruebas del dashboard del LIMS (specs/VCF-LIMS/requirements.md, REQ-LIMS-*)."""
import tempfile
from datetime import date, datetime, timedelta
from decimal import Decimal

from django.db import connection
from django.test import TestCase, override_settings
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from django.utils import timezone

from clientes.models import Cliente
from proyectos.models import (
    DetalleSolicitudEnsayo,
    InformeFinal,
    MuestraDetalle,
    Proyecto,
    RecepcionMuestra,
    SolicitudEnsayo,
    TipoMuestra,
)
from servicios.models import Cotizacion, CotizacionDetalle, CotizacionGrupo, Servicio
from trabajadores.testing import crear_trabajador, rol_con_permisos

from .dashboard import Periodo, construir_dashboard, periodo_anterior, resolver_periodo

HOY = date(2026, 11, 3)  # martes


class PeriodoTests(TestCase):
    """RN-06 / REQ-LIMS-17."""

    def test_por_defecto_son_los_ultimos_6_meses(self):
        periodo = resolver_periodo({}, HOY)
        self.assertEqual((periodo.clave, periodo.desde, periodo.hasta), ('6m', date(2026, 6, 1), HOY))

    def test_mes_y_12_meses(self):
        self.assertEqual(resolver_periodo({'periodo': 'mes'}, HOY).desde, date(2026, 11, 1))
        self.assertEqual(resolver_periodo({'periodo': '12m'}, HOY).desde, date(2025, 12, 1))

    def test_rango_invertido_se_ordena_e_invalido_cae_al_defecto(self):
        periodo = resolver_periodo({'periodo': 'rango', 'desde': '2026-10-31', 'hasta': '2026-10-01'}, HOY)
        self.assertEqual((periodo.desde, periodo.hasta), (date(2026, 10, 1), date(2026, 10, 31)))
        self.assertEqual(resolver_periodo({'periodo': 'rango', 'desde': 'x'}, HOY).clave, '6m')
        self.assertEqual(resolver_periodo({'periodo': 'raro'}, HOY).clave, '6m')

    def test_periodo_anterior_corre_meses_y_ajusta_fin_de_mes(self):
        anterior = periodo_anterior(resolver_periodo({'periodo': 'mes'}, date(2026, 3, 31)))
        self.assertEqual((anterior.desde, anterior.hasta), (date(2026, 2, 1), date(2026, 2, 28)))

    def test_periodo_anterior_de_un_rango_son_los_dias_previos(self):
        anterior = periodo_anterior(Periodo('rango', date(2026, 10, 11), date(2026, 10, 20)))
        self.assertEqual((anterior.desde, anterior.hasta), (date(2026, 10, 1), date(2026, 10, 10)))


class DatosDashboardMixin:
    """Constructores mínimos de cotizaciones, solicitudes y proyectos."""

    @classmethod
    def setUpTestData(cls):
        cls.cliente = Cliente.objects.create(ruc='20100000001', razon_social='Cliente Dashboard SAC')
        rol_jefe = rol_con_permisos('Jefe dashboard', 'ensayos.ver', 'ensayos.ver_todos')
        cls.user_jefe, cls.perfil_jefe = crear_trabajador('jefe.dashboard', rol_jefe)
        rol_tecnico = rol_con_permisos('Técnico dashboard', 'ensayos.ver')
        cls.user_tecnico, cls.perfil_tecnico = crear_trabajador('tecnico.dashboard', rol_tecnico)
        cls.servicio = Servicio.objects.create(codigo_facturacion='DSH-1', nombre='Proctor', precio_base=Decimal('100'))
        cls.cot_base = cls._cot('Aceptada', date(2020, 1, 1), numero='BASE')
        grupo = CotizacionGrupo.objects.create(cotizacion=cls.cot_base, nombre_grupo='Suelos')
        cls.detalle_cot = CotizacionDetalle.objects.create(
            grupo=grupo, servicio=cls.servicio, descripcion_especifica='Proctor', precio_unitario=Decimal('100'),
        )
        cls.tipo_muestra = TipoMuestra.objects.create(nombre='Suelo dashboard', sigla='SDB')
        cls._n = 0

    @classmethod
    def _cot(cls, estado, fecha, cliente=None, plantilla=False, numero=None):
        cls._contador = getattr(cls, '_contador', 0) + 1
        return Cotizacion.objects.create(
            cliente=cliente or cls.cliente, estado=estado, fecha_generacion=fecha, es_plantilla=plantilla,
            numero_oferta=numero or f'DSH-{cls._contador:04d}', asunto_servicio='Ensayos',
            persona_contacto='Ana', correo_contacto='ana@example.com', telefono_contacto='999999999',
        )

    def _solicitud(self, codigo, estado='pendiente', fecha=HOY, entrega=HOY + timedelta(days=10), tecnico=None,
                   entrega_real=None):
        recepcion = RecepcionMuestra.objects.create(
            cotizacion=self.cot_base, procedencia='Cajamarca', responsable_cliente='Ana', telefono='999',
            responsable_recepcion=self.user_jefe,
        )
        muestra = MuestraDetalle.objects.create(
            recepcion=recepcion, tipo_muestra=self.tipo_muestra, descripcion='M', masa_aprox=Decimal('1'),
        )
        solicitud = SolicitudEnsayo.objects.create(
            codigo_solicitud=codigo, recepcion=recepcion, cotizacion=self.cot_base, estado=estado,
            fecha_solicitud=fecha, fecha_entrega_programada=entrega, elaborado_por=self.perfil_jefe,
        )
        DetalleSolicitudEnsayo.objects.create(
            solicitud=solicitud, muestra=muestra, servicio_cotizado=self.detalle_cot, descripcion_ensayo='Proctor',
            norma='ASTM', tecnico_asignado=tecnico, fecha_entrega_programada=entrega, fecha_entrega_real=entrega_real,
        )
        return solicitud

    def _proyecto(self, codigo, estado, fecha=HOY):
        return Proyecto.objects.create(
            nombre_proyecto=codigo, codigo_proyecto=codigo, cliente=self.cliente, estado=estado, fecha_inicio=fecha,
        )

    def _dashboard(self, params=None, user=None):
        return construir_dashboard(resolver_periodo(params or {}, HOY), user or self.user_jefe, HOY)


class ComercialTests(DatosDashboardMixin, TestCase):
    """REQ-LIMS-03, 06 a 08, 11 y 25."""

    def test_embudo_tasa_y_conversion(self):
        for estado, n in (('Pendiente', 2), ('Enviada', 3), ('Aceptada', 4), ('Rechazada', 1), ('Anulada', 1)):
            for _ in range(n):
                self._cot(estado, date(2026, 10, 15))
        self._cot('Aceptada', date(2026, 10, 15), plantilla=True)  # REQ-LIMS-25

        comercial = self._dashboard()['comercial']

        self.assertEqual(comercial['emitidas'], 11)
        self.assertEqual(comercial['enviadas'], 8)  # RN-02: 3 enviadas + 4 aceptadas + 1 rechazada
        self.assertEqual(comercial['aceptadas'], 4)
        self.assertEqual(comercial['en_gestion'], 5)
        self.assertEqual(comercial['tasa_aceptacion'], 80)  # 4 / (4 + 1)
        self.assertEqual(comercial['conversion_global'], 36)  # 4 / 11
        self.assertEqual([e['etiqueta'] for e in comercial['embudo']], ['Emitidas', 'Enviadas al cliente', 'Aceptadas'])
        self.assertEqual([e['ancho'] for e in comercial['embudo']], [100.0, 72.7, 36.4])

    def test_tasa_sin_decididas_es_none(self):
        self._cot('Pendiente', date(2026, 10, 15))
        comercial = self._dashboard()['comercial']
        self.assertIsNone(comercial['tasa_aceptacion'])
        self.assertEqual(comercial['conversion_global'], 0)

    def test_sin_cotizaciones_no_hay_datos(self):
        comercial = self._dashboard({'periodo': 'mes'})['comercial']
        self.assertFalse(comercial['tiene_datos'])
        self.assertIsNone(comercial['conversion_global'])

    def test_barras_por_mes_y_estado(self):
        self._cot('Aceptada', date(2026, 9, 2))
        self._cot('Pendiente', date(2026, 9, 3))
        self._cot('Enviada', date(2026, 10, 1))
        self._cot('Anulada', date(2026, 10, 2))
        self._cot('Rechazada', date(2026, 10, 3))

        por_mes = self._dashboard()['comercial']['por_mes']

        self.assertEqual([m['etiqueta'] for m in por_mes], ['Jun', 'Jul', 'Ago', 'Set', 'Oct', 'Nov'])
        septiembre, octubre = por_mes[3], por_mes[4]
        self.assertEqual((septiembre['aceptadas'], septiembre['en_gestion'], septiembre['perdidas']), (1, 1, 0))
        self.assertEqual((octubre['aceptadas'], octubre['en_gestion'], octubre['perdidas']), (0, 1, 2))

    def test_diferencia_contra_el_periodo_anterior(self):
        for _ in range(3):
            self._cot('Pendiente', date(2026, 11, 2))
        self._cot('Pendiente', date(2026, 10, 2))  # mismo tramo (1-3) del mes anterior
        self._cot('Pendiente', date(2026, 10, 20))  # fuera del tramo comparable

        comercial = self._dashboard({'periodo': 'mes'})['comercial']

        self.assertEqual((comercial['emitidas'], comercial['emitidas_anterior']), (3, 1))
        self.assertEqual((comercial['tendencia'], comercial['diferencia']), ('sube', 2))


class ClientesTests(DatosDashboardMixin, TestCase):
    """REQ-LIMS-02 / RN-05."""

    def test_nuevo_es_el_de_la_primera_cotizacion_en_el_periodo(self):
        antiguo = Cliente.objects.create(ruc='20100000002', razon_social='Antiguo')
        nuevo = Cliente.objects.create(ruc='20100000003', razon_social='Nuevo')
        Cliente.objects.create(ruc='20100000004', razon_social='Sin cotizaciones')
        self._cot('Pendiente', date(2025, 1, 10), cliente=antiguo)
        self._cot('Pendiente', date(2026, 10, 10), cliente=antiguo)
        self._cot('Pendiente', date(2026, 10, 12), cliente=nuevo)
        self._cot('Pendiente', date(2026, 10, 1), cliente=antiguo, plantilla=True)

        clientes = self._dashboard()['clientes']

        self.assertEqual(clientes['total'], 4)  # incluye el del setUp
        self.assertEqual(clientes['nuevos_periodo'], 1)
        self.assertEqual(len(clientes['sparkline_valores']), 12)
        self.assertEqual(clientes['sparkline_valores'][-2], {'etiqueta': 'Oct 2026', 'cantidad': 1})


class LaboratorioTests(DatosDashboardMixin, TestCase):
    """REQ-LIMS-12 a 15."""

    def test_segmentos_por_estado(self):
        self._solicitud('S-1', 'pendiente')
        self._solicitud('S-2', 'proceso')
        self._solicitud('S-3', 'finalizado')
        self._solicitud('S-4', 'finalizado')
        self._solicitud('S-5', 'finalizado', fecha=date(2025, 1, 1))  # fuera del periodo

        laboratorio = self._dashboard()['laboratorio']

        self.assertEqual(laboratorio['solicitudes_total'], 4)
        self.assertEqual([s['cantidad'] for s in laboratorio['segmentos']], [1, 1, 2])

    def test_vencidas_ordenadas_por_atraso_y_maximo_cinco(self):
        for dias in (1, 7, 3, 9, 2, 5):
            self._solicitud(f'V-{dias}', 'proceso', entrega=HOY - timedelta(days=dias))
        self._solicitud('V-FIN', 'finalizado', entrega=HOY - timedelta(days=30))
        self._solicitud('V-HOY', 'pendiente', entrega=HOY)

        laboratorio = self._dashboard()['laboratorio']

        self.assertEqual(laboratorio['vencidas_total'], 6)
        self.assertEqual([v['codigo'] for v in laboratorio['vencidas']], ['V-9', 'V-7', 'V-5', 'V-3', 'V-2'])
        self.assertEqual(laboratorio['vencidas'][0]['dias_atraso'], 9)

    def test_tecnico_sin_ver_todos_solo_ve_sus_vencidas(self):
        self._solicitud('V-MIA', entrega=HOY - timedelta(days=2), tecnico=self.perfil_tecnico)
        self._solicitud('V-AJENA', entrega=HOY - timedelta(days=4))

        laboratorio = self._dashboard(user=self.user_tecnico)['laboratorio']

        self.assertEqual(laboratorio['vencidas_total'], 1)
        self.assertEqual([v['codigo'] for v in laboratorio['vencidas']], ['V-MIA'])

    def test_ensayos_finalizados_por_semana(self):
        self._solicitud('E-1', 'finalizado', entrega_real=HOY)  # semana actual
        self._solicitud('E-2', 'finalizado', entrega_real=HOY - timedelta(days=1))  # lunes, misma semana
        self._solicitud('E-3', 'finalizado', entrega_real=HOY - timedelta(days=8))  # semana anterior
        self._solicitud('E-4', 'finalizado', entrega_real=HOY - timedelta(weeks=20))  # fuera de la ventana

        semanas = self._dashboard()['laboratorio']['ensayos_semana']

        self.assertEqual(len(semanas), 12)
        self.assertEqual([s['cantidad'] for s in semanas[-2:]], [1, 2])
        self.assertEqual(semanas[-1]['etiqueta'], 'Sem. 45')


class ProyectosTests(DatosDashboardMixin, TestCase):
    """REQ-LIMS-16 y 21."""

    def test_etapas_leidas_de_proyecto_estado(self):
        self._proyecto('P-1', 'EN_CURSO')
        self._proyecto('P-2', 'EN_CURSO')
        self._proyecto('P-3', 'CANCELADO')
        self._proyecto('P-4', 'FINALIZADO', fecha=date(2024, 1, 1))  # fuera del periodo

        proyectos = self._dashboard()['proyectos']

        etapas = {e['clave']: e for e in proyectos['etapas']}
        self.assertEqual(proyectos['total'], 3)
        self.assertEqual((etapas['EN_CURSO']['cantidad'], etapas['EN_CURSO']['ancho']), (2, 100.0))
        self.assertEqual((etapas['CANCELADO']['cantidad'], etapas['CANCELADO']['ancho']), (1, 50.0))
        self.assertEqual(etapas['CANCELADO']['color'], '#a9a8a1')
        self.assertEqual(etapas['FINALIZADO']['cantidad'], 0)

    def test_consultas_no_crecen_con_los_datos(self):
        self._proyecto('Q-1', 'PENDIENTE')
        self._solicitud('Q-S1', entrega=HOY - timedelta(days=1))
        with CaptureQueriesContext(connection) as pocas:
            self._dashboard()
        for i in range(10):
            self._proyecto(f'Q-P{i}', 'EN_CURSO')
            self._solicitud(f'Q-S{i + 2}', 'proceso', entrega=HOY - timedelta(days=i + 2))
            self._cot('Aceptada', date(2026, 10, 1))
        with CaptureQueriesContext(connection) as muchas:
            self._dashboard()
        self.assertEqual(len(pocas), len(muchas))


@override_settings(ROOT_URLCONF='grupovicaf.urls_lab')
class VistaDashboardTests(DatosDashboardMixin, TestCase):
    """REQ-LIMS-01, 05, 10, 18 y 19 sobre el HTML."""

    def test_html_del_dashboard(self):
        self._cot('Aceptada', date(2026, 10, 1))
        self.client.force_login(self.user_jefe)

        respuesta = self.client.get(reverse('dashboard'))
        html = respuesta.content.decode()

        self.assertEqual(respuesta.status_code, 200)
        for kpi in ('Clientes registrados', 'Cotizaciones emitidas', 'Tasa de aceptación',
                    'Solicitudes vencidas', 'Informes por enviar'):
            self.assertIn(kpi, html)
        self.assertNotIn('del objetivo', html)
        self.assertIn('vendor/chartjs/chart.umd.js', html)
        self.assertNotIn('cdn.jsdelivr.net/npm/chart.js', html)
        self.assertNotIn('@phosphor-icons', html)
        self.assertIn('id="dashboard-datos"', html)
        self.assertIn('Ver como tabla', html)

    def test_periodo_invalido_no_rompe_la_vista(self):
        self.client.force_login(self.user_jefe)
        respuesta = self.client.get(reverse('dashboard'), {'periodo': 'rango', 'desde': '2026-99-99'})
        self.assertEqual(respuesta.status_code, 200)

    @override_settings(MEDIA_ROOT=tempfile.mkdtemp())
    def test_informes_por_enviar(self):
        solicitud = self._solicitud('I-1', 'finalizado')
        InformeFinal.objects.create(
            solicitud=solicitud, archivo_pdf='x.pdf', responsable_firma=self.perfil_jefe,
            fecha_emision=timezone.make_aware(datetime(2026, 10, 20, 10, 0)),
        )

        informes = self._dashboard()['informes']

        self.assertEqual(informes, {'por_enviar': 1, 'emitidos_periodo': 1})
