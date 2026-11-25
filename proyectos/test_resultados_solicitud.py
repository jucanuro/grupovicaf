"""Pantalla «Resultados de la solicitud»: pasos 1-4, registro por línea y
registro a nombre del técnico (formato en papel pasado al sistema)."""
from datetime import date, timedelta

from django.urls import reverse

from proyectos.models import ResultadoEnsayo, SesionEnsayo, SolicitudEnsayo
from proyectos import test_compresion
from proyectos.models import Equipo
from proyectos.test_compresion import CompresionBase, jpeg
from trabajadores.testing import crear_trabajador, rol_con_permisos


class PantallaResultadosTests(CompresionBase):

    def setUp(self):
        super().setUp()
        self.solicitud = self.mia.solicitud
        self.url = reverse('proyectos:resultados_solicitud', args=[self.solicitud.pk])

    def poner_en_proceso(self):
        SolicitudEnsayo.objects.filter(pk=self.solicitud.pk).update(estado='proceso')

    def test_icono_verde_de_la_lista_abre_los_resultados_y_ya_no_finaliza(self):
        self.poner_en_proceso()
        rol = rol_con_permisos('Coordinador', 'ensayos.ver', 'ensayos.ver_todos', 'ensayos.editar')
        user, _ = crear_trabajador('coord', rol)
        self.client.force_login(user)
        r = self.client.get(reverse('proyectos:lista_solicitudes'))
        self.assertContains(r, self.url)
        self.assertContains(r, 'title="Registrar resultados"')
        self.assertNotContains(r, reverse('proyectos:cambiar_estado', args=[self.solicitud.pk, 'finalizado']))

    def test_finalizar_a_mano_sin_resultados_lleva_a_la_pantalla(self):
        self.poner_en_proceso()
        rol = rol_con_permisos('Coordinador', 'ensayos.ver', 'ensayos.ver_todos', 'ensayos.editar')
        user, _ = crear_trabajador('coord', rol)
        self.client.force_login(user)
        r = self.client.post(reverse('proyectos:cambiar_estado', args=[self.solicitud.pk, 'finalizado']))
        self.assertRedirects(r, self.url, fetch_redirect_response=False)
        self.solicitud.refresh_from_db()
        self.assertEqual(self.solicitud.estado, 'proceso')

    def test_el_tecnico_ve_solo_sus_lineas_y_no_el_cliente(self):
        self.poner_en_proceso()
        self.client.force_login(self.user_tec)
        r = self.client.get(self.url)
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, f'data-linea="{self.mia.pk}"')
        self.assertContains(r, f'data-linea="{self.proctor.pk}"')
        self.assertNotContains(r, f'data-linea="{self.ajena.pk}"')
        self.assertContains(r, '1 ensayo más')
        self.assertNotContains(r, 'Constructora Secreta')
        self.assertContains(r, f"{self.url_registro(self.mia)}?desde=solicitud")

    def test_sin_lineas_asignadas_no_entra(self):
        rol = rol_con_permisos('Técnico 3', 'ensayos.ver', 'ensayos.registrar')
        user, _ = crear_trabajador('tecnico3', rol)
        self.client.force_login(user)
        self.assertEqual(self.client.get(self.url).status_code, 403)

    def test_pendiente_pide_iniciar_antes_de_registrar(self):
        self.client.force_login(self.user_sup)
        r = self.client.get(self.url)
        self.assertContains(r, 'data-paso-iniciar')
        self.assertNotContains(r, 'data-registrar')
        self.assertContains(r, 'Constructora Secreta')

    def test_paso_de_revision_lleva_a_aprobar(self):
        self.poner_en_proceso()
        for d in (self.mia, self.ajena, self.proctor):
            ResultadoEnsayo.objects.create(detalle=d, plantilla=ResultadoEnsayo.plantilla_para(d),
                                           estado=ResultadoEnsayo.ESTADO_TERMINADO)
        rol = rol_con_permisos('Jefe', 'ensayos.ver', 'ensayos.ver_todos', 'informes.aprobar')
        user, _ = crear_trabajador('jefe', rol)
        self.client.force_login(user)
        r = self.client.get(self.url)
        self.assertContains(r, '3 de 3 terminados')
        self.assertContains(r, 'data-ir-revision')
        self.assertContains(r, reverse('proyectos:revision_compresion', args=[self.solicitud.pk]))


