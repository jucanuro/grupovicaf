"""Firma con plantilla: datos → HTML de correo seguro, logo propio y vista previa."""
import io
import shutil
import tempfile

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import SimpleTestCase, override_settings
from PIL import Image

from . import firma_plantilla as fp
from .models import Firma
from .sanitizar import bloquear_imagenes_remotas, tiene_imagenes_remotas
from .tests_plataforma import BasePlataforma

DATOS = dict(nombre='Gina Gestora', cargo='Jefa de Laboratorio', telefono='+51 976 000 000',
             correo='gina@grupovicaf.com', direccion='Jr. Lima 123', ciudad='Cajamarca',
             web='https://www.grupovicaf.com', facebook='', instagram='https://instagram.com/vicaf', tiktok='')


class GenerarHtmlTests(SimpleTestCase):
    def test_lleva_los_datos_y_solo_las_redes_llenas(self):
        html = fp.generar_html(fp.limpiar_datos(DATOS))
        for texto in ('Gina Gestora', 'JEFA DE LABORATORIO', 'mailto:gina@grupovicaf.com', 'tel:+51976000000',
                      'Jr. Lima 123, Cajamarca', 'https://instagram.com/vicaf', 'LogoF'):
            self.assertIn(texto, html)
        self.assertNotIn('Facebook', html)
        self.assertNotIn('TikTok', html)

    def test_escapa_el_texto_y_descarta_enlaces_no_https(self):
        datos = fp.limpiar_datos({**DATOS, 'nombre': '<script>alert(1)</script>', 'web': 'javascript:alert(1)',
                                  'facebook': 'http://facebook.com/x'})
        self.assertEqual(datos['web'], '')
        self.assertEqual(datos['facebook'], '')
        html = fp.generar_html(datos)
        self.assertNotIn('<script>', html)
        self.assertIn('&lt;script&gt;', html)

    def test_sin_cargo_ni_redes_sigue_siendo_una_firma_valida(self):
        html = fp.generar_html(fp.limpiar_datos({'nombre': 'Solo Nombre'}))
        self.assertIn('Solo Nombre', html)
        self.assertNotIn('<a href="https', html)


class FirmaPlantillaVistaTests(BasePlataforma):
    def test_guardar_con_plantilla_arma_el_html_y_guarda_los_datos(self):
        self.entrar(self.gestor)
        self.post('firma_nueva', modo='plantilla', nombre_firma='Completa', ambito='personal',
                  para_nuevos='1', **DATOS)
        firma = Firma.objects.get(usuario=self.gestor)
        self.assertEqual(firma.nombre, 'Completa')
        self.assertEqual(firma.plantilla['cargo'], 'Jefa de Laboratorio')
        self.assertIn('Gina Gestora', firma.html)
        self.assertIn('<table', firma.html)
        self.assertTrue(firma.para_nuevos)

    def test_editar_muestra_los_datos_guardados(self):
        firma = Firma.objects.create(usuario=self.gestor, nombre='Completa', html='<p>x</p>',
                                     plantilla=fp.limpiar_datos(DATOS))
        self.entrar(self.gestor)
        r = self.get('firma_editar', firma.pk)
        self.assertContains(r, 'value="Jefa de Laboratorio"')

    def test_enlace_de_red_sin_https_se_rechaza(self):
        self.entrar(self.gestor)
        self.post('firma_nueva', modo='plantilla', nombre_firma='Mala', ambito='personal',
                  **{**DATOS, 'facebook': 'http://facebook.com/x'})
        self.assertFalse(Firma.objects.filter(usuario=self.gestor).exists())

    def test_el_editor_libre_sigue_funcionando(self):
        self.entrar(self.gestor)
        self.post('firma_nueva', nombre='Libre', html='<p>G.</p>', ambito='personal')
        firma = Firma.objects.get(usuario=self.gestor)
        self.assertIsNone(firma.plantilla)


def _png(ancho=800, alto=300, modo='RGBA'):
    salida = io.BytesIO()
    Image.new(modo, (ancho, alto), (18, 48, 107, 255) if modo == 'RGBA' else (18, 48, 107)).save(salida, 'PNG')
    return salida.getvalue()


