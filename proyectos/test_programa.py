"""Programa de ensayos del día (HU-LIMS-24, REQ-LIMS-87 a 96) y pestañas del
panel de proyectos (HU-LIMS-25, REQ-LIMS-97 a 102)."""
from datetime import date, timedelta
from decimal import Decimal

from django.test import TestCase, override_settings
from django.urls import reverse

from proyectos import programa
from proyectos.avance import filtro_fechas_panel
from proyectos.models import (
    CambioResultado, DetalleSolicitudEnsayo, MuestraDetalle, RecepcionMuestra, ResultadoEnsayo, SolicitudEnsayo,
)
from proyectos.test_avance import AvanceMixin
from proyectos.test_compresion import CompresionBase
from trabajadores.testing import crear_trabajador, rol_con_permisos


class ProgramaBase(CompresionBase):
    """En CompresionBase las probetas se moldearon hace 29 días con edad 28: tocaban ayer."""

    def setUp(self):
        super().setUp()
        self.ayer = date.today() - timedelta(days=1)
        self.hoy = date.today()
        self.cliente = self.mia.solicitud.cotizacion.cliente
        self.cliente.codigo_confidencial = 'CLI-0099'
        self.cliente.save(update_fields=['codigo_confidencial'])

    def segunda_recepcion(self, edad, moldeo):
        """Otra recepción (otra solicitud) del mismo cliente, con una probeta de otra edad."""
        cot = self.mia.solicitud.cotizacion
        rec = RecepcionMuestra.objects.create(
            cotizacion=cot, procedencia='Cajamarca', responsable_cliente='Ana', telefono='9',
            responsable_recepcion=self.user_sup, fecha_recepcion=self.mia.solicitud.recepcion.fecha_recepcion,
        )
        sol = SolicitudEnsayo.objects.create(
            codigo_solicitud='SOL-2026-0002', recepcion=rec, cotizacion=cot,
            fecha_entrega_programada=self.hoy, elaborado_por=self.tecnico,
        )
        muestra = MuestraDetalle.objects.create(
            recepcion=rec, tipo_muestra=self.mia.muestra.tipo_muestra, descripcion='Probeta',
            masa_aprox=Decimal('3.9'), fc_diseno=Decimal('210'), fecha_fabricacion=moldeo, edad_ensayo_dias=edad,
        )
        return DetalleSolicitudEnsayo.objects.create(
            solicitud=sol, muestra=muestra, servicio_cotizado=self.mia.servicio_cotizado,
            descripcion_ensayo='Ensayo', norma='ASTM C39', tecnico_asignado=self.tecnico,
            fecha_entrega_programada=self.hoy,
        )


class FechaPrevistaTests(ProgramaBase):

    def test_moldeo_mas_edad(self):
        """RN-12.1."""
        self.assertEqual(programa.fecha_prevista(self.mia.muestra), self.ayer)

    def test_sin_edad_usa_la_fecha_programada_de_la_recepcion(self):
        """RN-12.2."""
        m = self.mia.muestra
        m.edad_ensayo_dias = None
        m.recepcion.fecha_ensayo_programado = self.hoy
        self.assertEqual(programa.fecha_prevista(m), self.hoy)

    def test_sin_datos_no_hay_fecha(self):
        """RN-12.3."""
        m = self.mia.muestra
        m.fecha_fabricacion = None
        self.assertIsNone(programa.fecha_prevista(m))


