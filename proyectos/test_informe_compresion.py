"""HU-LIMS-15, 16, 18, 19 y 20: revisión, informe PDF, Excel y envío del
ensayo de compresión."""
import shutil
import tempfile
from datetime import date, timedelta
from io import BytesIO
from unittest.mock import patch

from django.core import mail
from django.test import override_settings
from django.urls import reverse
from openpyxl import load_workbook
from pypdf import PdfReader

from proyectos.models import DetalleSolicitudEnsayo, ResultadoEnsayo, FotoEnsayo, InformeFinal, RecepcionMuestra, SolicitudEnsayo
from proyectos.tasks import enviar_informe_cliente, generar_informe_editor
from proyectos.test_compresion import CompresionBase, TerminarTests, jpeg
from trabajadores.testing import crear_trabajador, rol_con_permisos

MEDIA_TMP = tempfile.mkdtemp(prefix='media_test_')


@override_settings(MEDIA_ROOT=MEDIA_TMP, EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')
class InformeCompresionTests(CompresionBase):

    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        shutil.rmtree(MEDIA_TMP, ignore_errors=True)

    def setUp(self):
        super().setUp()
        rol = rol_con_permisos('Jefe de laboratorio', 'informes.aprobar', 'informes.exportar', 'informes.ver')
        self.user_jefe, self.jefe = crear_trabajador('jefe', rol, 'Carla Jefa')
        self.url = reverse('proyectos:revision_compresion', args=[self.mia.solicitud_id])
        # Estas pruebas son del informe de compresión: el Proctor va en otra solicitud.
        rec = self.recepcion
        otra_rec = RecepcionMuestra.objects.create(
            cotizacion=rec.cotizacion, procedencia='Cajamarca', responsable_cliente='Ana',
            telefono='987654321', responsable_recepcion=self.user_sup, fecha_recepcion=rec.fecha_recepcion,
        )
        otra = SolicitudEnsayo.objects.create(
            codigo_solicitud='SOL-2026-0002', recepcion=otra_rec, cotizacion=rec.cotizacion,
            fecha_entrega_programada=date.today(), elaborado_por=self.tecnico,
        )
        DetalleSolicitudEnsayo.objects.filter(pk=self.proctor.pk).update(solicitud=otra)

    def terminar(self, detalle, user):
        self.client.force_login(user)
        self.abrir_sesion()
        for tipo in FotoEnsayo.TIPOS_COMPRESION:
            ancho, alto = FotoEnsayo.PROPORCIONES[tipo]
            self.subir(detalle, tipo, jpeg(ancho * 100, alto * 100))
        self.client.post(self.url_registro(detalle), {
            'accion': 'terminar', 'fecha_ensayo': (date.today() - timedelta(days=1)).isoformat(),
            **TerminarTests.MEDIDAS_P1,
        })
        self.assertTrue(ResultadoEnsayo.objects.get(detalle=detalle).terminado)

    def cerrar_sesion(self, user):
        self.client.force_login(user)
        self.client.post(reverse('proyectos:cerrar_sesion_ensayo'), {'temperatura_final': '19.42', 'humedad_final': '71.04'})

    def terminar_todas(self):
        self.terminar(self.mia, self.user_tec)
        self.terminar(self.ajena, self.user_otro)
        self.cerrar_sesion(self.user_tec)
        self.cerrar_sesion(self.user_otro)
        self.client.force_login(self.user_jefe)

    def test_no_emite_con_sesiones_abiertas(self):
        self.terminar(self.mia, self.user_tec)
        self.terminar(self.ajena, self.user_otro)
        self.client.force_login(self.user_jefe)
        r = self.client.post(self.url, {'accion': 'aprobar'}, follow=True)
        self.assertContains(r, 'Falta cerrar la sesión')
        self.assertFalse(InformeFinal.objects.filter(solicitud=self.mia.solicitud).exists())

    def test_solo_con_informes_aprobar(self):
        self.client.force_login(self.user_tec)
        self.assertEqual(self.client.get(self.url).status_code, 403)
        self.assertEqual(self.client.get(reverse('proyectos:revision_compresion_lista')).status_code, 403)

    def test_no_emite_si_falta_alguna_probeta(self):
        self.terminar(self.mia, self.user_tec)
        self.client.force_login(self.user_jefe)
        r = self.client.get(self.url)
        self.assertContains(r, self.mia.muestra.codigo_laboratorio)
        self.assertNotContains(r, self.proctor.muestra.codigo_laboratorio)
        self.client.post(self.url, {'accion': 'aprobar'})
        self.assertFalse(InformeFinal.objects.filter(solicitud=self.mia.solicitud).exists())

    def test_devolver_con_observacion_reabre_al_tecnico(self):
        self.terminar(self.mia, self.user_tec)
        self.client.force_login(self.user_jefe)
        self.client.post(self.url, {'accion': 'devolver', 'detalle_id': self.mia.pk, 'observacion': ''})
        self.assertTrue(ResultadoEnsayo.objects.get(detalle=self.mia).terminado)
        self.client.post(self.url, {'accion': 'devolver', 'detalle_id': self.mia.pk,
                                    'observacion': 'Repite la foto de la carga, está borrosa.'})
        e = ResultadoEnsayo.objects.get(detalle=self.mia)
        self.assertEqual(e.estado, ResultadoEnsayo.ESTADO_BORRADOR)
        self.client.force_login(self.user_tec)
        self.assertContains(self.client.get(self.url_registro(self.mia)), 'está borrosa')
        self.assertContains(self.client.get(reverse('proyectos:mis_ensayos_compresion')), 'Devuelta')

    def test_el_revisor_abre_el_ensayo_terminado_en_la_pantalla_de_revision(self):
        self.terminar(self.mia, self.user_tec)
        self.client.force_login(self.user_jefe)
        r = self.client.get(reverse('proyectos:revisar_ensayo', args=[self.mia.pk]))
        self.assertEqual(r.status_code, 200)
        for marca in ('data-modo-revision="1"', 'data-form-devolver', 'data-marcar-foto="antes"', 'id="marcas-revision"'):
            self.assertContains(r, marca)
        self.assertTrue(r.context['puede_devolver'])
        # Solo lectura: no acepta cambios por esta ruta.
        self.assertEqual(self.client.post(reverse('proyectos:revisar_ensayo', args=[self.mia.pk])).status_code, 405)
        # El técnico no entra a la revisión.
        self.client.force_login(self.user_tec)
        self.assertEqual(self.client.get(reverse('proyectos:revisar_ensayo', args=[self.mia.pk])).status_code, 403)

    def test_devolver_con_marcas_las_guarda_y_el_tecnico_las_ve_en_rojo(self):
        import json
        self.terminar(self.mia, self.user_tec)
        self.client.force_login(self.user_jefe)
        marcas = {'d1': 'No coincide con la foto', 'foto:carga': ''}
        r = self.client.post(reverse('proyectos:marcar_revision', args=[self.mia.pk]), {'marcas': json.dumps(marcas)})
        self.assertEqual(r.json(), {'ok': True, 'n': 2})
        # Sin comentario escrito, las marcas bastan para devolver.
        self.client.post(self.url, {'accion': 'devolver', 'detalle_id': self.mia.pk, 'observacion': '',
                                    'marcas': json.dumps(marcas)})
        e = ResultadoEnsayo.objects.get(detalle=self.mia)
        self.assertEqual(e.estado, ResultadoEnsayo.ESTADO_BORRADOR)
        self.assertEqual(e.marcas_revision, marcas)
        self.assertIn('2 datos marcados', e.observacion_revision)
        self.client.force_login(self.user_tec)
        r = self.client.get(self.url_registro(self.mia))
        self.assertContains(r, '2 datos marcados en rojo')
        self.assertEqual(r.context['marcas_revision'], marcas)
        # Al volver a terminar, las marcas se limpian.
        self.abrir_sesion()
        self.client.post(self.url_registro(self.mia), {
            'accion': 'terminar', 'fecha_ensayo': (date.today() - timedelta(days=1)).isoformat(),
            **TerminarTests.MEDIDAS_P1,
        })
        e.refresh_from_db()
        self.assertTrue(e.terminado)
        self.assertEqual(e.marcas_revision, {})

    def test_la_lista_de_terminados_lleva_al_revisor_a_la_revision(self):
        self.terminar(self.mia, self.user_tec)
        url_rev = reverse('proyectos:revisar_ensayo', args=[self.mia.pk])
        self.client.force_login(self.user_jefe)
        # El jefe no ve ensayos ajenos en «Mis resultados» salvo que vea todos; con permiso de aprobar y de ver todos sí.
        from trabajadores.models import TrabajadorProfile  # noqa: F401
        r = self.client.get(reverse('proyectos:revision_compresion', args=[self.mia.solicitud_id]))
        self.assertContains(r, url_rev)
        self.assertContains(r, 'data-revisar')

    def test_no_se_marca_un_ensayo_que_no_esta_terminado(self):
        self.client.force_login(self.user_jefe)
        r = self.client.post(reverse('proyectos:marcar_revision', args=[self.mia.pk]), {'marcas': '{"d1": ""}'})
        self.assertEqual(r.status_code, 409)

    @patch('proyectos.views_informe_editor.generar_informe_editor')
    def test_aprobar_lleva_al_editor_y_emitir_pide_el_pdf(self, tarea):
        self.terminar_todas()
        r = self.client.post(self.url, {'accion': 'aprobar'})
        # También la compresión pasa por el editor: aprobar no emite nada.
        url_editor = reverse('proyectos:editor_informe', args=[self.mia.solicitud_id])
        self.assertRedirects(r, url_editor, fetch_redirect_response=False)
        self.assertTrue(all(e.aprobado for e in ResultadoEnsayo.objects.all()))
        self.assertFalse(InformeFinal.objects.filter(solicitud=self.mia.solicitud).exists())
        self.client.get(url_editor)
        with self.captureOnCommitCallbacks(execute=True):
            self.client.post(reverse('proyectos:emitir_informe', args=[self.mia.solicitud_id]))
        informe = InformeFinal.objects.get(solicitud=self.mia.solicitud)
        self.assertEqual(informe.pdf_estado, InformeFinal.PDF_GENERANDO)
        self.assertEqual(informe.responsable_firma, self.jefe)
        tarea.delay.assert_called_once_with(informe.pk)

        # Aprobada: ni el técnico la modifica ni el supervisor la reabre.
        self.client.force_login(self.user_tec)
        self.assertEqual(self.subir(self.mia, 'carga', jpeg(1800, 700)).status_code, 409)
        self.client.force_login(self.user_sup)
        self.client.post(self.url_registro(self.mia), {'accion': 'reabrir'})
        self.assertTrue(ResultadoEnsayo.objects.get(detalle=self.mia).aprobado)

    def emitir(self):
        self.terminar_todas()
        self.client.post(self.url, {'accion': 'aprobar'})
        self.client.get(reverse('proyectos:editor_informe', args=[self.mia.solicitud_id]))
        with patch('proyectos.views_informe_editor.generar_informe_editor'):
            self.client.post(reverse('proyectos:emitir_informe', args=[self.mia.solicitud_id]))
        informe = InformeFinal.objects.get(solicitud=self.mia.solicitud)
        generar_informe_editor.apply(args=[informe.pk])
        informe.refresh_from_db()
        return informe

    def test_pdf_con_los_datos_de_cada_probeta_y_fin(self):
        informe = self.emitir()
        self.assertEqual(informe.pdf_estado, InformeFinal.PDF_LISTO, informe.pdf_error)
        with informe.archivo_pdf.open('rb') as f:
            lector = PdfReader(BytesIO(f.read()))
        texto = '\n'.join(p.extract_text() for p in lector.pages)
        self.assertIn(informe.codigo_informe, texto)
        self.assertIn(self.mia.muestra.codigo_laboratorio, texto)
        self.assertIn('8171,30', texto.replace(' ', ''))
        self.assertIn('621,0', texto)
        self.assertIn('VCF-EQ-PRC-001', texto)
        self.assertIn('Fin del Informe', lector.pages[-1].extract_text())
        # El PDF puede partir la frase en dos líneas («ISO/\nIEC»).
        self.assertIn('NTP ISO/IEC 17025', ' '.join(texto.replace('/\n', '/').split()))
        self.assertIn('19,42', texto)  # T final de la sesión

        r = self.client.get(reverse('proyectos:pdf_informe_compresion', args=[informe.pk]))
        self.assertEqual(r['Content-Type'], 'application/pdf')
        self.client.force_login(self.user_tec)
        self.assertEqual(self.client.get(reverse('proyectos:pdf_informe_compresion', args=[informe.pk])).status_code, 403)

    def preparar_correo(self, de='cliente@empresa.pe', personal=False):
        """Un usuario con correo, una cuenta y el pedido del cliente recibido en ella."""
        from correo.mensajeria import crear_mensaje
        from correo.models import AccesoCuenta, CuentaCorreo
        rol = rol_con_permisos('Correo informes', 'correo.ver', 'informes.ver', 'informes.aprobar')
        usuario, _ = crear_trabajador('correista', rol, 'Carla Correo')
        cuenta = CuentaCorreo.objects.create(direccion='ventas@vicaf.pe', nombre='Ventas VICAF', slug='ventas', personal=personal)
        AccesoCuenta.objects.create(usuario=usuario, cuenta=cuenta, rol=AccesoCuenta.GESTIONA)
        cot = self.mia.solicitud.cotizacion
        type(cot).objects.filter(pk=cot.pk).update(correo_contacto='cliente@empresa.pe', persona_contacto='Ana Pérez')
        pedido = crear_mensaje(
            cuenta, 'entrada', de=de, de_nombre='Ana Pérez', para=[{'nombre': '', 'correo': cuenta.direccion},
                                                                {'nombre': 'Obra', 'correo': 'obra@empresa.pe'}],
            asunto=f'Solicitud de ensayos {self.mia.solicitud.codigo_solicitud}', html='<p>Necesitamos ensayos</p>',
            leido=True,
        )
        return usuario, cuenta, pedido

    def test_enviar_al_cliente_lleva_a_la_pantalla_de_envio(self):
        informe = self.emitir()
        r = self.client.post(self.url, {'accion': 'enviar'})
        self.assertRedirects(r, reverse('proyectos:enviar_informe', args=[informe.pk]), fetch_redirect_response=False)
        r = self.client.get(reverse('proyectos:enviar_informe', args=[informe.pk]))
        self.assertContains(r, 'Por correo')
        self.assertContains(r, 'Por WhatsApp')
        self.assertContains(r, str(informe.slug_validacion))

    def test_correo_inteligente_responde_al_pedido_con_copia(self):
        from proyectos import envio_informe as envio
        informe = self.emitir()
        usuario, cuenta, pedido = self.preparar_correo()
        plan = envio.planear_correo(usuario, informe)
        self.assertEqual(plan.modo, 'respuesta')
        self.assertEqual(plan.origen.pk, pedido.pk)
        self.assertTrue(plan.cuenta_empresa)
        self.assertEqual([p['correo'] for p in plan.para], ['cliente@empresa.pe'])
        self.assertEqual([p['correo'] for p in plan.cc], ['obra@empresa.pe'])  # sin copiar a nuestra propia cuenta
        self.assertTrue(plan.asunto.startswith('RE: '))
        borrador = envio.crear_borrador_correo(usuario, informe, plan)
        self.assertEqual(borrador.hilo_id, pedido.hilo_id)
        self.assertEqual(borrador.in_reply_to, pedido.message_id)
        self.assertEqual(borrador.adjuntos.count(), 1)
        self.assertEqual(borrador.adjuntos.first().nombre, f'{informe.codigo_informe}.pdf')
        self.assertIn(str(informe.slug_validacion), borrador.cuerpo_html)
        informe.refresh_from_db()
        self.assertEqual(informe.mensaje_envio, borrador.pk)

    def test_si_otra_persona_reenvio_el_pedido_va_con_copia_a_quien_lo_envio(self):
        from proyectos import envio_informe as envio
        informe = self.emitir()
        usuario, cuenta, pedido = self.preparar_correo(de='intermediario@gestor.pe')
        plan = envio.planear_correo(usuario, informe)
        self.assertEqual([p['correo'] for p in plan.para], ['cliente@empresa.pe'])
        self.assertIn('intermediario@gestor.pe', [p['correo'] for p in plan.cc])

    def test_cuenta_personal_avisa_y_sin_pedido_redacta_uno_nuevo(self):
        from proyectos import envio_informe as envio
        informe = self.emitir()
        usuario, cuenta, pedido = self.preparar_correo(personal=True)
        plan = envio.planear_correo(usuario, informe)
        self.assertFalse(plan.cuenta_empresa)
        self.assertIn('personal', plan.aviso)
        pedido.delete()
        plan = envio.planear_correo(usuario, informe)
        self.assertEqual(plan.modo, 'nuevo')
        self.assertEqual([p['correo'] for p in plan.para], ['cliente@empresa.pe'])

    def test_al_salir_el_correo_el_informe_queda_enviado(self):
        from correo.tasks import enviar_mensaje
        from correo.models import Mensaje
        from proyectos import envio_informe as envio
        informe = self.emitir()
        usuario, cuenta, pedido = self.preparar_correo()
        borrador = envio.crear_borrador_correo(usuario, informe)
        Mensaje.objects.filter(pk=borrador.pk).update(estado_envio=Mensaje.EN_COLA)
        with override_settings(CORREO_ENVIO='simulado'):
            enviar_mensaje.apply(args=[borrador.pk])
        informe.refresh_from_db()
        self.assertEqual((informe.estado_envio, informe.canal_envio), ('enviado', 'correo'))

    def test_whatsapp_registra_el_envio(self):
        informe = self.emitir()
        r = self.client.post(reverse('proyectos:enviar_informe_whatsapp', args=[informe.pk]))
        self.assertEqual(r.json(), {'ok': True})
        informe.refresh_from_db()
        self.assertEqual((informe.estado_envio, informe.canal_envio), ('enviado', 'whatsapp'))

    def test_excel_con_numeros(self):
        self.terminar(self.mia, self.user_tec)
        self.client.force_login(self.user_jefe)
        r = self.client.get(reverse('proyectos:excel_compresion'), {'solicitud': self.mia.solicitud_id})
        self.assertEqual(r.status_code, 200)
        hoja = load_workbook(BytesIO(r.content)).active
        encabezados = [c.value for c in hoja[1]]
        fila = dict(zip(encabezados, [c.value for c in hoja[2]]))
        self.assertEqual(hoja.max_row, 2)
        self.assertEqual(fila['ID laboratorio'], self.mia.muestra.codigo_laboratorio)
        self.assertEqual(fila['D1 (mm)'], 102.12)
        self.assertEqual(fila['Resistencia (kg/cm²)'], 621.0)
        self.assertEqual(fila['Prensa'], 'VCF-EQ-PRC-001')

        self.client.force_login(self.user_tec)
        self.assertEqual(self.client.get(reverse('proyectos:excel_compresion')).status_code, 403)


def hoja(nombre='datos.xlsx', contenido=b'PK\x03\x04 hoja de prueba'):
    from django.core.files.uploadedfile import SimpleUploadedFile
    return SimpleUploadedFile(nombre, contenido)


@override_settings(MEDIA_ROOT=MEDIA_TMP)
class FlujoResultadosTests(CompresionBase):
    """Fase 1: resultados por línea, plantilla general, estado automático y
    separación de funciones."""

    terminar = InformeCompresionTests.terminar
    cerrar_sesion = InformeCompresionTests.cerrar_sesion

    def setUp(self):
        super().setUp()
        rol = rol_con_permisos('Jefe de laboratorio', 'informes.aprobar', 'informes.exportar', 'informes.ver')
        self.user_jefe, self.jefe = crear_trabajador('jefe', rol, 'Carla Jefa')
        self.solicitud = self.mia.solicitud
        self.url_revision = reverse('proyectos:revision_compresion', args=[self.solicitud.pk])

    def subir_fotos_generales(self, detalle):
        for tipo in FotoEnsayo.TIPOS_COMPRESION:
            ancho, alto = FotoEnsayo.PROPORCIONES[tipo]
            self.assertEqual(self.subir(detalle, tipo, jpeg(ancho * 100, alto * 100)).status_code, 200)

    def terminar_general(self, detalle, user, **extra):
        self.client.force_login(user)
        self.subir_fotos_generales(detalle)
        datos = {
            'accion': 'terminar', 'fecha_ensayo': (date.today() - timedelta(days=1)).isoformat(),
            'resumen': 'Máxima densidad seca 1,95 g/cm³; humedad óptima 12,4 %.',
        }
        datos.update(extra)
        return self.client.post(self.url_registro(detalle), datos)

    def test_plantilla_general_pide_resumen_y_las_seis_fotos(self):
        self.client.force_login(self.user_tec)
        r = self.client.post(self.url_registro(self.proctor), {
            'accion': 'terminar', 'fecha_ensayo': (date.today() - timedelta(days=1)).isoformat(),
        }, follow=True)
        self.assertContains(r, 'la foto «Antes del ensayo»')
        self.assertNotContains(r, 'hoja de resultados')
        e = ResultadoEnsayo.objects.get(detalle=self.proctor)
        self.assertEqual(e.plantilla, ResultadoEnsayo.PLANTILLA_GENERAL)
        self.assertFalse(e.terminado)

    def test_plantilla_general_termina_sin_sesion(self):
        self.terminar_general(self.proctor, self.user_tec)
        e = ResultadoEnsayo.objects.get(detalle=self.proctor)
        self.assertTrue(e.terminado)
        self.assertEqual(e.tecnico, self.tecnico)
        self.assertIsNone(e.sesion)
        self.proctor.refresh_from_db()
        self.assertEqual(self.proctor.fecha_entrega_real, date.today())

    def test_hoja_rechaza_otros_formatos(self):
        self.client.force_login(self.user_tec)
        r = self.client.post(self.url_registro(self.proctor), {
            'accion': 'guardar', 'hoja_calculo': hoja('virus.exe'),
        }, follow=True)
        self.assertContains(r, 'Excel, ODS, CSV, PDF o una foto')
        self.assertFalse(ResultadoEnsayo.objects.get(detalle=self.proctor).hoja_calculo)

    def test_la_pantalla_ya_no_pide_hojas_y_trae_el_panel_de_fotos(self):
        self.client.force_login(self.user_tec)
        r = self.client.get(self.url_registro(self.proctor))
        self.assertNotContains(r, 'name="hoja_foto"')
        self.assertNotContains(r, 'name="hoja_calculo"')
        self.assertContains(r, 'data-fotos-ensayo')
        self.assertContains(r, 'data-abrir-formulario')
        self.assertContains(r, 'data-modal-formulario')
        self.assertContains(r, 'Llenar formulario')

    def test_hoja_solo_para_quien_ve_la_linea(self):
        self.terminar_general(self.proctor, self.user_tec, hoja_calculo=hoja())
        url = reverse('proyectos:hoja_resultado', args=[self.proctor.pk])
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)
        self.assertIn('attachment', r['Content-Disposition'])
        self.client.force_login(self.user_jefe)
        self.assertEqual(self.client.get(url).status_code, 200)
        self.client.force_login(self.user_otro)
        self.assertEqual(self.client.get(url).status_code, 404)
        self.client.force_login(self.user_com)
        self.assertEqual(self.client.get(url).status_code, 404)

    def test_estado_de_la_solicitud_sale_de_los_resultados(self):
        self.assertEqual(self.solicitud.estado, 'pendiente')
        self.terminar_general(self.proctor, self.user_tec)
        self.solicitud.refresh_from_db()
        self.assertEqual(self.solicitud.estado, 'proceso')
        self.assertEqual(self.solicitud.avance_resultados(), (1, 3))

        self.terminar(self.mia, self.user_tec)
        self.terminar(self.ajena, self.user_otro)
        self.solicitud.refresh_from_db()
        self.assertEqual(self.solicitud.estado, 'finalizado')
        self.assertEqual(self.solicitud.fecha_entrega_real, date.today())

        # Devolver una línea la regresa a «en proceso».
        self.client.force_login(self.user_jefe)
        self.client.post(self.url_revision, {'accion': 'devolver', 'detalle_id': self.proctor.pk,
                                             'observacion': 'Falta la curva en la hoja.'})
        self.solicitud.refresh_from_db()
        self.assertEqual(self.solicitud.estado, 'proceso')
        self.assertIsNone(self.solicitud.fecha_entrega_real)

    def test_no_se_finaliza_a_mano_sin_todos_los_resultados(self):
        rol = rol_con_permisos('Coordinador', 'ensayos.ver', 'ensayos.ver_todos', 'ensayos.editar')
        user, _ = crear_trabajador('coordinador', rol)
        self.client.force_login(user)
        r = self.client.post(
            reverse('proyectos:cambiar_estado', args=[self.solicitud.pk, 'finalizado']), follow=True,
        )
        self.assertContains(r, '0 de 3')
        self.solicitud.refresh_from_db()
        self.assertEqual(self.solicitud.estado, 'pendiente')

    def test_quien_ejecuto_no_revisa_ni_aprueba(self):
        rol = rol_con_permisos('Técnico jefe', 'ensayos.ver', 'ensayos.registrar', 'informes.aprobar')
        user, perfil = crear_trabajador('tecjefe', rol, 'Rosa Doble')
        DetalleSolicitudEnsayo.objects.filter(pk=self.proctor.pk).update(tecnico_asignado=perfil)
        self.terminar_general(self.proctor, user)
        r = self.client.post(self.url_revision, {'accion': 'devolver', 'detalle_id': self.proctor.pk,
                                                 'observacion': 'Me lo devuelvo.'}, follow=True)
        self.assertContains(r, 'No puedes revisar un ensayo que ejecutaste tú')
        self.assertTrue(ResultadoEnsayo.objects.get(detalle=self.proctor).terminado)

        self.terminar(self.mia, self.user_tec)
        self.terminar(self.ajena, self.user_otro)
        self.cerrar_sesion(self.user_tec)
        self.cerrar_sesion(self.user_otro)
        self.client.force_login(user)
        r = self.client.post(self.url_revision, {'accion': 'aprobar'}, follow=True)
        self.assertContains(r, 'No puedes aprobar ensayos que ejecutaste tú')
        self.assertFalse(ResultadoEnsayo.objects.filter(estado=ResultadoEnsayo.ESTADO_APROBADO).exists())

    def test_solicitud_mixta_aprueba_y_pasa_a_subir_el_informe(self):
        self.terminar_general(self.proctor, self.user_tec)
        self.terminar(self.mia, self.user_tec)
        self.terminar(self.ajena, self.user_otro)
        self.cerrar_sesion(self.user_tec)
        self.cerrar_sesion(self.user_otro)
        self.client.force_login(self.user_jefe)
        r = self.client.get(self.url_revision)
        self.assertContains(r, 'Máxima densidad seca')
        self.assertContains(r, 'Al aprobar pasas al editor del informe')
        r = self.client.post(self.url_revision, {'accion': 'aprobar'})
        self.assertRedirects(
            r, reverse('proyectos:editor_informe', args=[self.solicitud.pk]), fetch_redirect_response=False,
        )
        self.assertEqual(ResultadoEnsayo.objects.filter(estado=ResultadoEnsayo.ESTADO_APROBADO).count(), 3)
        self.assertFalse(InformeFinal.objects.filter(solicitud=self.solicitud).exists())

