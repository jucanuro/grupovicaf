"""Avance por muestra en el panel de proyectos (HU-LIMS-19, REQ-LIMS-44 a 52)."""
from datetime import date, timedelta
from decimal import Decimal

from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext
from django.urls import reverse

from clientes.models import Cliente
from proyectos.avance import calcular_avance
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

PERMISOS_TODOS = (
    'proyectos.ver', 'muestras.ver', 'muestras.crear', 'ensayos.ver', 'ensayos.ver_todos',
    'ensayos.crear', 'informes.ver', 'informes.aprobar',
)


class AvanceMixin:
    @classmethod
    def setUpTestData(cls):
        cls.cliente = Cliente.objects.create(ruc='20100000077', razon_social='Constructora Avance SAC')
        cls.user, cls.perfil = crear_trabajador('jefe.avance', rol_con_permisos('Jefe avance', *PERMISOS_TODOS))
        cls.servicio = Servicio.objects.create(codigo_facturacion='AV-1', nombre='Compresión', precio_base=Decimal('30'))
        cls.tipo = TipoMuestra.objects.create(nombre='Probeta avance', sigla='PAV')

    _n = 0

    def _proyecto(self, previstas, con_cotizacion=True):
        AvanceMixin._n += 1
        n = AvanceMixin._n
        cot = None
        if con_cotizacion:
            cot = Cotizacion.objects.create(
                cliente=self.cliente, estado='Aceptada', numero_oferta=f'AV-{n:04d}', asunto_servicio='Ensayos',
                persona_contacto='Ana', correo_contacto='ana@example.com', telefono_contacto='999',
            )
            grupo = CotizacionGrupo.objects.create(cotizacion=cot, nombre_grupo='Concreto')
            cot.detalle_ = CotizacionDetalle.objects.create(
                grupo=grupo, servicio=self.servicio, descripcion_especifica='Compresión',
                precio_unitario=Decimal('30'), cantidad=previstas,
            )
        proyecto = Proyecto.objects.create(
            nombre_proyecto=f'Proyecto avance {n}', codigo_proyecto=f'P-AV-{n:04d}', cliente=self.cliente,
            cotizacion=cot, numero_muestras=previstas,
        )
        proyecto.cot_ = cot
        return proyecto

    def _recepcion(self, proyecto, muestras):
        recepcion = RecepcionMuestra.objects.create(
            cotizacion=proyecto.cot_, procedencia='Cajamarca', responsable_cliente='Ana', telefono='999',
            responsable_recepcion=self.user,
        )
        lista = [
            MuestraDetalle.objects.create(recepcion=recepcion, tipo_muestra=self.tipo, nro_item=i + 1,
                                          descripcion='Probeta', masa_aprox=Decimal('1'))
            for i in range(muestras)
        ]
        return recepcion, lista

    def _solicitud(self, proyecto, recepcion, muestras, estado='proceso', informe=False):
        AvanceMixin._n += 1
        hoy = date.today()
        solicitud = SolicitudEnsayo.objects.create(
            codigo_solicitud=f'SOL-AV-{AvanceMixin._n:04d}', recepcion=recepcion, cotizacion=proyecto.cot_,
            estado=estado, fecha_entrega_programada=hoy + timedelta(days=5), elaborado_por=self.perfil,
        )
        for muestra in muestras:
            DetalleSolicitudEnsayo.objects.create(
                solicitud=solicitud, muestra=muestra, servicio_cotizado=proyecto.cot_.detalle_,
                descripcion_ensayo='Compresión', norma='ASTM C39', fecha_entrega_programada=hoy,
            )
        if informe:
            InformeFinal.objects.create(solicitud=solicitud, archivo_pdf='x.pdf', responsable_firma=self.perfil)
        return solicitud

    def _avance(self, proyecto, user=None):
        return calcular_avance([Proyecto.objects.get(pk=proyecto.pk)], user or self.user)[0].avance

    @staticmethod
    def _conteo(avance):
        return {e['clave']: e['cantidad'] for e in avance['etapas']}