class ProgramaDiaTests(ProgramaBase):

    def test_junta_probetas_de_varias_solicitudes_y_edades_en_una_hoja_por_cliente(self):
        """REQ-LIMS-87/63: la de 28 días y la de 7 días de otra recepción van juntas."""
        otra = self.segunda_recepcion(7, self.ayer - timedelta(days=7))
        self.client.force_login(self.user_sup)
        r = self.client.get(reverse('proyectos:programa_dia'), {'fecha': self.ayer.isoformat()})
        self.assertEqual(r.status_code, 200)
        grupos = r.context['grupos']
        self.assertEqual(len(grupos), 1)
        self.assertEqual({d.pk for d in grupos[0]['lineas']}, {self.mia.pk, self.ajena.pk, otra.pk})
        self.assertEqual(grupos[0]['edades'], [7, 28])
        self.assertEqual(len(grupos[0]['solicitudes']), 2)
        self.assertContains(r, 'Constructora Secreta SAC')

    def test_solo_compresion(self):
        """REQ-LIMS-87: el Proctor no entra al programa de rotura."""
        self.client.force_login(self.user_sup)
        r = self.client.get(reverse('proyectos:programa_dia'), {'fecha': self.ayer.isoformat()})
        pks = {d.pk for g in r.context['grupos'] for d in g['lineas']}
        self.assertNotIn(self.proctor.pk, pks)

    def test_el_tecnico_ve_lo_suyo_y_el_codigo_del_cliente_no_su_nombre(self):
        """REQ-LIMS-89."""
        self.client.force_login(self.user_tec)
        r = self.client.get(reverse('proyectos:programa_dia'), {'fecha': self.ayer.isoformat()})
        pks = {d.pk for g in r.context['grupos'] for d in g['lineas']}
        self.assertEqual(pks, {self.mia.pk})
        self.assertContains(r, 'CLI-0099')
        self.assertNotContains(r, 'Constructora Secreta')

    def test_hoy_muestra_las_atrasadas(self):
        """RN-13 / REQ-LIMS-90."""
        self.client.force_login(self.user_sup)
        r = self.client.get(reverse('proyectos:programa_dia'))
        self.assertEqual(r.context['atrasadas'], 2)
        self.assertContains(r, '2 atrasadas')

    def test_otro_dia_sin_probetas(self):
        self.client.force_login(self.user_sup)
        r = self.client.get(reverse('proyectos:programa_dia'), {'fecha': (self.hoy + timedelta(days=3)).isoformat()})
        self.assertContains(r, 'data-programa-vacio')

    def test_sin_fecha_se_avisa(self):
        MuestraDetalle.objects.filter(pk=self.mia.muestra_id).update(fecha_fabricacion=None)
        self.client.force_login(self.user_sup)
        r = self.client.get(reverse('proyectos:programa_dia'))
        self.assertEqual(r.context['sin_fecha_total'], 1)
        self.assertContains(r, 'data-sin-fecha')

    def test_terminada_aparece_el_dia_en_que_se_ensayo(self):
        """RN-12: una terminada sale el día real del ensayo, no el previsto."""
        ResultadoEnsayo.objects.create(detalle=self.mia, plantilla=ResultadoEnsayo.PLANTILLA_COMPRESION,
                                       estado=ResultadoEnsayo.ESTADO_TERMINADO, fecha_ensayo=self.hoy)
        self.client.force_login(self.user_sup)
        hoy = self.client.get(reverse('proyectos:programa_dia'))
        ayer = self.client.get(reverse('proyectos:programa_dia'), {'fecha': self.ayer.isoformat()})
        self.assertIn(self.mia.pk, {d.pk for g in hoy.context['grupos'] for d in g['lineas']})
        self.assertNotIn(self.mia.pk, {d.pk for g in ayer.context['grupos'] for d in g['lineas']})
        self.assertEqual(hoy.context['rotas'], 1)

    def test_sin_permiso_no_entra(self):
        self.client.force_login(self.user_com)
        self.assertNotEqual(self.client.get(reverse('proyectos:programa_dia')).status_code, 200)


