"""Fase 2: informe tipo Word dentro del sistema (borrador, autoguardado,
bloques de datos protegidos, emisión y PDF)."""
import json
import shutil
import tempfile
from datetime import date, timedelta
from unittest.mock import patch

from django.test import SimpleTestCase, override_settings
from django.urls import reverse
from django.utils import timezone
from pypdf import PdfReader
from io import BytesIO

from proyectos.informe_editor import (
    BLOQUE_FIRMAS, DocumentoInvalido, bloques_faltantes, bloques_usados, render_documento, validar_contenido,
)
from proyectos.models import BorradorInforme, InformeFinal, ResultadoEnsayo, VersionInforme
from proyectos.tasks import generar_informe_editor
from proyectos.test_compresion import CompresionBase
from trabajadores.testing import crear_trabajador, rol_con_permisos

MEDIA_TMP = tempfile.mkdtemp(prefix='media_editor_')


class ValidacionDocumentoTests(SimpleTestCase):

    def test_solo_pasan_nodos_y_marcas_conocidos(self):
        doc = {'type': 'doc', 'content': [
            {'type': 'paragraph', 'attrs': {'textAlign': 'center', 'onclick': 'x'}, 'content': [
                {'type': 'text', 'text': '<script>alert(1)</script>', 'marks': [{'type': 'bold'}, {'type': 'link', 'attrs': {'href': 'javascript:x'}}]},
            ]},
            {'type': 'iframe', 'attrs': {'src': 'https://malo'}},
            {'type': 'bloqueDatos', 'attrs': {'tipo': 'resultados', 'ref': '1 OR 1=1'}},
            {'type': 'bloqueDatos', 'attrs': {'tipo': 'firmas', 'ref': 'algo'}},
            {'type': 'heading', 'attrs': {'level': 9}, 'content': [{'type': 'text', 'text': 'Título'}]},
        ]}
        limpio = validar_contenido(doc)
        tipos = [n['type'] for n in limpio['content']]
        self.assertEqual(tipos, ['paragraph', 'bloqueDatos', 'heading'])
        self.assertEqual(limpio['content'][0]['attrs'], {'textAlign': 'center'})
        self.assertEqual(limpio['content'][0]['content'][0]['marks'], [{'type': 'bold'}])
        self.assertEqual(limpio['content'][1]['attrs'], {'tipo': BLOQUE_FIRMAS, 'ref': ''})
        self.assertEqual(limpio['content'][2]['attrs']['level'], 3)
        html = render_documento(limpio, {'lineas': {}, 'firma': None, 'modo': 'web'})
        self.assertIn('&lt;script&gt;', html)
        self.assertNotIn('<script>', html)
        self.assertIn('<p style="text-align:center"><strong>', html)

    def test_rechaza_lo_que_no_es_un_documento(self):
        with self.assertRaises(DocumentoInvalido):
            validar_contenido({'type': 'paragraph'})
        with self.assertRaises(DocumentoInvalido):
            validar_contenido([1, 2])

    def test_rechaza_documentos_enormes(self):
        doc = {'type': 'doc', 'content': [{'type': 'paragraph'}] * 20001}
        with self.assertRaises(DocumentoInvalido):
            validar_contenido(doc)