class CalculoAvanceTests(AvanceMixin, TestCase):

    def test_cuenta_cada_muestra_en_su_etapa(self):
        """REQ-LIMS-44 y 45: 10 previstas = 5 por ingresar, 1 recibida, 2 en ensayo, 2 con informe."""
        proyecto = self._proyecto(10)
        rec1, muestras1 = self._recepcion(proyecto, 2)
        self._solicitud(proyecto, rec1, muestras1, estado='finalizado', informe=True)
        rec2, muestras2 = self._recepcion(proyecto, 3)
        self._solicitud(proyecto, rec2, muestras2[:2])

        avance = self._avance(proyecto)

        self.assertEqual(
            self._conteo(avance), {'por_ingresar': 5, 'recibida': 1, 'en_ensayo': 2, 'informe': 2},
        )
        self.assertEqual([e['clave'] for e in avance['etapas']], ['por_ingresar', 'recibida', 'en_ensayo', 'informe'])
        # RN-10: (1×1 + 2×2 + 2×3) / (10×3) = 11/30 → 37 %
        self.assertEqual(avance['porcentaje'], 37)
        self.assertFalse(avance['completo'])

    def test_mas_muestras_registradas_que_previstas_no_da_negativos(self):
        proyecto = self._proyecto(1)
        self._recepcion(proyecto, 3)
        avance = self._avance(proyecto)
        self.assertEqual(self._conteo(avance)['por_ingresar'], 0)
        self.assertEqual(avance['total'], 3)

    def test_todas_con_informe_es_100_y_completo(self):
        """REQ-LIMS-50."""
        proyecto = self._proyecto(2)
        rec, muestras = self._recepcion(proyecto, 2)
        self._solicitud(proyecto, rec, muestras, estado='finalizado', informe=True)
        avance = self._avance(proyecto)
        self.assertEqual(avance['porcentaje'], 100)
        self.assertTrue(avance['completo'])
        self.assertEqual(avance['accion']['tipo'], 'completo')
        self.assertEqual(avance['accion']['url'], f"{reverse('proyectos:lista_informes')}?proyecto={proyecto.pk}")

    def test_sin_cotizacion(self):
        avance = self._avance(self._proyecto(0, con_cotizacion=False))
        self.assertTrue(avance['sin_cotizacion'])
        self.assertIsNone(avance['accion'])

    def test_enlaces_de_cada_etapa(self):
        """REQ-LIMS-46: cada número abre su pantalla filtrada al proyecto."""
        proyecto = self._proyecto(3)
        urls = {e['clave']: e['url'] for e in self._avance(proyecto)['etapas']}
        self.assertEqual(urls, {
            'por_ingresar': reverse('proyectos:crear_recepcion_desde_proyecto', args=[proyecto.pk]),
            'recibida': f"{reverse('proyectos:lista_recepciones')}?proyecto={proyecto.pk}",
            'en_ensayo': f"{reverse('proyectos:lista_solicitudes')}?proyecto={proyecto.pk}",
            'informe': f"{reverse('proyectos:lista_informes')}?proyecto={proyecto.pk}",
        })

    def test_sin_permiso_la_etapa_no_es_enlace(self):
        """REQ-LIMS-51."""
        user, _ = crear_trabajador('solo.proyectos', rol_con_permisos('Solo proyectos', 'proyectos.ver'))
        avance = self._avance(self._proyecto(3), user)
        self.assertTrue(all(e['url'] is None for e in avance['etapas']))
        self.assertFalse(avance['accion']['permiso'])

    def test_numero_fijo_de_consultas(self):
        """REQ-LIMS-52: las consultas no crecen con los proyectos."""
        for _ in range(3):
            p = self._proyecto(4)
            rec, muestras = self._recepcion(p, 2)
            self._solicitud(p, rec, muestras)
        proyectos = list(Proyecto.objects.all())
        with CaptureQueriesContext(connection) as pocos:
            calcular_avance(proyectos[:1], self.user)
        with CaptureQueriesContext(connection) as muchos:
            calcular_avance(proyectos, self.user)
        self.assertEqual(len(pocos), len(muchos))


