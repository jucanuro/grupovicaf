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
from io import BytesIO, StringIO

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
            self.assertIn(f'resultados:{d.pk}', usados)  # las fotos van dentro de la hoja de resultados
        self.assertIn('caratula', usados)
        self.assertIn('notas', usados)
        self.assertIn('firmas', usados)
        # Estructura del informe oficial: carátula, notas y firma en la primera hoja; luego una hoja por ensayo.
        self.assertEqual(usados[:3], ['caratula', 'notas', 'firmas'])
        html = r.context['bloques_html']
        self.assertIn('VCF-LAB-FOR-064', html['caratula'])
        self.assertIn('INFORMACIÓN DEL CLIENTE', html['caratula'])
        self.assertIn('VCF-LAB-FOR-039', html[f'resultados:{self.mia.pk}'])
        self.assertIn('EJECUCIÓN DEL MÉTODO', html[f'resultados:{self.mia.pk}'])
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
        # Diseño oficial: carátula FOR-064, hoja FOR-039 y QR de validación.
        self.assertIn('VCF-LAB-FOR-064', texto)
        self.assertIn('VCF-LAB-FOR-039', texto)
        self.assertIn('Verifica el documento online', borrador.html_emitido)
        self.assertIn('alt="QR de validación del informe"', borrador.html_emitido)

        # El comando pasa los informes ya emitidos al diseño actual y regenera su PDF.
        from django.core.management import call_command
        borrador.html_emitido = '<p>informe viejo</p>'
        borrador.save(update_fields=['html_emitido'])
        call_command('regenerar_informes_diseno', '--aplicar', stdout=StringIO())
        borrador.refresh_from_db()
        self.assertIn('VCF-LAB-FOR-064', borrador.html_emitido)

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

    def test_lista_por_emitir_lleva_al_editor(self):
        self.aprobar_todo()
        self.client.force_login(self.user_jefe)
        url = reverse('proyectos:revision_compresion_lista')
        r = self.client.get(url + '?vista=por_emitir')
        self.assertContains(r, self.url_editor)
        self.assertContains(r, 'Sin firmar')
        self.assertNotContains(r, 'data-vista="todas"')
        self.assertNotContains(self.client.get(url), self.url_editor)