class HojaClienteTests(ProgramaBase):

    def url(self, fecha=None):
        return reverse('proyectos:programa_cliente', args=[(fecha or self.ayer).isoformat(), self.cliente.pk])

    def test_hoja_lista_datos_del_cliente_y_enlaza_el_registro_con_regreso(self):
        """REQ-LIMS-91/68."""
        self.client.force_login(self.user_sup)
        r = self.client.get(self.url())
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, f'data-linea="{self.mia.pk}"')
        self.assertContains(r, '420 kg/cm²')
        self.assertContains(r, 'data-imprimir')
        self.assertContains(r, 'data-medir-todas')
        self.assertContains(r, f'{self.url_registro(self.mia)}?desde=programa&amp;fecha={self.ayer.isoformat()}')

    def test_el_registro_vuelve_a_la_hoja(self):
        """REQ-LIMS-93."""
        self.client.force_login(self.user_tec)
        r = self.client.get(self.url_registro(self.mia),
                            {'desde': 'programa', 'fecha': self.ayer.isoformat(), 'cliente': self.cliente.pk})
        self.assertEqual(r.context['url_salida'], self.url())
        self.assertContains(r, f'Programa del {self.ayer:%d/%m/%Y}')

    def test_hoja_vacia_vuelve_al_programa(self):
        self.client.force_login(self.user_sup)
        r = self.client.get(self.url(self.hoy + timedelta(days=5)))
        self.assertEqual(r.status_code, 302)

    def test_hoy_incluye_atrasadas_marcadas(self):
        self.client.force_login(self.user_sup)
        r = self.client.get(self.url(self.hoy))
        self.assertContains(r, 'data-atrasada')

    def test_medir_todas_de_varias_solicitudes_con_trazabilidad(self):
        """REQ-LIMS-92/69: un solo formulario guarda las medidas de dos solicitudes."""
        otra = self.segunda_recepcion(7, self.ayer - timedelta(days=7))
        self.client.force_login(self.user_sup)
        url = reverse('proyectos:programa_medidas', args=[self.ayer.isoformat(), self.cliente.pk])
        self.assertEqual(self.client.get(url).status_code, 200)
        datos = {'fecha_ensayo': self.ayer.isoformat()}
        for d in (self.mia, otra):
            datos.update({f'masa_g-{d.pk}': '3914', f'd1-{d.pk}': '102.1', f'd2-{d.pk}': '101.8',
                          f'l1-{d.pk}': '205.3', f'l2-{d.pk}': '205.2', f'l3-{d.pk}': '205.4'})
        r = self.client.post(url, datos)
        self.assertRedirects(r, self.url(), fetch_redirect_response=False)
        for d in (self.mia, otra):
            e = ResultadoEnsayo.objects.get(detalle=d)
            self.assertEqual(e.masa_g, Decimal('3914'))
            self.assertEqual(e.fecha_ensayo, self.ayer)
            self.assertEqual(d.solicitud.__class__.objects.get(pk=d.solicitud_id).estado, 'proceso')
        # Una corrección queda en la trazabilidad.
        datos[f'masa_g-{self.mia.pk}'] = '3920'
        self.client.post(url, datos)
        cambio = CambioResultado.objects.filter(resultado__detalle=self.mia, campo='masa_g').last()
        self.assertIsNotNone(cambio)
        self.assertIn('3920', cambio.nuevo)
        # La hoja ya la muestra como medida.
        r = self.client.get(self.url())
        self.assertContains(r, 'Medida y pesada')

    def test_el_tecnico_no_mide_lo_ajeno(self):
        self.client.force_login(self.user_tec)
        url = reverse('proyectos:programa_medidas', args=[self.ayer.isoformat(), self.cliente.pk])
        r = self.client.get(url)
        self.assertContains(r, f'masa_g-{self.mia.pk}')
        self.assertNotContains(r, f'masa_g-{self.ajena.pk}')