class RegistroANombreDelTecnicoTests(CompresionBase):
    """Quien recibe el formato en papel lo pasa al sistema a nombre del técnico."""

    MEDIDAS_P1 = test_compresion.TerminarTests.MEDIDAS_P1

    def setUp(self):
        super().setUp()
        SolicitudEnsayo.objects.filter(pk=self.mia.solicitud_id).update(estado='proceso')
        self.sup = self.user_sup.trabajadorprofile
        self.pantalla = reverse('proyectos:resultados_solicitud', args=[self.mia.solicitud_id])

    def abrir_sesion_de(self, perfil):
        datos = {
            'fecha': (date.today() - timedelta(days=1)).isoformat(),
            'temperatura_inicial': '22.5', 'humedad_inicial': '51', 'neopreno_usos': '59-60',
        }
        for campo, tipo in SesionEnsayo.EQUIPOS + SesionEnsayo.ACCESORIOS:
            datos[campo] = Equipo.objects.filter(tipo=tipo).first().pk
        for clave, _, _, esperado in SesionEnsayo.COMPROBACION:
            datos['comp_' + clave] = '1' if esperado else '0'
        url = reverse('proyectos:abrir_sesion_ensayo') + f'?tecnico={perfil.pk}&volver={self.pantalla}'
        return self.client.post(url, datos)

    def terminar(self):
        datos = {'accion': 'terminar', 'fecha_ensayo': (date.today() - timedelta(days=1)).isoformat(),
                 'observaciones': '', **self.MEDIDAS_P1}
        return self.client.post(self.url_registro(self.mia), datos)

    def test_supervisor_abre_la_sesion_y_termina_a_nombre_del_tecnico(self):
        self.client.force_login(self.user_sup)
        r = self.client.get(self.pantalla)
        self.assertContains(r, f'data-sesion-tecnico="{self.tecnico.pk}"')

        r = self.abrir_sesion_de(self.tecnico)
        self.assertRedirects(r, self.pantalla, fetch_redirect_response=False)
        sesion = SesionEnsayo.objects.get()
        self.assertEqual(sesion.tecnico, self.tecnico)
        self.assertEqual(sesion.registrada_por, self.sup)

        r = self.client.get(self.url_registro(self.mia) + '?desde=solicitud')
        self.assertContains(r, 'data-a-nombre-de')
        self.subir_las_cinco(self.mia)
        datos = {'accion': 'terminar', 'fecha_ensayo': (date.today() - timedelta(days=1)).isoformat(),
                 'observaciones': '', **self.MEDIDAS_P1}
        r = self.client.post(self.url_registro(self.mia) + '?desde=solicitud', datos)
        self.assertRedirects(r, self.pantalla, fetch_redirect_response=False)
        e = ResultadoEnsayo.objects.get(detalle=self.mia)
        self.assertTrue(e.terminado)
        self.assertEqual(e.tecnico, self.tecnico)
        self.assertEqual(e.registrado_por, self.sup)
        self.assertEqual(e.sesion, sesion)

    def test_sin_la_sesion_del_tecnico_no_termina(self):
        self.client.force_login(self.user_sup)
        self.subir_las_cinco(self.mia)
        r = self.terminar()
        self.assertFalse(ResultadoEnsayo.objects.get(detalle=self.mia).terminado)
        r = self.client.get(self.url_registro(self.mia))
        self.assertContains(r, 'Ana Ruiz no tiene sesión abierta')

    def test_el_tecnico_no_abre_sesiones_a_nombre_de_otro(self):
        self.client.force_login(self.user_tec)
        self.abrir_sesion_de(self.otro)
        sesion = SesionEnsayo.objects.get()
        self.assertEqual(sesion.tecnico, self.tecnico)
        self.assertIsNone(sesion.registrada_por)

    def test_el_tecnico_registra_lo_suyo_sin_registrado_por(self):
        self.client.force_login(self.user_tec)
        self.abrir_sesion_de(self.tecnico)
        self.subir_las_cinco(self.mia)
        self.terminar()
        e = ResultadoEnsayo.objects.get(detalle=self.mia)
        self.assertTrue(e.terminado)
        self.assertEqual(e.tecnico, self.tecnico)
        self.assertIsNone(e.registrado_por)


