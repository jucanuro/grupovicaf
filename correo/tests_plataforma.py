"""Paso 2 del módulo de correo: plataforma tipo Outlook sobre los modelos reales.

Cubre lo que pide el prompt del Gerente: permisos (nadie ve ni descarga correo
de una cuenta que no tiene asignada), hilos, búsqueda, firmas y saneado del
HTML recibido. Las pruebas de la pantalla de entrada (Paso 1) están en tests.py.
"""
import re
import shutil
import tempfile
import time
from unittest import mock, skipUnless

from django.contrib.auth.models import User
from django.core.cache import cache
from django.core.files.storage import FileSystemStorage
from django.core.management import call_command
from django.db import connection
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils.functional import empty

from trabajadores.testing import crear_trabajador, rol_con_permisos

from .almacen import almacen_correo
from .enlaces import crear_enlace, token_adjunto
from .mensajeria import carpeta, crear_mensaje
from .middleware import URLCONF_CORREO
from .models import AccesoCuenta, Asignacion, Carpeta, CuentaCorreo, EventoMensaje, Firma, Hilo, Mensaje
from .sanitizar import bloquear_imagenes_remotas, sanitizar_html

HOST = 'email.localhost'
ES_POSTGRES = connection.vendor == 'postgresql'


def ruta(nombre, *args):
    return reverse(nombre, urlconf=URLCONF_CORREO, args=args)