class OpcionesDeDisenoTests(SimpleTestCase):
    def test_tamano_posicion_y_colores_se_aplican(self):
        datos = fp.limpiar_datos({**DATOS, 'logo_ancho': '200', 'logo_pos': 'arriba',
                                  'color_principal': '#aa0000', 'color_acento': '#00aa00', 'color_panel': '#eeeeee'})
        html = fp.generar_html(datos, logo_url='https://x.example/mi-logo.png')
        self.assertIn('width="200"', html)
        self.assertIn('https://x.example/mi-logo.png', html)
        self.assertIn('#AA0000', html)
        self.assertIn('#00AA00', html)
        self.assertIn('colspan="2" align="left"', html)  # logo arriba: ocupa toda la fila

    def test_valores_fuera_de_rango_o_peligrosos_vuelven_al_valor_inicial(self):
        datos = fp.limpiar_datos({**DATOS, 'logo_ancho': '9999', 'logo_pos': 'x',
                                  'color_principal': 'red;background:url(x)', 'color_panel': 'javascript:1'})
        self.assertEqual(datos['logo_ancho'], fp.LOGO_ANCHO_MAX)
        self.assertEqual(datos['logo_pos'], 'izquierda')
        self.assertEqual(datos['color_principal'], fp.AZUL)
        self.assertEqual(datos['color_panel'], fp.FONDO)
        self.assertEqual(fp.limpiar_datos({**DATOS, 'logo_ancho': 'abc'})['logo_ancho'], fp.LOGO_ANCHO_INICIAL)


class ProcesarLogoTests(SimpleTestCase):
    def _subir(self, contenido, nombre='logo.png'):
        return SimpleUploadedFile(nombre, contenido)

    def test_reduce_a_600_px_y_conserva_la_transparencia(self):
        extension, datos = fp.procesar_logo(self._subir(_png(1500, 600)))
        img = Image.open(io.BytesIO(datos))
        self.assertEqual(extension, 'png')
        self.assertEqual(max(img.size), 600)

    def test_rechaza_lo_que_no_es_imagen_o_pesa_de_mas(self):
        with self.assertRaises(ValueError):
            fp.procesar_logo(self._subir(b'<script>alert(1)</script>', 'logo.png'))
        with self.assertRaises(ValueError):
            fp.procesar_logo(self._subir(b'GIF89a' + b'0' * 20, 'logo.gif'))
        with self.assertRaises(ValueError):
            fp.procesar_logo(self._subir(b'0' * (fp.LOGO_MAX_BYTES + 1)))


class ImagenesPropiasTests(SimpleTestCase):
    @override_settings(SITE_URL='https://www.grupovicaf.com')
    def test_las_imagenes_de_vicaf_no_se_bloquean_pero_las_de_afuera_si(self):
        propia = '<img src="https://www.grupovicaf.com/static/img/firma/web.png">'
        ajena = '<img src="https://rastreador.example/p.gif">'
        self.assertFalse(tiene_imagenes_remotas(propia))
        self.assertTrue(tiene_imagenes_remotas(propia + ajena))
        html, cuantas = bloquear_imagenes_remotas(propia + ajena)
        self.assertEqual(cuantas, 1)
        self.assertIn('src="https://www.grupovicaf.com/static/img/firma/web.png"', html)
        self.assertIn('data-src-bloqueada="https://rastreador.example/p.gif"', html)


class LogoYVistaPreviaTests(BasePlataforma):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._media = tempfile.mkdtemp(prefix='firmas-media-')
        cls._override = override_settings(MEDIA_ROOT=cls._media)
        cls._override.enable()

    @classmethod
    def tearDownClass(cls):
        cls._override.disable()
        shutil.rmtree(cls._media, ignore_errors=True)
        super().tearDownClass()

    def _guardar(self, **extra):
        return self.post('firma_nueva', modo='plantilla', nombre_firma='Con logo', ambito='personal',
                         **{**DATOS, **extra})

    def test_el_logo_subido_se_guarda_y_la_firma_lo_usa(self):
        self.entrar(self.gestor)
        self._guardar(logo=SimpleUploadedFile('mi.png', _png()), logo_ancho='180', logo_pos='arriba')
        firma = Firma.objects.get(usuario=self.gestor)
        self.assertTrue(firma.logo.name.startswith('correo/firmas/'))
        self.assertIn(firma.logo.url, firma.html)
        self.assertNotIn('LogoF', firma.html)
        self.assertEqual(firma.plantilla['logo_ancho'], 180)
        self.assertEqual(firma.plantilla['logo_pos'], 'arriba')

    def test_un_archivo_que_no_es_imagen_no_guarda_la_firma(self):
        self.entrar(self.gestor)
        self._guardar(logo=SimpleUploadedFile('malo.png', b'esto no es un png'))
        self.assertFalse(Firma.objects.filter(usuario=self.gestor).exists())

    def test_quitar_el_logo_vuelve_al_de_vicaf(self):
        self.entrar(self.gestor)
        self._guardar(logo=SimpleUploadedFile('mi.png', _png()))
        firma = Firma.objects.get(usuario=self.gestor)
        self.post('firma_editar', firma.pk, modo='plantilla', nombre_firma='Con logo', ambito='personal',
                  quitar_logo='1', **DATOS)
        firma.refresh_from_db()
        self.assertFalse(firma.logo)
        self.assertIn('LogoF', firma.html)

    def test_la_vista_previa_no_guarda_y_muestra_el_logo_sin_guardar(self):
        self.entrar(self.gestor)
        r = self.post('firma_previa', modo='plantilla', firma_pk='', **{**DATOS, 'logo': SimpleUploadedFile('mi.png', _png())})
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, 'data:image/png;base64,')
        self.assertContains(r, 'Gina Gestora')
        self.assertIn('img-src', r['Content-Security-Policy'])
        self.assertFalse(Firma.objects.exists())

    def test_la_vista_previa_exige_sesion_de_correo(self):
        self.entrar(self.sin_modulo)
        sin_permiso = self.post('firma_previa', **DATOS)
        self.assertNotEqual(sin_permiso.status_code, 200)