@override_settings(MEDIA_ROOT=MEDIA_TMP)
class BloqueEditadoTests(CompresionBase):
    """«Convertir en texto editable»: solo con informes.editar_datos."""

    def setUp(self):
        super().setUp()
        rol = rol_con_permisos('Jefe de laboratorio', 'informes.aprobar', 'informes.ver')
        self.user_jefe, self.jefe = crear_trabajador('jefe', rol, 'Carla Jefa')
        rol_editor = rol_con_permisos('Jefe con edición', 'informes.aprobar', 'informes.ver', 'informes.editar_datos')
        self.user_editor, self.editor = crear_trabajador('editor', rol_editor, 'Eva Editora')
        self.solicitud = self.mia.solicitud
        self.url_editor = reverse('proyectos:editor_informe', args=[self.solicitud.pk])
        self.url_guardar = reverse('proyectos:guardar_informe', args=[self.solicitud.pk])
        ayer = date.today() - timedelta(days=1)
        for d, t in ((self.mia, self.tecnico), (self.ajena, self.otro), (self.proctor, self.tecnico)):
            ResultadoEnsayo.objects.create(
                detalle=d, plantilla=ResultadoEnsayo.plantilla_para(d), fecha_ensayo=ayer, resumen='ok',
                estado=ResultadoEnsayo.ESTADO_APROBADO, tecnico=t, terminado_en=timezone.now(),
            )

    def convertido(self, contenido, detalle, texto='Resistencia corregida 210'):
        nuevo = []
        for n in contenido['content']:
            if n['type'] == 'bloqueDatos' and n['attrs'] == {'tipo': 'resultados', 'ref': str(detalle.pk)}:
                n = {'type': 'bloqueEditado', 'attrs': dict(n['attrs']),
                     'content': [{'type': 'paragraph', 'content': [{'type': 'text', 'text': texto}]}]}
            nuevo.append(n)
        return {'type': 'doc', 'content': nuevo}

    def guardar(self, contenido, version):
        return self.client.post(self.url_guardar, json.dumps({'version': version, 'contenido': contenido}),
                                content_type='application/json')

    def test_validacion_solo_admite_bloques_convertibles_en_primer_nivel(self):
        hijo = [{'type': 'paragraph', 'content': [{'type': 'text', 'text': 'x'}]}]
        doc = {'type': 'doc', 'content': [
            {'type': 'bloqueEditado', 'attrs': {'tipo': 'fotos', 'ref': '1'}, 'content': hijo},
            {'type': 'bloqueEditado', 'attrs': {'tipo': 'firmas'}, 'content': hijo},
            {'type': 'bloqueEditado', 'attrs': {'tipo': 'caratula'}, 'content': []},
            {'type': 'bulletList', 'content': [{'type': 'listItem', 'content': [
                {'type': 'bloqueEditado', 'attrs': {'tipo': 'notas'}, 'content': hijo}]}]},
            {'type': 'bloqueEditado', 'attrs': {'tipo': 'resultados', 'ref': '7'}, 'content': hijo},
        ]}
        limpio = validar_contenido(doc)
        editados = [n for n in limpio['content'] if n['type'] == 'bloqueEditado']
        self.assertEqual([n['attrs'] for n in editados], [{'tipo': 'resultados', 'ref': '7'}])
        self.assertNotIn('bloqueEditado', json.dumps(limpio['content'][0]))

    def test_sin_permiso_no_convierte(self):
        self.client.force_login(self.user_jefe)
        r = self.client.get(self.url_editor)
        self.assertNotContains(r, 'data-editar-datos="1"')
        borrador = BorradorInforme.objects.get(solicitud=self.solicitud)
        r = self.guardar(self.convertido(borrador.contenido, self.mia), borrador.version)
        self.assertEqual(r.status_code, 403)
        borrador.refresh_from_db()
        self.assertNotIn('bloqueEditado', json.dumps(borrador.contenido))

    def test_con_permiso_convierte_queda_en_historial_y_sale_en_el_informe(self):
        self.client.force_login(self.user_editor)
        r = self.client.get(self.url_editor)
        self.assertContains(r, 'data-editar-datos="1"')
        borrador = BorradorInforme.objects.get(solicitud=self.solicitud)
        r = self.guardar(self.convertido(borrador.contenido, self.mia), borrador.version)
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()['faltan'], [])
        nota = borrador.versiones.first().nota
        self.assertIn('Convirtió en texto editable', nota)
        self.assertIn(self.mia.muestra.codigo_laboratorio, nota)
        html = self.client.get(reverse('proyectos:vista_previa_informe', args=[self.solicitud.pk])).content.decode()
        self.assertIn('<div class="bloque bloque-editado"><p>Resistencia corregida 210</p></div>', html)

    def test_sin_permiso_no_cambia_un_bloque_ya_convertido(self):
        self.client.force_login(self.user_editor)
        self.client.get(self.url_editor)
        borrador = BorradorInforme.objects.get(solicitud=self.solicitud)
        self.guardar(self.convertido(borrador.contenido, self.mia), borrador.version)
        borrador.refresh_from_db()
        self.client.force_login(self.user_jefe)
        # Texto libre fuera del bloque: sí puede.
        libre = dict(borrador.contenido)
        libre['content'] = libre['content'] + [{'type': 'paragraph', 'content': [{'type': 'text', 'text': 'Conforme.'}]}]
        self.assertEqual(self.guardar(libre, borrador.version).status_code, 200)
        borrador.refresh_from_db()
        # Dentro del bloque convertido: no.
        cambiado = json.loads(json.dumps(borrador.contenido).replace('Resistencia corregida 210', 'Otra cifra'))
        self.assertEqual(self.guardar(cambiado, borrador.version).status_code, 403)
        # Quitarlo entero sí (igual que un bloque de datos), y emitir lo exigirá de vuelta.
        sin_bloque = {'type': 'doc', 'content': [n for n in borrador.contenido['content'] if n['type'] != 'bloqueEditado']}
        r = self.guardar(sin_bloque, borrador.version)
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()['faltan'], [f'Resultados de {self.mia.muestra.codigo_laboratorio}'])


@override_settings(MEDIA_ROOT=MEDIA_TMP)
class PantallaCompletaTests(CompresionBase):

    def test_editor_trae_pantalla_completa_zoom_y_contador(self):
        rol = rol_con_permisos('Jefe de laboratorio', 'informes.aprobar', 'informes.ver')
        user_jefe, jefe = crear_trabajador('jefe', rol, 'Carla Jefa')
        ayer = date.today() - timedelta(days=1)
        for d, t in ((self.mia, self.tecnico), (self.ajena, self.otro), (self.proctor, self.tecnico)):
            ResultadoEnsayo.objects.create(
                detalle=d, plantilla=ResultadoEnsayo.plantilla_para(d), fecha_ensayo=ayer, resumen='ok',
                estado=ResultadoEnsayo.ESTADO_APROBADO, tecnico=t, terminado_en=timezone.now(),
            )
        self.client.force_login(user_jefe)
        r = self.client.get(reverse('proyectos:editor_informe', args=[self.mia.solicitud.pk]))
        for marca in ('data-pantalla', 'data-zoom', 'data-palabras', 'data-paginas', 'ed-cuerpo'):
            self.assertContains(r, marca)
