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

from proyectos.models import EnsayoCompresion, FotoEnsayo, InformeFinal
from proyectos.tasks import enviar_informe_cliente, generar_informe_compresion
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

    def terminar(self, detalle, user):
        self.client.force_login(user)
        self.abrir_sesion()
        for tipo, _ in FotoEnsayo.TIPOS:
            ancho, alto = FotoEnsayo.PROPORCIONES[tipo]
            self.subir(detalle, tipo, jpeg(ancho * 100, alto * 100))
        self.client.post(self.url_registro(detalle), {
            'accion': 'terminar', 'fecha_ensayo': (date.today() - timedelta(days=1)).isoformat(),
            **TerminarTests.MEDIDAS_P1,
        })
        self.assertTrue(EnsayoCompresion.objects.get(detalle=detalle).terminado)

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
        self.assertTrue(EnsayoCompresion.objects.get(detalle=self.mia).terminado)
        self.client.post(self.url, {'accion': 'devolver', 'detalle_id': self.mia.pk,
                                    'observacion': 'Repite la foto de la carga, está borrosa.'})
        e = EnsayoCompresion.objects.get(detalle=self.mia)
        self.assertEqual(e.estado, EnsayoCompresion.ESTADO_BORRADOR)
        self.client.force_login(self.user_tec)
        self.assertContains(self.client.get(self.url_registro(self.mia)), 'está borrosa')
        self.assertContains(self.client.get(reverse('proyectos:mis_ensayos_compresion')), 'Devuelta')

    @patch('proyectos.views_informe_compresion.generar_informe_compresion')
    def test_aprobar_bloquea_las_probetas_y_pide_el_pdf(self, tarea):
        self.terminar_todas()
        with self.captureOnCommitCallbacks(execute=True):
            self.client.post(self.url, {'accion': 'aprobar'})
        informe = InformeFinal.objects.get(solicitud=self.mia.solicitud)
        self.assertEqual(informe.pdf_estado, InformeFinal.PDF_GENERANDO)
        self.assertEqual(informe.responsable_firma, self.jefe)
        tarea.delay.assert_called_once_with(informe.pk)
        self.assertTrue(all(e.aprobado for e in EnsayoCompresion.objects.all()))

        # Aprobada: ni el técnico la modifica ni el supervisor la reabre.
        self.client.force_login(self.user_tec)
        self.assertEqual(self.subir(self.mia, 'carga', jpeg(1800, 700)).status_code, 409)
        self.client.force_login(self.user_sup)
        self.client.post(self.url_registro(self.mia), {'accion': 'reabrir'})
        self.assertTrue(EnsayoCompresion.objects.get(detalle=self.mia).aprobado)

    def emitir(self):
        self.terminar_todas()
        with patch('proyectos.views_informe_compresion.generar_informe_compresion'):
            self.client.post(self.url, {'accion': 'aprobar'})
        informe = InformeFinal.objects.get(solicitud=self.mia.solicitud)
        generar_informe_compresion.apply(args=[informe.pk])
        informe.refresh_from_db()
        return informe

    def test_pdf_con_caratula_una_pagina_por_probeta_y_fin(self):
        informe = self.emitir()
        self.assertEqual(informe.pdf_estado, InformeFinal.PDF_LISTO, informe.pdf_error)
        with informe.archivo_pdf.open('rb') as f:
            lector = PdfReader(BytesIO(f.read()))
        self.assertEqual(len(lector.pages), 3)
        texto = '\n'.join(p.extract_text() for p in lector.pages)
        self.assertIn(informe.codigo_informe, texto)
        self.assertIn(self.mia.muestra.codigo_laboratorio, texto)
        self.assertIn('8171,30', texto.replace(' ', ''))
        self.assertIn('621,0', texto)
        self.assertIn('VCF-EQ-PRC-001', texto)
        self.assertIn('Fin del Informe', lector.pages[-1].extract_text())
        self.assertIn('19,42', texto)  # T final de la sesión

        r = self.client.get(reverse('proyectos:pdf_informe_compresion', args=[informe.pk]))
        self.assertEqual(r['Content-Type'], 'application/pdf')
        self.client.force_login(self.user_tec)
        self.assertEqual(self.client.get(reverse('proyectos:pdf_informe_compresion', args=[informe.pk])).status_code, 403)

    def test_enviar_al_cliente(self):
        informe = self.emitir()
        with patch('proyectos.views_informe_compresion.enviar_informe_cliente') as tarea:
            self.client.post(self.url, {'accion': 'enviar'})
            tarea.delay.assert_called_once_with(informe.pk, 'a@b.pe')
        enviar_informe_cliente.apply(args=[informe.pk, 'a@b.pe'])
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, ['a@b.pe'])
        self.assertEqual(mail.outbox[0].attachments[0][2], 'application/pdf')
        self.assertIn(str(informe.slug_validacion), mail.outbox[0].body)
        informe.refresh_from_db()
        self.assertEqual(informe.estado_envio, 'enviado')

    def test_sin_correo_del_cliente_no_envia(self):
        informe = self.emitir()
        cot = self.mia.solicitud.cotizacion
        type(cot).objects.filter(pk=cot.pk).update(correo_contacto='')
        type(cot.cliente).objects.filter(pk=cot.cliente_id).update(correo_contacto='')
        with patch('proyectos.views_informe_compresion.enviar_informe_cliente') as tarea:
            self.client.post(self.url, {'accion': 'enviar'})
            tarea.delay.assert_not_called()
        informe.refresh_from_db()
        self.assertEqual(informe.estado_envio, 'pendiente')

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