@override_settings(ROOT_URLCONF='grupovicaf.urls_lab')
class PestanasPanelTests(AvanceMixin, TestCase):

    def test_cada_proyecto_en_una_pestana_y_filtra(self):
        """REQ-LIMS-97/73."""
        por_registrar = self._proyecto(3)
        en_ensayo = self._proyecto(2)
        rec, muestras = self._recepcion(en_ensayo, 2)
        self._solicitud(en_ensayo, rec, muestras)
        completo = self._proyecto(1)
        rec2, muestras2 = self._recepcion(completo, 1)
        self._solicitud(completo, rec2, muestras2, estado='finalizado', informe=True)

        self.client.force_login(self.user)
        url = reverse('proyectos:lista_proyectos_pendientes')
        r = self.client.get(url)
        conteo = {p['clave']: p['cantidad'] for p in r.context['pestanas']}
        self.assertEqual(conteo['todos'], 3)
        self.assertEqual(conteo['muestras'], 1)
        self.assertEqual(conteo['ensayo'], 1)
        self.assertEqual(conteo['completos'], 1)
        self.assertContains(r, 'data-pestana="informes"')

        r = self.client.get(url, {'tab': 'ensayo'})
        self.assertEqual([p.pk for p in r.context['proyectos_pendientes']], [en_ensayo.pk])
        r = self.client.get(url, {'tab': 'muestras'})
        self.assertEqual([p.pk for p in r.context['proyectos_pendientes']], [por_registrar.pk])

    def _envejecer(self, proyecto, dias=60):
        """Deja al proyecto sin movimiento reciente (creado y editado hace `dias`)."""
        from datetime import datetime, time, timezone as tz
        antes = datetime.combine(date.today() - timedelta(days=dias), time(12, 0), tzinfo=tz.utc)
        type(proyecto).objects.filter(pk=proyecto.pk).update(creado_en=antes, modificado_en=antes)

    def test_por_defecto_muestra_lo_que_se_manejo_hoy(self):
        """REQ-LIMS-99 / RN-15: sin parámetros el filtro es «Hoy» (proyectos con movimiento hoy)."""
        viejo = self._proyecto(1)
        self._envejecer(viejo)
        nuevo = self._proyecto(1)
        self.client.force_login(self.user)
        url = reverse('proyectos:lista_proyectos_pendientes')
        r = self.client.get(url)
        self.assertEqual(r.context['filtro_fechas']['periodo'], 'hoy')
        self.assertEqual([p.pk for p in r.context['proyectos_pendientes']], [nuevo.pk])
        # Las cantidades de las pestañas salen del mismo filtro.
        self.assertEqual(r.context['pestanas'][0]['cantidad'], 1)

    def test_un_proyecto_viejo_aparece_si_hoy_tuvo_movimiento(self):
        """RN-15: una recepción de hoy en un proyecto de hace 60 días lo trae a «Hoy»."""
        viejo = self._proyecto(2)
        self._envejecer(viejo)
        self.client.force_login(self.user)
        url = reverse('proyectos:lista_proyectos_pendientes')
        self.assertEqual(list(self.client.get(url).context['proyectos_pendientes']), [])
        self._recepcion(viejo, 1)
        self.assertEqual([p.pk for p in self.client.get(url).context['proyectos_pendientes']], [viejo.pk])

    def test_todas_las_fechas_y_rango_propio(self):
        """REQ-LIMS-99: «Todas las fechas» y «Elegir fechas» (por movimiento)."""
        viejo = self._proyecto(1)
        self._envejecer(viejo)
        nuevo = self._proyecto(1)
        self.client.force_login(self.user)
        url = reverse('proyectos:lista_proyectos_pendientes')
        r = self.client.get(url, {'periodo': 'todas'})
        self.assertEqual({p.pk for p in r.context['proyectos_pendientes']}, {viejo.pk, nuevo.pk})
        r = self.client.get(url, {'desde': (date.today() - timedelta(days=90)).isoformat(),
                                  'hasta': (date.today() - timedelta(days=30)).isoformat()})
        self.assertEqual(r.context['filtro_fechas']['periodo'], 'rango')
        self.assertEqual([p.pk for p in r.context['proyectos_pendientes']], [viejo.pk])
        # Las pestañas conservan el periodo.
        self.assertIn('periodo=rango', r.context['pestanas'][1]['url'])

    def test_sin_movimiento_hoy_ofrece_ver_todas_las_fechas(self):
        """REQ-LIMS-101."""
        viejo = self._proyecto(1)
        self._envejecer(viejo)
        self.client.force_login(self.user)
        r = self.client.get(reverse('proyectos:lista_proyectos_pendientes'))
        self.assertContains(r, 'Ningún proyecto con movimiento hoy')
        self.assertContains(r, 'data-ver-todas')

    def test_periodos(self):
        hoy = date(2026, 11, 25)
        self.assertEqual(filtro_fechas_panel({}, hoy)['periodo'], 'hoy')
        f = filtro_fechas_panel({'periodo': 'hoy'}, hoy)
        self.assertEqual((f['desde'], f['hasta']), (hoy, hoy))
        f = filtro_fechas_panel({'periodo': 'todas'}, hoy)
        self.assertEqual((f['desde'], f['hasta']), (None, None))
        f = filtro_fechas_panel({'desde': '2026-11-30', 'hasta': '2026-11-01'}, hoy)
        self.assertEqual((f['periodo'], f['desde'], f['hasta']), ('rango', date(2026, 11, 1), date(2026, 11, 30)))
        self.assertEqual(filtro_fechas_panel({'periodo': 'raro'}, hoy)['periodo'], 'hoy')
        self.assertEqual([p['clave'] for p in f['periodos']], ['hoy', 'todas', 'rango'])


@override_settings(ROOT_URLCONF='grupovicaf.urls_lab')
class SolicitudVariasProbetasTests(AvanceMixin, TestCase):
    """Bug hallado en la prueba de punta a punta: con el mismo ensayo (compresión)
    para varias probetas, la solicitud guardaba solo la primera línea."""

    def test_una_linea_por_probeta_con_el_mismo_ensayo(self):
        proyecto = self._proyecto(3)
        _, muestras = self._recepcion(proyecto, 3)
        user, perfil = crear_trabajador('jefe.sol', rol_con_permisos('Jefe sol', 'ensayos.crear', 'ensayos.editar'))
        self.perfil = perfil
        self.client.force_login(user)
        hoy = date.today().isoformat()
        datos = {
            'cotizacion': proyecto.cot_.pk, 'fecha_solicitud': hoy, 'fecha_entrega_programada': hoy,
            'muestra_id[]': [m.pk for m in muestras],
            'servicio_id[]': [proyecto.cot_.detalle_.pk] * 3,
            'norma[]': ['ASTM C39'] * 3, 'metodo[]': [''] * 3,
            'tecnico_id[]': [self.perfil.pk] * 3, 'entrega_detalle[]': [hoy] * 3,
        }
        self.client.post(reverse('proyectos:crear_solicitud'), datos)
        solicitud = SolicitudEnsayo.objects.get(cotizacion=proyecto.cot_)
        self.assertEqual(solicitud.detalles.count(), 3)
        # Volver a guardar (las filas existentes llegan como ocultas) no duplica.
        self.client.post(reverse('proyectos:editar_solicitud', args=[solicitud.pk]), datos)
        self.assertEqual(solicitud.detalles.count(), 3)