@override_settings(ROOT_URLCONF='grupovicaf.urls_lab', SITE_ROLE='lab')
class BasePlataforma(TestCase):
    """Dos cuentas (informes y laboratorio) y cuatro personas con distinto acceso."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # Los archivos del correo van a una carpeta temporal, no a CORREO_ALMACEN_DIR.
        cls._dir = tempfile.mkdtemp(prefix='correo-pruebas-')
        cls._anterior = almacen_correo._wrapped
        almacen_correo._wrapped = FileSystemStorage(location=cls._dir)

    @classmethod
    def tearDownClass(cls):
        almacen_correo._wrapped = cls._anterior if cls._anterior is not None else empty
        shutil.rmtree(cls._dir, ignore_errors=True)
        super().tearDownClass()

    def setUp(self):
        cache.clear()
        rol = rol_con_permisos('Correo', 'correo.ver', 'cotizaciones.ver', 'clientes.ver')
        self.gestor, _ = crear_trabajador('gestor', rol, 'Gina Gestora')
        self.lector, _ = crear_trabajador('lector', rol, 'Luis Lector')
        self.ajeno, _ = crear_trabajador('ajeno', rol, 'Ana Ajena')
        self.jefe, _ = crear_trabajador('jefe', rol, 'Jorge Jefe')
        self.sin_modulo, _ = crear_trabajador('sin_modulo', rol_con_permisos('Técnico', 'ensayos.ver'))
        self.informes = CuentaCorreo.objects.create(
            direccion='informes@grupovicaf.com', nombre='Informes', slug='informes')
        self.lab = CuentaCorreo.objects.create(
            direccion='laboratorio@grupovicaf.com', nombre='Laboratorio', slug='laboratorio')
        for usuario, cuenta, nivel in (
            (self.gestor, self.informes, AccesoCuenta.GESTIONA),
            (self.lector, self.informes, AccesoCuenta.LECTURA),
            (self.jefe, self.informes, AccesoCuenta.ADMINISTRA),
            (self.ajeno, self.lab, AccesoCuenta.GESTIONA),
            (self.sin_modulo, self.informes, AccesoCuenta.GESTIONA),
        ):
            AccesoCuenta.objects.create(usuario=usuario, cuenta=cuenta, rol=nivel)

        self.m = crear_mensaje(
            self.informes, 'entrada', de='ana@cliente.example', de_nombre='Ana Cliente',
            para=[{'nombre': '', 'correo': 'informes@grupovicaf.com'}],
            asunto='Cotización de compresión de probetas',
            html='<p>Necesitamos ensayar 12 probetas de concreto.</p>',
            message_id='<orig-1@cliente.example>',
            adjuntos=[('planos.pdf', 'application/pdf', b'%PDF-1.4 planos', '', False)],
        )
        self.m_lab = crear_mensaje(
            self.lab, 'entrada', de='obra@otra.example', asunto='Resultados del Proctor',
            html='<p>¿Ya tienen el resultado del Proctor?</p>',
        )

    def entrar(self, usuario):
        self.client.force_login(usuario)

    def get(self, _vista, *args, **params):
        return self.client.get(ruta(_vista, *args), params, HTTP_HOST=HOST)

    def post(self, _vista, *args, **datos):
        return self.client.post(ruta(_vista, *args), datos, HTTP_HOST=HOST)


# ------------------------------------------------------------------ permisos

class PermisosTests(BasePlataforma):
    def test_sin_correo_ver_es_403_aunque_tenga_cuenta(self):
        self.entrar(self.sin_modulo)
        self.assertEqual(self.get('bandeja').status_code, 403)
        self.assertEqual(self.get('bandeja_cuenta', 'informes').status_code, 403)

    def test_cuenta_ajena_es_404(self):
        self.entrar(self.ajeno)
        self.assertEqual(self.get('bandeja_cuenta', 'informes').status_code, 404)
        self.assertEqual(self.get('carpeta', 'informes', carpeta(self.informes, 'enviados').pk).status_code, 404)

    def test_mensaje_ajeno_es_404_en_todas_sus_vistas(self):
        self.entrar(self.ajeno)
        for nombre in ('mensaje', 'mensaje_cuerpo', 'imprimir'):
            with self.subTest(vista=nombre):
                self.assertEqual(self.get(nombre, self.m.pk).status_code, 404)

    def test_hilo_ajeno_en_la_lista_es_404(self):
        self.entrar(self.ajeno)
        self.assertEqual(self.get('bandeja', h=self.m.hilo_id).status_code, 404)

    def test_bandeja_unificada_solo_muestra_cuentas_propias(self):
        self.entrar(self.ajeno)
        respuesta = self.get('bandeja')
        self.assertContains(respuesta, 'Resultados del Proctor')
        self.assertNotContains(respuesta, 'compresión de probetas')
        self.assertNotContains(respuesta, 'informes@grupovicaf.com')

    def test_acciones_sobre_mensajes_ajenos_no_hacen_nada(self):
        self.entrar(self.ajeno)
        self.post('acciones', accion='eliminar', mensajes=self.m.pk, volver='/')
        self.post('acciones', accion='eliminar', hilos=self.m.hilo_id, volver='/')
        self.m.refresh_from_db()
        self.assertEqual(self.m.carpeta.tipo, 'entrada')

    def test_lector_puede_leer_pero_no_modificar(self):
        self.entrar(self.lector)
        lectura = self.get('bandeja_cuenta', 'informes', h=self.m.hilo_id)
        self.assertContains(lectura, 'Cotización de compresión de probetas')
        self.assertNotContains(lectura, '?responder=')
        self.assertEqual(self.post('acciones', accion='archivar', mensajes=self.m.pk, volver='/').status_code, 403)
        self.assertEqual(self.get('redactar', responder=self.m.pk).status_code, 403)
        self.assertEqual(self.post('carpeta_nueva', 'informes', nombre='Mía').status_code, 403)
        self.assertEqual(self.post('asignar', self.m.hilo_id, usuario=self.lector.pk).status_code, 403)
        self.m.refresh_from_db()
        self.assertEqual(self.m.carpeta.tipo, 'entrada')

    def test_busqueda_no_muestra_cuentas_ajenas(self):
        self.entrar(self.ajeno)
        respuesta = self.get('buscar', q='probetas')
        self.assertNotContains(respuesta, 'compresión de probetas')
        respuesta = self.get('buscar', q='Proctor')
        self.assertContains(respuesta, 'Resultados del Proctor')

    def test_historial_de_contacto_no_muestra_cuentas_ajenas(self):
        self.entrar(self.ajeno)
        respuesta = self.get('contacto', correo='ana@cliente.example')
        self.assertEqual(respuesta.status_code, 200)
        self.assertNotContains(respuesta, 'compresión de probetas')

    def test_no_puede_mover_a_una_carpeta_de_otra_cuenta(self):
        self.entrar(self.gestor)
        destino = carpeta(self.lab, 'archivados')
        self.post('acciones', accion=f'mover:{destino.pk}', mensajes=self.m.pk, volver='/')
        self.m.refresh_from_db()
        self.assertEqual(self.m.cuenta, self.informes)
        self.assertEqual(self.m.carpeta.tipo, 'entrada')

    def test_borrador_de_otra_persona_no_se_abre(self):
        self.entrar(self.gestor)
        respuesta = self.get('redactar', cuenta='informes')
        borrador = Mensaje.objects.get(estado_envio=Mensaje.BORRADOR)
        self.assertRedirects(respuesta, ruta('borrador', borrador.pk), fetch_redirect_response=False)
        AccesoCuenta.objects.filter(usuario=self.lector).update(rol=AccesoCuenta.GESTIONA)
        self.entrar(self.lector)
        self.assertEqual(self.get('borrador', borrador.pk).status_code, 403)
        self.entrar(self.ajeno)
        self.assertEqual(self.get('borrador', borrador.pk).status_code, 404)


class AdjuntosFirmadosTests(BasePlataforma):
    def enlace_desde_la_lectura(self):
        self.entrar(self.gestor)
        html = self.get('bandeja_cuenta', 'informes', h=self.m.hilo_id).content.decode()
        encontrado = re.search(r'href="(/a/[^"]+/)"', html)
        self.assertIsNotNone(encontrado, 'La lectura no muestra el enlace del adjunto')
        return encontrado.group(1)

    def test_el_enlace_firmado_descarga_el_adjunto(self):
        url = self.enlace_desde_la_lectura()
        self.client.logout()  # el enlace es la credencial, como una URL prefirmada
        respuesta = self.client.get(url, HTTP_HOST=HOST)
        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(b''.join(respuesta.streaming_content), b'%PDF-1.4 planos')
        self.assertIn('attachment', respuesta['Content-Disposition'])
        self.assertEqual(respuesta['X-Content-Type-Options'], 'nosniff')

    def test_enlace_alterado_es_404(self):
        url = self.enlace_desde_la_lectura()
        alterado = url[:-3] + ('A' if url[-3] != 'A' else 'B') + url[-2:]
        self.assertEqual(self.client.get(alterado, HTTP_HOST=HOST).status_code, 404)

    def test_enlace_vencido_es_404(self):
        url = self.enlace_desde_la_lectura()
        futuro = time.time() + 301
        with mock.patch('django.core.signing.time.time', return_value=futuro):
            self.assertEqual(self.client.get(url, HTTP_HOST=HOST).status_code, 404)

    def test_otro_token_firmado_no_sirve_para_descargar(self):
        token_de_sesion = crear_enlace(self.gestor, '/')
        self.assertEqual(self.get('adjunto', token_de_sesion).status_code, 404)

    def test_quien_no_tiene_la_cuenta_nunca_recibe_el_enlace(self):
        self.entrar(self.ajeno)
        self.assertEqual(self.get('bandeja', h=self.m.hilo_id).status_code, 404)
        self.assertEqual(self.get('mensaje', self.m.pk).status_code, 404)
        # Y el token solo se emite con el pk del adjunto propio.
        adjunto = self.m.adjuntos.get()
        self.assertNotEqual(token_adjunto(adjunto), '')


# --------------------------------------------------------------------- hilos

class HilosTests(BasePlataforma):
    def test_respuesta_por_in_reply_to_entra_al_mismo_hilo(self):
        r = crear_mensaje(self.informes, 'entrada', de='ana@cliente.example', asunto='Otro asunto cualquiera',
                          in_reply_to='<orig-1@cliente.example>', html='<p>Sigo</p>')
        self.assertEqual(r.hilo_id, self.m.hilo_id)

    def test_respuesta_por_references_entra_al_mismo_hilo(self):
        r = crear_mensaje(self.informes, 'entrada', de='ana@cliente.example', asunto='x',
                          references='<algo@otro> <orig-1@cliente.example>', html='<p>Sigo</p>')
        self.assertEqual(r.hilo_id, self.m.hilo_id)

    def test_re_sin_cabeceras_usa_el_asunto_reciente(self):
        r = crear_mensaje(self.informes, 'entrada', de='ana@cliente.example',
                          asunto='RE: Cotización de compresión de probetas', html='<p>Ok</p>')
        self.assertEqual(r.hilo_id, self.m.hilo_id)

    def test_asunto_nuevo_es_otro_hilo_y_otra_cuenta_tambien(self):
        nuevo = crear_mensaje(self.informes, 'entrada', de='ana@cliente.example', asunto='Consulta distinta')
        self.assertNotEqual(nuevo.hilo_id, self.m.hilo_id)
        otra = crear_mensaje(self.lab, 'entrada', de='ana@cliente.example', in_reply_to='<orig-1@cliente.example>')
        self.assertNotEqual(otra.hilo_id, self.m.hilo_id)

    def test_la_lista_agrupa_por_conversacion(self):
        crear_mensaje(self.informes, 'entrada', de='ana@cliente.example', asunto='RE: x',
                      in_reply_to='<orig-1@cliente.example>', html='<p>Segundo</p>')
        self.entrar(self.gestor)
        respuesta = self.get('bandeja_cuenta', 'informes')
        self.assertContains(respuesta, '<span class="fila__n">(2)</span>', html=True)
        self.assertEqual(respuesta.content.decode().count('data-fila '), 1)

    def test_abrir_marca_leido_y_registra_en_la_bitacora_una_vez(self):
        self.entrar(self.gestor)
        self.get('bandeja_cuenta', 'informes', h=self.m.hilo_id)
        self.get('bandeja_cuenta', 'informes', h=self.m.hilo_id)
        self.m.refresh_from_db()
        self.assertTrue(self.m.leido)
        self.assertEqual(EventoMensaje.objects.filter(hilo=self.m.hilo, tipo=EventoMensaje.ABRIO).count(), 1)

    def test_responder_crea_borrador_en_el_hilo_y_al_enviar_cita_el_original(self):
        self.entrar(self.gestor)
        respuesta = self.get('redactar', responder=self.m.pk)
        borrador = Mensaje.objects.get(estado_envio=Mensaje.BORRADOR)
        self.assertRedirects(respuesta, ruta('borrador', borrador.pk), fetch_redirect_response=False)
        self.assertEqual(borrador.hilo_id, self.m.hilo_id)
        self.assertEqual(borrador.asunto, 'RE: Cotización de compresión de probetas')
        self.assertEqual(borrador.para, [{'nombre': 'Ana Cliente', 'correo': 'ana@cliente.example'}])
        self.assertEqual(borrador.in_reply_to, '<orig-1@cliente.example>')

        with self.captureOnCommitCallbacks(execute=True):
            self.post('borrador_enviar', borrador.pk, para='Ana Cliente <ana@cliente.example>',
                      asunto=borrador.asunto, cuerpo_html='<p>Con gusto, adjuntamos la oferta.</p>')
        borrador.refresh_from_db()
        self.assertEqual(borrador.estado_envio, Mensaje.ENVIADO)
        self.assertEqual(borrador.carpeta.tipo, 'enviados')
        self.assertIn('Con gusto', borrador.cuerpo_html)
        self.assertIn('<blockquote', borrador.cuerpo_html)
        self.assertIn('12 probetas', borrador.cuerpo_html)
        self.assertTrue(EventoMensaje.objects.filter(hilo=self.m.hilo, tipo=EventoMensaje.RESPONDIO,
                                                     usuario=self.gestor).exists())

    def test_responder_a_todos_suma_cc_sin_la_cuenta_propia(self):
        con_cc = crear_mensaje(
            self.informes, 'entrada', de='ana@cliente.example', asunto='Con copia',
            para=[{'nombre': '', 'correo': 'informes@grupovicaf.com'}, {'nombre': '', 'correo': 'b@cliente.example'}],
            cc=[{'nombre': '', 'correo': 'c@cliente.example'}],
        )
        self.entrar(self.gestor)
        self.get('redactar', responder_todos=con_cc.pk)
        borrador = Mensaje.objects.get(estado_envio=Mensaje.BORRADOR)
        self.assertEqual([p['correo'] for p in borrador.para], ['ana@cliente.example', 'b@cliente.example'])
        self.assertEqual([p['correo'] for p in borrador.cc], ['c@cliente.example'])

    def test_reenviar_conserva_los_adjuntos(self):
        self.entrar(self.gestor)
        self.get('redactar', reenviar=self.m.pk)
        borrador = Mensaje.objects.get(estado_envio=Mensaje.BORRADOR)
        self.assertEqual(borrador.asunto, 'RV: Cotización de compresión de probetas')
        self.assertEqual(list(borrador.adjuntos.values_list('nombre', flat=True)), ['planos.pdf'])
        self.assertTrue(borrador.tiene_adjuntos)

    def test_envio_fallido_queda_en_salida_y_se_puede_reintentar(self):
        self.entrar(self.gestor)
        self.get('redactar', cuenta='informes')
        borrador = Mensaje.objects.get(estado_envio=Mensaje.BORRADOR)
        with self.captureOnCommitCallbacks(execute=True):
            self.post('borrador_enviar', borrador.pk, para='residente@falla.invalid', asunto='Prueba',
                      cuerpo_html='<p>Hola</p>')
        borrador.refresh_from_db()
        self.assertEqual(borrador.estado_envio, Mensaje.FALLIDO)
        self.assertEqual(borrador.carpeta.tipo, 'salida')
        self.assertIn('Rebote', borrador.ultimo_error)
        with self.captureOnCommitCallbacks(execute=True):
            self.post('reintentar', borrador.pk)
        borrador.refresh_from_db()
        self.assertEqual(borrador.intentos, 2)

    def test_enviar_sin_destinatario_no_sale(self):
        self.entrar(self.gestor)
        self.get('redactar', cuenta='informes')
        borrador = Mensaje.objects.get(estado_envio=Mensaje.BORRADOR)
        self.post('borrador_enviar', borrador.pk, para='', asunto='x', cuerpo_html='<p>x</p>')
        borrador.refresh_from_db()
        self.assertEqual(borrador.estado_envio, Mensaje.BORRADOR)

    def test_autoguardado_responde_json(self):
        self.entrar(self.gestor)
        self.get('redactar', cuenta='informes')
        borrador = Mensaje.objects.get(estado_envio=Mensaje.BORRADOR)
        respuesta = self.client.post(
            ruta('borrador_guardar', borrador.pk), {'asunto': 'Guardado solo', 'cuerpo_html': '<p>a</p>'},
            HTTP_HOST=HOST, HTTP_X_REQUESTED_WITH='fetch',
        )
        self.assertTrue(respuesta.json()['ok'])
        borrador.refresh_from_db()
        self.assertEqual(borrador.asunto, 'Guardado solo')

    def test_adjunto_que_supera_el_limite_se_rechaza(self):
        self.entrar(self.gestor)
        self.get('redactar', cuenta='informes')
        borrador = Mensaje.objects.get(estado_envio=Mensaje.BORRADOR)
        from django.core.files.uploadedfile import SimpleUploadedFile
        with override_settings(CORREO_MAX_ADJUNTOS_BYTES=10), \
                mock.patch('correo.views_redactar.MAX_BYTES', 10):
            respuesta = self.client.post(
                ruta('borrador_adjuntos', borrador.pk),
                {'archivo': SimpleUploadedFile('grande.txt', b'x' * 50, 'text/plain')}, HTTP_HOST=HOST,
            )
        self.assertEqual(respuesta.status_code, 400)
        self.assertFalse(borrador.adjuntos.exists())


class CarpetasYAsignacionTests(BasePlataforma):
    def test_carpeta_propia_se_crea_y_al_borrarla_sus_correos_vuelven(self):
        self.entrar(self.gestor)
        self.post('carpeta_nueva', 'informes', nombre='Proveedores')
        propia = Carpeta.objects.get(cuenta=self.informes, nombre='Proveedores')
        self.post('acciones', accion=f'mover:{propia.pk}', mensajes=self.m.pk, volver='/')
        self.m.refresh_from_db()
        self.assertEqual(self.m.carpeta, propia)
        self.post('carpeta_eliminar', 'informes', propia.pk)
        self.m.refresh_from_db()
        self.assertEqual(self.m.carpeta.tipo, 'entrada')

    def test_nombre_repetido_no_crea_otra(self):
        self.entrar(self.gestor)
        self.post('carpeta_nueva', 'informes', nombre='Proveedores')
        self.post('carpeta_nueva', 'informes', nombre='Proveedores')
        self.assertEqual(Carpeta.objects.filter(cuenta=self.informes, nombre='Proveedores').count(), 1)

    def test_eliminar_en_papelera_es_definitivo(self):
        self.entrar(self.gestor)
        self.post('acciones', accion='eliminar', mensajes=self.m.pk, volver='/')
        self.m.refresh_from_db()
        self.assertEqual(self.m.carpeta.tipo, 'papelera')
        self.post('acciones', accion='eliminar', mensajes=self.m.pk, volver='/')
        self.assertFalse(Mensaje.objects.filter(pk=self.m.pk).exists())

    def test_asignar_solo_a_quien_gestiona_la_cuenta(self):
        self.entrar(self.gestor)
        self.post('asignar', self.m.hilo_id, usuario=self.lector.pk, volver='/')
        self.assertFalse(Asignacion.objects.exists())
        self.post('asignar', self.m.hilo_id, usuario=self.jefe.pk, volver='/')
        asignacion = Asignacion.objects.get(hilo=self.m.hilo)
        self.assertEqual(asignacion.asignado_a, self.jefe)
        self.post('atendido', self.m.hilo_id, volver='/')
        asignacion.refresh_from_db()
        self.assertEqual(asignacion.estado, Asignacion.ATENDIDO)
        respuesta = self.get('bandeja_cuenta', 'informes')
        self.assertContains(respuesta, 'Atendido: Jorge Jefe')


# ------------------------------------------------------------------ búsqueda

class BusquedaTests(BasePlataforma):
    def test_filtros_de_cuenta_adjunto_y_remitente(self):
        crear_mensaje(self.informes, 'entrada', de='pedro@proveedor.example', asunto='Factura de cemento')
        self.entrar(self.gestor)
        con_adjunto = self.get('buscar', adjunto='1').content.decode()
        self.assertIn('Cotización de compresión', con_adjunto)
        self.assertNotIn('Factura de cemento', con_adjunto)
        de_pedro = self.get('buscar', de='pedro').content.decode()
        self.assertIn('Factura de cemento', de_pedro)
        self.assertNotIn('Cotización de compresión', de_pedro)

    def test_papelera_queda_fuera_salvo_que_se_pida(self):
        self.entrar(self.gestor)
        self.post('acciones', accion='eliminar', mensajes=self.m.pk, volver='/')
        self.assertNotContains(self.get('buscar', q='probetas'), 'Cotización de compresión')
        self.assertContains(self.get('buscar', q='probetas', carpeta='papelera'), 'Cotización de compresión')

    def test_sin_filtros_no_lista_nada(self):
        self.entrar(self.gestor)
        self.assertNotContains(self.get('buscar'), 'Cotización de compresión')

    @skipUnless(ES_POSTGRES, 'La búsqueda de texto completo usa PostgreSQL')
    def test_ignora_tildes_y_encuentra_variantes(self):
        self.entrar(self.gestor)
        self.assertContains(self.get('buscar', q='compresion'), 'Cotización de compresión')
        self.assertContains(self.get('buscar', q='COTIZACION probeta'), 'Cotización de compresión')
        self.assertNotContains(self.get('buscar', q='granulometría'), 'Cotización de compresión')

    @skipUnless(ES_POSTGRES, 'La búsqueda de texto completo usa PostgreSQL')
    def test_busca_en_el_cuerpo_y_en_el_remitente(self):
        self.entrar(self.gestor)
        self.assertContains(self.get('buscar', q='concreto'), 'Cotización de compresión')
        self.assertContains(self.get('buscar', q='ana@cliente.example'), 'Cotización de compresión')


# -------------------------------------------------------------------- firmas

class FirmasTests(BasePlataforma):
    def test_firma_personal_y_una_sola_predeterminada(self):
        self.entrar(self.gestor)
        self.post('firma_nueva', nombre='Completa', html='<p>Gina · VICAF</p>', ambito='personal', para_nuevos='1')
        self.post('firma_nueva', nombre='Breve', html='<p>G.</p>', ambito='personal', para_nuevos='1',
                  para_respuestas='1')
        self.assertEqual(list(Firma.objects.filter(usuario=self.gestor, para_nuevos=True).values_list('nombre', flat=True)),
                         ['Breve'])

    def test_el_correo_nuevo_lleva_la_firma_personal(self):
        Firma.objects.create(usuario=self.gestor, nombre='Completa', html='<p>Firma de Gina</p>', para_nuevos=True)
        self.entrar(self.gestor)
        self.get('redactar', cuenta='informes')
        self.assertIn('Firma de Gina', Mensaje.objects.get(estado_envio=Mensaje.BORRADOR).cuerpo_html)

    def test_la_firma_de_la_cuenta_prevalece(self):
        Firma.objects.create(usuario=self.gestor, nombre='Mía', html='<p>Firma de Gina</p>', para_respuestas=True)
        compartida = Firma.objects.create(cuenta=self.informes, nombre='Ventas', html='<p>Área de Informes</p>')
        CuentaCorreo.objects.filter(pk=self.informes.pk).update(firma_predeterminada=compartida)
        self.entrar(self.gestor)
        self.get('redactar', responder=self.m.pk)
        cuerpo = Mensaje.objects.get(estado_envio=Mensaje.BORRADOR).cuerpo_html
        self.assertIn('Área de Informes', cuerpo)
        self.assertNotIn('Firma de Gina', cuerpo)

    def test_solo_quien_administra_define_la_firma_de_la_cuenta(self):
        self.entrar(self.gestor)
        self.post('firma_nueva', nombre='Ventas', html='<p>x</p>', ambito=str(self.informes.pk))
        self.assertFalse(Firma.objects.filter(cuenta=self.informes).exists())
        self.entrar(self.jefe)
        self.post('firma_nueva', nombre='Ventas', html='<p>x</p>', ambito=str(self.informes.pk),
                  predeterminada_cuenta='1')
        firma = Firma.objects.get(cuenta=self.informes)
        self.informes.refresh_from_db()
        self.assertEqual(self.informes.firma_predeterminada, firma)

    def test_la_firma_se_sanitiza(self):
        self.entrar(self.gestor)
        self.post('firma_nueva', nombre='Mala', ambito='personal',
                  html='<p onclick="robar()">Hola<script>alert(1)</script></p><a href="javascript:x()">y</a>')
        html = Firma.objects.get(nombre='Mala').html
        self.assertNotIn('<script', html)
        self.assertNotIn('onclick', html)
        self.assertNotIn('javascript:', html)

    def test_firma_de_otra_persona_no_se_ve_ni_se_edita(self):
        ajena = Firma.objects.create(usuario=self.ajeno, nombre='Suya', html='<p>x</p>')
        self.entrar(self.gestor)
        self.assertEqual(self.get('firma_editar', ajena.pk).status_code, 404)
        self.assertEqual(self.get('firma_vista', ajena.pk).status_code, 404)
        self.assertEqual(self.post('firma_eliminar', ajena.pk).status_code, 404)
        self.assertNotContains(self.get('firmas'), 'Suya')

    def test_gestor_ve_la_firma_de_cuenta_pero_no_la_edita(self):
        compartida = Firma.objects.create(cuenta=self.informes, nombre='Ventas', html='<p>x</p>')
        self.entrar(self.gestor)
        self.assertContains(self.get('firmas'), 'Ventas')
        self.assertEqual(self.get('firma_editar', compartida.pk).status_code, 404)


# ------------------------------------------------------------------- saneado

class SaneadoTests(BasePlataforma):
    MALICIOSO = (
        '<p onclick="robar()" style="color:#B45309">Hola</p><script>alert(1)</script>'
        '<a href="javascript:alert(1)">clic</a><iframe src="https://x.example"></iframe>'
        '<img src="https://rastreo.example/pixel.gif" alt="pixel"><form action="https://x"><input></form>'
    )

    def test_sanitizar_quita_scripts_eventos_y_esquemas_peligrosos(self):
        limpio = sanitizar_html(self.MALICIOSO)
        for prohibido in ('<script', 'onclick', 'javascript:', '<iframe', '<form', '<input'):
            self.assertNotIn(prohibido, limpio)
        self.assertIn('color:#B45309', limpio.replace(' ', ''))
        self.assertIn('rel="noopener noreferrer"', limpio)

    def test_imagenes_remotas_bloqueadas_por_defecto(self):
        html, n = bloquear_imagenes_remotas(sanitizar_html(self.MALICIOSO))
        self.assertEqual(n, 1)
        self.assertNotIn('src="https://rastreo.example', html)
        self.assertIn('data-src-bloqueada', html)

    def test_imagen_data_solo_si_es_imagen(self):
        self.assertIn('data:image/png', sanitizar_html('<img src="data:image/png;base64,AAAA">'))
        self.assertNotIn('data:text/html', sanitizar_html('<img src="data:text/html;base64,AAAA">'))
        self.assertNotIn('data:', sanitizar_html('<a href="data:text/html,hola">x</a>'))

    def test_el_cuerpo_se_sirve_aislado(self):
        malo = crear_mensaje(self.informes, 'entrada', de='x@spam.example', asunto='Oferta', html=self.MALICIOSO)
        self.entrar(self.gestor)
        respuesta = self.get('mensaje_cuerpo', malo.pk)
        self.assertEqual(respuesta.status_code, 200)
        csp = respuesta['Content-Security-Policy']
        self.assertIn("default-src 'none'", csp)
        self.assertIn('sandbox', csp)
        self.assertNotIn('script-src', csp)
        self.assertNotIn('https:', csp.split('img-src')[1].split(';')[0])
        self.assertNotIn(b'<script>alert', respuesta.content)
        self.assertNotIn(b'src="https://rastreo.example', respuesta.content)
        con_imagenes = self.get('mensaje_cuerpo', malo.pk, imagenes='1')
        self.assertIn('https:', con_imagenes['Content-Security-Policy'].split('img-src')[1].split(';')[0])
        self.assertIn(b'https://rastreo.example/pixel.gif', con_imagenes.content)

    def test_la_lectura_ofrece_mostrar_imagenes(self):
        malo = crear_mensaje(self.informes, 'entrada', de='x@spam.example', asunto='Boletín', html=self.MALICIOSO)
        self.entrar(self.gestor)
        self.assertContains(self.get('bandeja_cuenta', 'informes', h=malo.hilo_id), 'Mostrar imágenes')


# ------------------------------------------------------------- datos de ejemplo

class SemillaTests(BasePlataforma):
    @override_settings(DEBUG=True)
    def test_seed_correo_demo_es_idempotente(self):
        call_command('seed_correo_demo', usuario=['gestor'], verbosity=0)
        primero = (Mensaje.objects.count(), Hilo.objects.count())
        call_command('seed_correo_demo', usuario=['gestor'], verbosity=0)
        self.assertEqual((Mensaje.objects.count(), Hilo.objects.count()), primero)
        self.entrar(self.gestor)
        self.assertEqual(self.get('bandeja').status_code, 200)

    def test_seed_correo_demo_no_corre_en_produccion(self):
        from django.core.management.base import CommandError
        with self.assertRaises(CommandError):
            call_command('seed_correo_demo', usuario=['gestor'], verbosity=0)

    def test_superusuario_sin_cuentas_ve_la_bandeja_vacia(self):
        admin = User.objects.create_superuser('admin', password='x')
        self.entrar(admin)
        respuesta = self.get('bandeja')
        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, 'Aún no tienes cuentas de correo asignadas')