class AccionUrgenteTests(AvanceMixin, TestCase):
    """REQ-LIMS-47 a 49 (RN-11)."""

    def test_primero_registrar_las_que_faltan(self):
        proyecto = self._proyecto(8)
        self._recepcion(proyecto, 3)
        accion = self._avance(proyecto)['accion']
        self.assertEqual((accion['tipo'], accion['texto']), ('registrar', 'Registrar 5 muestras'))
        self.assertEqual(accion['url'], reverse('proyectos:crear_recepcion_desde_proyecto', args=[proyecto.pk]))

    def test_luego_emitir_informe_pendiente(self):
        proyecto = self._proyecto(2)
        rec, muestras = self._recepcion(proyecto, 2)
        solicitud = self._solicitud(proyecto, rec, muestras, estado='finalizado')
        accion = self._avance(proyecto)['accion']
        self.assertEqual((accion['tipo'], accion['texto']), ('informe', 'Revisar y emitir informe'))
        self.assertEqual(accion['url'], reverse('proyectos:revision_compresion', args=[solicitud.pk]))

    def test_luego_asignar_ensayos_a_las_recibidas(self):
        proyecto = self._proyecto(1)
        self._recepcion(proyecto, 1)
        accion = self._avance(proyecto)['accion']
        self.assertEqual((accion['tipo'], accion['texto']), ('solicitud', 'Asignar ensayos a 1 muestra'))
        self.assertEqual(accion['url'], f"{reverse('proyectos:crear_solicitud')}?proyecto={proyecto.pk}")

    def test_luego_seguir_las_que_estan_en_ensayo(self):
        proyecto = self._proyecto(2)
        rec, muestras = self._recepcion(proyecto, 2)
        self._solicitud(proyecto, rec, muestras)
        accion = self._avance(proyecto)['accion']
        self.assertEqual((accion['tipo'], accion['texto']), ('ensayo', 'Seguir 2 muestras en ensayo'))

    def test_sin_muestras_previstas_ofrece_registrar(self):
        accion = self._avance(self._proyecto(0))['accion']
        self.assertEqual((accion['tipo'], accion['texto']), ('registrar', 'Registrar muestras'))


class PantallasFiltradasTests(AvanceMixin, TestCase):
    """REQ-LIMS-46: las pantallas destino respetan ?proyecto=<id>."""

    def setUp(self):
        self.client.force_login(self.user)
        self.p1 = self._proyecto(2)
        rec1, m1 = self._recepcion(self.p1, 2)
        self.s1 = self._solicitud(self.p1, rec1, m1, estado='finalizado', informe=True)
        self.p2 = self._proyecto(2)
        rec2, m2 = self._recepcion(self.p2, 2)
        self.s2 = self._solicitud(self.p2, rec2, m2, estado='finalizado', informe=True)

    def test_solicitudes_filtradas(self):
        r = self.client.get(reverse('proyectos:lista_solicitudes'), {'proyecto': self.p1.pk})
        self.assertEqual(list(r.context['solicitudes']), [self.s1])
        self.assertContains(r, 'data-filtro-proyecto')

    def test_recepciones_filtradas(self):
        r = self.client.get(reverse('proyectos:lista_recepciones'), {'proyecto': self.p1.pk})
        self.assertEqual([x.cotizacion_id for x in r.context['recepciones']], [self.p1.cotizacion_id])

    def test_informes_filtrados(self):
        r = self.client.get(reverse('proyectos:lista_informes'), {'proyecto': self.p2.pk})
        self.assertEqual([i.solicitud_id for i in r.context['informes']], [self.s2.pk])

    def test_valor_invalido_no_filtra(self):
        r = self.client.get(reverse('proyectos:lista_solicitudes'), {'proyecto': 'abc'})
        self.assertEqual(len(r.context['solicitudes']), 2)
        self.assertNotContains(r, 'data-filtro-proyecto')

    def test_panel_muestra_tarjetas_con_etapas(self):
        r = self.client.get(reverse('proyectos:lista_proyectos_pendientes'))
        self.assertContains(r, f'data-proyecto="{self.p1.pk}"')
        self.assertContains(r, 'data-etapa="en_ensayo"')
        self.assertContains(r, f'href="{reverse("proyectos:lista_informes")}?proyecto={self.p1.pk}"')