@override_settings(ROOT_URLCONF='grupovicaf.urls_lab')
class SolicitudUnaPantallaTests(AvanceMixin, TestCase):
    """HU-LIMS-32: la solicitud se arma en una pantalla (un ensayo para varias muestras)."""

    def _usuario(self):
        user, perfil = crear_trabajador('jefe.una', rol_con_permisos('Jefe una', 'ensayos.ver', 'ensayos.crear', 'ensayos.editar'))
        self.perfil = perfil
        self.client.force_login(user)

    def test_la_pantalla_trae_el_nuevo_formulario(self):
        proyecto = self._proyecto(2)
        self._recepcion(proyecto, 2)
        self._usuario()
        html = self.client.get(reverse('proyectos:crear_solicitud'), {'proyecto': proyecto.pk}).content.decode()
        for marca in ('id="se-filas"', 'solicitud_ensayo.js', 'id="se-tecnicos"', 'se-todas-muestras'):
            self.assertIn(marca, html)
        self.assertNotIn('sol-tab-btn', html)

    def test_la_api_trae_muestras_con_tipo_y_norma_sin_none(self):
        proyecto = self._proyecto(2)
        self._recepcion(proyecto, 2)
        self._usuario()
        datos = self.client.get(reverse('proyectos:api_cotizacion_detalles', args=[proyecto.cot_.pk])).json()
        self.assertEqual(len(datos['muestras']), 2)
        self.assertIn('tipo_muestra__nombre', datos['muestras'][0])
        for s in datos['servicios_pendientes']:
            self.assertNotEqual(s['metodo'], 'None')
            self.assertNotEqual(s['norma'], 'None')

    def test_un_ensayo_para_varias_muestras_crea_una_linea_por_muestra(self):
        proyecto = self._proyecto(3)
        _, muestras = self._recepcion(proyecto, 3)
        self._usuario()
        hoy = date.today().isoformat()
        self.client.post(reverse('proyectos:crear_solicitud'), {
            'cotizacion': proyecto.cot_.pk, 'fecha_solicitud': hoy, 'fecha_entrega_programada': hoy,
            'muestra_id[]': [m.pk for m in muestras[:2]],
            'servicio_id[]': [proyecto.cot_.detalle_.pk] * 2,
            'norma[]': ['ASTM C39'] * 2, 'metodo[]': [''] * 2,
            'tecnico_id[]': [self.perfil.pk] * 2, 'entrega_detalle[]': [hoy] * 2,
            'incidencia_detalle[]': ['Probeta con fisura'], 'incidencia_fecha[]': [hoy + 'T08:00'],
            'incidencia_cliente[]': ['Ana'], 'incidencia_responsable_id[]': [''], 'incidencia_autorizado[]': ['false'],
        })
        solicitud = SolicitudEnsayo.objects.get(cotizacion=proyecto.cot_)
        self.assertEqual(solicitud.detalles.count(), 2)
        self.assertEqual(solicitud.incidencias.count(), 1)

    def test_editar_muestra_las_incidencias_previas_como_lectura(self):
        proyecto = self._proyecto(1)
        _, muestras = self._recepcion(proyecto, 1)
        self._usuario()
        hoy = date.today().isoformat()
        self.client.post(reverse('proyectos:crear_solicitud'), {
            'cotizacion': proyecto.cot_.pk, 'fecha_solicitud': hoy, 'fecha_entrega_programada': hoy,
            'muestra_id[]': [muestras[0].pk], 'servicio_id[]': [proyecto.cot_.detalle_.pk],
            'norma[]': ['x'], 'metodo[]': [''], 'tecnico_id[]': [self.perfil.pk], 'entrega_detalle[]': [hoy],
            'incidencia_detalle[]': ['Humedad alta'], 'incidencia_fecha[]': [hoy + 'T08:00'],
            'incidencia_cliente[]': [''], 'incidencia_responsable_id[]': [''], 'incidencia_autorizado[]': ['false'],
        })
        solicitud = SolicitudEnsayo.objects.get(cotizacion=proyecto.cot_)
        html = self.client.get(reverse('proyectos:editar_solicitud', args=[solicitud.pk])).content.decode()
        self.assertIn('Humedad alta', html)