@override_settings(MEDIA_ROOT=MEDIA_TMP)
class EditorInformeTests(CompresionBase):

    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        shutil.rmtree(MEDIA_TMP, ignore_errors=True)

    def setUp(self):
        super().setUp()
        rol = rol_con_permisos('Jefe de laboratorio', 'informes.aprobar', 'informes.ver')
        self.user_jefe, self.jefe = crear_trabajador('jefe', rol, 'Carla Jefa')
        self.solicitud = self.mia.solicitud
        self.url_editor = reverse('proyectos:editor_informe', args=[self.solicitud.pk])
        self.url_guardar = reverse('proyectos:guardar_informe', args=[self.solicitud.pk])
        self.url_emitir = reverse('proyectos:emitir_informe', args=[self.solicitud.pk])

    def aprobar_todo(self, tecnico=None):
        ayer = date.today() - timedelta(days=1)
        for d, t in ((self.mia, self.tecnico), (self.ajena, self.otro), (self.proctor, self.tecnico)):
            ResultadoEnsayo.objects.create(
                detalle=d, plantilla=ResultadoEnsayo.plantilla_para(d), fecha_ensayo=ayer,
                resumen='Densidad máxima 1,95 g/cm³' if d == self.proctor else '',
                estado=ResultadoEnsayo.ESTADO_APROBADO, tecnico=tecnico or t,
                terminado_en=timezone.now(), aprobado_por=self.jefe, aprobado_en=timezone.now(),
            )

    def guardar(self, contenido, version):
        return self.client.post(self.url_guardar, json.dumps({'version': version, 'contenido': contenido}),
                                content_type='application/json')

    def test_sin_resultados_aprobados_no_abre(self):
        self.client.force_login(self.user_jefe)
        r = self.client.get(self.url_editor, follow=True)
        self.assertContains(r, 'cuando todos los resultados están aprobados')
        self.assertFalse(BorradorInforme.objects.exists())

    def test_solo_con_informes_aprobar(self):
        self.aprobar_todo()
        self.client.force_login(self.user_tec)
        self.assertEqual(self.client.get(self.url_editor).status_code, 403)
        self.assertEqual(self.guardar({'type': 'doc'}, 1).status_code, 403)

    def test_borrador_sale_del_modelo_con_un_bloque_por_linea(self):
        self.aprobar_todo()
        self.client.force_login(self.user_jefe)
        r = self.client.get(self.url_editor)
        self.assertEqual(r.status_code, 200)
        borrador = BorradorInforme.objects.get(solicitud=self.solicitud)
        usados = bloques_usados(borrador.contenido)
        for d in (self.mia, self.ajena, self.proctor):
            self.assertIn(f'resultados:{d.pk}', usados)
            self.assertIn(f'fotos:{d.pk}', usados)
        self.assertIn('caratula', usados)
        self.assertIn('firmas', usados)
        self.assertEqual(bloques_faltantes(borrador.contenido, self.solicitud), [])
        self.assertEqual(borrador.versiones.count(), 1)
        # El bloque del Proctor muestra su resumen; el editor no expone datos de otra solicitud.
        self.assertIn('Densidad máxima 1,95', r.context['bloques_html'][f'resultados:{self.proctor.pk}'])

    def test_autoguardado_con_control_de_version(self):
        self.aprobar_todo()
        self.client.force_login(self.user_jefe)
        self.client.get(self.url_editor)
        borrador = BorradorInforme.objects.get(solicitud=self.solicitud)
        nuevo = dict(borrador.contenido)
        nuevo['content'] = nuevo['content'] + [{'type': 'paragraph', 'content': [{'type': 'text', 'text': 'Conforme.'}]}]
        r = self.guardar(nuevo, borrador.version)
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()['version'], borrador.version + 1)
        # Una pestaña vieja (versión anterior) no pisa lo guardado.
        r = self.guardar({'type': 'doc', 'content': []}, borrador.version)
        self.assertEqual(r.status_code, 409)
        self.assertTrue(r.json()['conflicto'])
        borrador.refresh_from_db()
        self.assertIn('Conforme.', json.dumps(borrador.contenido))
        self.assertEqual(self.client.post(self.url_guardar, 'no es json', content_type='application/json').status_code, 400)

    def test_quitar_un_bloque_obligatorio_impide_emitir(self):
        self.aprobar_todo()
        self.client.force_login(self.user_jefe)
        self.client.get(self.url_editor)
        borrador = BorradorInforme.objects.get(solicitud=self.solicitud)
        sin_firmas = {'type': 'doc', 'content': [
            n for n in borrador.contenido['content']
            if not (n['type'] == 'bloqueDatos' and n['attrs']['tipo'] == 'firmas')
        ]}
        r = self.guardar(sin_firmas, borrador.version)
        self.assertEqual(r.json()['faltan'], ['Firmas'])
        r = self.client.post(self.url_emitir, follow=True)
        self.assertContains(r, 'vuelve a insertar: Firmas')
        self.assertFalse(InformeFinal.objects.exists())

    def test_quien_ejecuto_no_firma(self):
        self.aprobar_todo(tecnico=self.jefe)
        self.client.force_login(self.user_jefe)
        self.client.get(self.url_editor)
        r = self.client.post(self.url_emitir, follow=True)
        self.assertContains(r, 'No puedes firmar un informe con ensayos que ejecutaste tú')
        self.assertFalse(InformeFinal.objects.exists())

    @patch('proyectos.views_informe_editor.generar_informe_editor')
    def test_emitir_congela_el_informe_y_pide_el_pdf(self, tarea):
        self.aprobar_todo()
        self.client.force_login(self.user_jefe)
        self.client.get(self.url_editor)
        borrador = BorradorInforme.objects.get(solicitud=self.solicitud)
        with self.captureOnCommitCallbacks(execute=True):
            r = self.client.post(self.url_emitir)
        self.assertRedirects(r, reverse('proyectos:revision_compresion', args=[self.solicitud.pk]),
                             fetch_redirect_response=False)
        informe = InformeFinal.objects.get(solicitud=self.solicitud)
        tarea.delay.assert_called_once_with(informe.pk)
        borrador.refresh_from_db()
        self.assertTrue(borrador.emitido)
        self.assertIn(informe.codigo_informe, borrador.html_emitido)
        self.assertIn('Carla Jefa', borrador.html_emitido)
        self.assertTrue(VersionInforme.objects.filter(borrador=borrador, nota__startswith='Emitido').exists())
        # Emitido: ya no se modifica.
        self.assertEqual(self.guardar({'type': 'doc', 'content': []}, borrador.version).status_code, 409)

        generar_informe_editor.apply(args=[informe.pk])
        informe.refresh_from_db()
        self.assertEqual(informe.pdf_estado, InformeFinal.PDF_LISTO)
        with informe.archivo_pdf.open('rb') as f:
            texto = ''.join(p.extract_text() for p in PdfReader(BytesIO(f.read())).pages)
        self.assertIn(informe.codigo_informe, texto)
        self.assertIn(self.mia.muestra.codigo_laboratorio, texto)

    def test_vista_previa_y_restaurar_version(self):
        self.aprobar_todo()
        self.client.force_login(self.user_jefe)
        self.client.get(self.url_editor)
        borrador = BorradorInforme.objects.get(solicitud=self.solicitud)
        original = borrador.contenido
        self.guardar({'type': 'doc', 'content': [{'type': 'paragraph', 'content': [{'type': 'text', 'text': '<b>hola</b>'}]}]},
                     borrador.version)
        r = self.client.get(reverse('proyectos:vista_previa_informe', args=[self.solicitud.pk]))
        self.assertContains(r, '&lt;b&gt;hola&lt;/b&gt;')
        primera = borrador.versiones.order_by('numero').first()
        self.client.post(reverse('proyectos:restaurar_version_informe', args=[self.solicitud.pk, primera.pk]))
        borrador.refresh_from_db()
        self.assertEqual(bloques_usados(borrador.contenido), bloques_usados(original))

    def test_revision_lleva_al_editor_tras_aprobar(self):
        self.aprobar_todo()
        self.client.force_login(self.user_jefe)
        r = self.client.get(reverse('proyectos:revision_compresion', args=[self.solicitud.pk]))
        self.assertContains(r, 'data-abrir-editor')

    def test_quien_revisa_ve_las_fotos_de_cualquier_linea(self):
        from proyectos.models import FotoEnsayo
        from proyectos.test_compresion import jpeg
        self.client.force_login(self.user_tec)
        self.subir(self.mia, 'carga', jpeg(1800, 700))
        foto = FotoEnsayo.objects.get(ensayo__detalle=self.mia, tipo='carga')
        url = reverse('proyectos:foto_compresion', args=[foto.pk])
        self.client.force_login(self.user_jefe)
        self.assertEqual(self.client.get(url).status_code, 200)
        self.client.force_login(self.user_otro)
        self.assertEqual(self.client.get(url).status_code, 404)
        self.client.force_login(self.user_com)
        self.assertEqual(self.client.get(url).status_code, 404)