class FlujoRealCompresionTests(CompresionBase):
    """Orden del laboratorio, medir todas primero y trazabilidad de correcciones."""

    def setUp(self):
        super().setUp()
        SolicitudEnsayo.objects.filter(pk=self.mia.solicitud_id).update(estado='proceso')
        self.url_medidas = reverse('proyectos:medidas_solicitud', args=[self.mia.solicitud_id])

    def guardar(self, **datos):
        base = {'accion': 'guardar', 'fecha_ensayo': (date.today() - timedelta(days=1)).isoformat()}
        base.update(datos)
        return self.client.post(self.url_registro(self.mia), base)

    def test_el_formulario_sigue_el_orden_del_laboratorio(self):
        self.client.force_login(self.user_tec)
        html = self.client.get(self.url_registro(self.mia)).content.decode()
        # Formulario a la izquierda (datos, medidas, carga, rotura) y las 6 fotos en su panel, en orden de toma.
        orden = ['data-datos-cliente', 'data-medidas', 'data-paso-carga', 'name="carga_kn"', 'data-preliminar',
                 'data-paso-rotura', 'name="tipo_fractura"',
                 'data-slot="antes"', 'data-slot="antes_pizarra"', 'data-slot="durante"', 'data-slot="carga"',
                 'data-slot="despues"', 'data-slot="despues_pizarra"']
        posiciones = [html.index(x) for x in orden]
        self.assertEqual(posiciones, sorted(posiciones))
        self.assertIn('4. Durante el ensayo: lectura del equipo', html)

    def test_corregir_un_dato_queda_en_la_trazabilidad(self):
        self.client.force_login(self.user_tec)
        self.guardar(masa_g='3914')
        e = ResultadoEnsayo.objects.get(detalle=self.mia)
        self.assertEqual(e.cambios.count(), 0)
        self.guardar(masa_g='3941')
        c = e.cambios.get()
        self.assertEqual((c.campo, c.anterior, c.nuevo, c.usuario), ('masa_g', '3914', '3941', self.user_tec))

        rol = rol_con_permisos('Jefe', 'informes.aprobar')
        jefe, _ = crear_trabajador('jefe', rol)
        self.client.force_login(jefe)
        r = self.client.get(reverse('proyectos:revision_compresion', args=[self.mia.solicitud_id]))
        self.assertContains(r, 'data-trazabilidad')
        self.assertContains(r, 'Hay 1 corrección')
        self.assertContains(r, '3914')

    def test_el_tecnico_copia_los_datos_del_cliente_y_se_trazan(self):
        self.client.force_login(self.user_tec)
        muestra = self.mia.muestra
        self.guardar(**{'muestra-fc_diseno': '280', 'muestra-codigo_cliente': 'P-01',
                        'muestra-fecha_fabricacion': muestra.fecha_fabricacion.isoformat(),
                        'muestra-edad_ensayo_dias': '28', 'muestra-elemento_estructural': 'Zapata Z-1'})
        muestra.refresh_from_db()
        self.assertEqual(muestra.fc_diseno, 280)
        self.assertEqual(muestra.codigo_cliente, 'P-01')
        c = ResultadoEnsayo.objects.get(detalle=self.mia).cambios.get(campo='probeta:fc_diseno')
        self.assertEqual((c.anterior, c.nuevo), ('420', '280'))

    def test_foto_reemplazada_queda_en_la_trazabilidad(self):
        self.client.force_login(self.user_tec)
        self.subir(self.mia, 'carga', jpeg(1800, 700))
        self.subir(self.mia, 'carga', jpeg(1800, 700))
        c = ResultadoEnsayo.objects.get(detalle=self.mia).cambios.get()
        self.assertEqual(c.campo, 'foto')

    def test_medir_todas_primero(self):
        self.client.force_login(self.user_sup)
        r = self.client.get(self.url_medidas)
        self.assertContains(r, f'data-fila-medidas="{self.mia.pk}"')
        self.assertContains(r, f'data-fila-medidas="{self.ajena.pk}"')
        self.assertNotContains(r, f'data-fila-medidas="{self.proctor.pk}"')
        r = self.client.post(self.url_medidas, {
            'fecha_ensayo': (date.today() - timedelta(days=1)).isoformat(),
            f'masa_g-{self.mia.pk}': '3914', f'd1-{self.mia.pk}': '102,12', f'd2-{self.mia.pk}': '101.82',
            f'l1-{self.ajena.pk}': '205.32',
        })
        self.assertRedirects(r, reverse('proyectos:resultados_solicitud', args=[self.mia.solicitud_id]),
                             fetch_redirect_response=False)
        e = ResultadoEnsayo.objects.get(detalle=self.mia)
        self.assertEqual(str(e.d1), '102.12')
        self.assertEqual(e.fecha_ensayo, date.today() - timedelta(days=1))
        self.assertEqual(str(ResultadoEnsayo.objects.get(detalle=self.ajena).l1), '205.32')

    def test_medidas_con_error_no_guardan_nada(self):
        self.client.force_login(self.user_tec)
        r = self.client.post(self.url_medidas, {f'masa_g-{self.mia.pk}': '3914', f'd1-{self.mia.pk}': '1020'})
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, 'D1 (mm) debe estar entre')
        self.assertFalse(ResultadoEnsayo.objects.filter(detalle=self.mia).exists())
        # El técnico solo ve sus probetas.
        self.assertNotContains(r, f'data-fila-medidas="{self.ajena.pk}"')