class BloqueDeFirmaTests(SimpleTestCase):
    def test_envolver_y_separar_son_inversas(self):
        from .firma_bloque import envolver, separar
        firma = '<table><tr><td><div>x</div></td></tr></table>'
        self.assertEqual(separar('<p>Hola</p>' + envolver(firma)), ('<p>Hola</p>', firma))
        self.assertEqual(separar('<p>Sin firma</p>'), ('<p>Sin firma</p>', ''))
        self.assertEqual(envolver(''), '')

    def test_el_sanitizador_conserva_la_marca_del_bloque(self):
        from .firma_bloque import envolver, separar
        from .sanitizar import sanitizar_html
        limpio = sanitizar_html('<p>Hola</p>' + envolver('<table><tr><td>Gina</td></tr></table>'))
        self.assertEqual(separar(limpio)[1], '<table><tbody><tr><td>Gina</td></tr></tbody></table>')


class BloqueEnElBorradorTests(BasePlataforma):
    def setUp(self):
        super().setUp()
        self.rica = Firma.objects.create(
            usuario=self.gestor, nombre='Plantilla', plantilla=fp.limpiar_datos(DATOS), para_nuevos=True,
            html=fp.generar_html(fp.limpiar_datos(DATOS)))
        self.libre = Firma.objects.create(usuario=self.gestor, nombre='Libre', html='<p>Saludos, Gina</p>')

    def _borrador(self):
        from .models import Mensaje
        self.entrar(self.gestor)
        self.get('redactar', cuenta='informes')
        return Mensaje.objects.get(estado_envio=Mensaje.BORRADOR)

    def test_el_borrador_nuevo_lleva_la_firma_como_bloque_y_no_en_el_editor(self):
        from .firma_bloque import separar
        b = self._borrador()
        editable, firma = separar(b.cuerpo_html)
        self.assertIn('Gina Gestora', firma)
        self.assertNotIn('<table', editable)
        r = self.get('borrador', b.pk)
        self.assertEqual(r.context['tiene_firma_bloque'], True)
        self.assertNotIn('Gina Gestora', r.context['cuerpo_editor'])

    def test_la_pagina_no_ofrece_el_html_de_la_firma_con_plantilla_para_pegarlo_en_el_editor(self):
        b = self._borrador()
        r = self.get('borrador', b.pk)
        self.assertContains(r, f'data-firma-html="{self.libre.pk}"')
        self.assertNotContains(r, f'data-firma-html="{self.rica.pk}"')

    def test_guardar_el_texto_conserva_la_firma(self):
        from .firma_bloque import separar
        b = self._borrador()
        self.post('borrador_guardar', b.pk, cuerpo_html='<p>Hola, adjunto la cotización.</p>')
        b.refresh_from_db()
        editable, firma = separar(b.cuerpo_html)
        self.assertIn('Hola, adjunto la cotización.', editable)
        self.assertIn('Gina Gestora', firma)

    def test_quitar_y_poner_la_firma(self):
        from .firma_bloque import separar
        b = self._borrador()
        self.assertEqual(self.post('borrador_firma', b.pk, quitar='1').json(), {'ok': True, 'hay': False})
        b.refresh_from_db()
        self.assertEqual(separar(b.cuerpo_html)[1], '')
        self.assertEqual(self.post('borrador_firma', b.pk, firma_id=self.rica.pk).json(), {'ok': True, 'hay': True})
        b.refresh_from_db()
        self.assertIn('Gina Gestora', separar(b.cuerpo_html)[1])

    def test_una_firma_libre_o_ajena_no_se_puede_poner_como_bloque(self):
        b = self._borrador()
        self.assertEqual(self.post('borrador_firma', b.pk, firma_id=self.libre.pk).status_code, 404)
        ajena = Firma.objects.create(usuario=self.ajeno, nombre='Ajena', html='<p>x</p>', plantilla={'nombre': 'x'})
        self.assertEqual(self.post('borrador_firma', b.pk, firma_id=ajena.pk).status_code, 404)

    def test_el_marco_de_la_firma_se_ve_con_imagenes_y_solo_para_quien_redacta(self):
        b = self._borrador()
        r = self.get('borrador_firma_vista', b.pk)
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, 'Gina Gestora')
        self.assertIn('img-src', r['Content-Security-Policy'])
        self.entrar(self.ajeno)
        self.assertEqual(self.get('borrador_firma_vista', b.pk).status_code, 404)