class PlazoEntregaTests(CompresionBase):
    """Oferta FOR-001: probetas se entregan 24 h después del ensayo; sábado → lunes."""

    def test_plazo_de_probetas(self):
        from proyectos.plazos import estado_plazo, plazo_probeta
        self.assertEqual(plazo_probeta(date(2026, 11, 19)), date(2026, 11, 20))  # jueves → viernes
        self.assertEqual(plazo_probeta(date(2026, 11, 20)), date(2026, 11, 21))  # viernes → sábado
        self.assertEqual(plazo_probeta(date(2026, 11, 21)), date(2026, 11, 23))  # sábado → lunes
        self.assertIsNone(plazo_probeta(None))
        self.assertEqual(estado_plazo(date(2026, 11, 20), hoy=date(2026, 11, 21)), 'vencido')
        self.assertEqual(estado_plazo(date(2026, 11, 21), hoy=date(2026, 11, 21)), 'hoy')
        self.assertIsNone(estado_plazo(date(2026, 11, 20), entregado=True, hoy=date(2026, 11, 21)))

    def test_la_pantalla_muestra_el_plazo_y_los_datos_que_faltan(self):
        SolicitudEnsayo.objects.filter(pk=self.mia.solicitud_id).update(estado='proceso')
        ResultadoEnsayo.objects.create(detalle=self.mia, plantilla='compresion',
                                       fecha_ensayo=date.today() - timedelta(days=3))
        type(self.mia.muestra).objects.filter(pk=self.ajena.muestra_id).update(fc_diseno=None)
        self.client.force_login(self.user_sup)
        r = self.client.get(reverse('proyectos:resultados_solicitud', args=[self.mia.solicitud_id]))
        self.assertContains(r, 'data-plazo="vencido"')
        self.assertContains(r, 'data-faltan-datos-cliente')
        self.assertContains(r, self.ajena.muestra.codigo_laboratorio)
