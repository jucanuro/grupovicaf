"""Correo real en local: recepción de .eml, envío MIME por SMTP y puente de Mailpit."""
import json
import smtplib
import tempfile
from email import policy
from email.message import EmailMessage
from email.parser import BytesParser
from io import StringIO
from pathlib import Path
from unittest import mock

from django.core.cache import cache
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import override_settings

from .envio import ServicioEnvioSMTP, construir_mime
from .mailpit import traer
from .mensajeria import agregar_adjunto, crear_mensaje
from .models import CuentaCorreo, Mensaje
from .recepcion import CorreoRechazado, RecepcionEML
from .servicios import ServicioEnvioSimulado, servicio_envio
from .tasks import MAX_INTENTOS, enviar_mensaje
from .tests_plataforma import BasePlataforma

PNG = b'\x89PNG\r\n\x1a\n' + b'0' * 20


def eml(*, de='Ana Cliente <ana@cliente.example>', para='informes@grupovicaf.com', cc='', asunto='Consulta',
        texto='Hola', html=None, message_id='<m1@cliente.example>', in_reply_to='', adjuntos=(), imagen_cid='',
        cabeceras=None):
    m = EmailMessage()
    m['From'] = de
    m['To'] = para
    if cc:
        m['Cc'] = cc
    m['Subject'] = asunto
    m['Date'] = 'Thu, 12 Nov 2026 10:00:00 -0500'
    if message_id:
        m['Message-ID'] = message_id
    if in_reply_to:
        m['In-Reply-To'] = in_reply_to
        m['References'] = in_reply_to
    for clave, valor in (cabeceras or {}).items():
        m[clave] = valor
    m.set_content(texto)
    if html is not None:
        m.add_alternative(html, subtype='html')
        if imagen_cid:
            m.get_payload()[-1].add_related(PNG, 'image', 'png', cid=f'<{imagen_cid}>', filename='logo.png',
                                            disposition='inline')
    for nombre, contenido in adjuntos:
        m.add_attachment(contenido, 'application', 'pdf', filename=nombre)
    return m.as_bytes()


class RecepcionTests(BasePlataforma):
    def recibir(self, crudo, destinatarios=()):
        return RecepcionEML().recibir(crudo, destinatarios)

    def test_correo_simple_entra_a_la_bandeja_de_la_cuenta(self):
        [m] = self.recibir(eml(asunto='Consulta de granulometría', texto='¿Cuánto cuesta?'))
        self.assertEqual((m.cuenta, m.carpeta.tipo), (self.informes, 'entrada'))
        self.assertEqual((m.de, m.de_nombre), ('ana@cliente.example', 'Ana Cliente'))
        self.assertEqual(m.asunto, 'Consulta de granulometría')
        self.assertIn('¿Cuánto cuesta?', m.cuerpo_texto)
        self.assertEqual(m.message_id, '<m1@cliente.example>')
        self.assertFalse(m.leido)
        self.assertTrue(m.eml.name)
        self.assertEqual(len(m.eml_sha256), 64)

    def test_html_se_sanitiza_y_conserva_adjuntos_e_imagenes(self):
        [m] = self.recibir(eml(
            html='<p onclick="x()">Hola</p><script>alert(1)</script><img src="cid:logo@cli">',
            imagen_cid='logo@cli', adjuntos=[('plano.pdf', b'%PDF-1.4 plano')],
        ))
        self.assertNotIn('<script', m.cuerpo_html)
        self.assertNotIn('onclick', m.cuerpo_html)
        self.assertIn('cid:logo@cli', m.cuerpo_html)
        adjuntos = {a.nombre: a for a in m.adjuntos.all()}
        self.assertTrue(adjuntos['logo.png'].incrustado)
        self.assertEqual(adjuntos['logo.png'].content_id, 'logo@cli')
        self.assertFalse(adjuntos['plano.pdf'].incrustado)
        with adjuntos['plano.pdf'].archivo.open('rb') as f:
            self.assertEqual(f.read(), b'%PDF-1.4 plano')
        self.assertTrue(m.tiene_adjuntos)

    def test_el_mismo_correo_no_entra_dos_veces(self):
        crudo = eml()
        self.assertEqual(len(self.recibir(crudo)), 1)
        self.assertEqual(self.recibir(crudo), [])
        self.assertEqual(self.recibir(eml(texto='otro cuerpo, mismo Message-ID')), [])
        self.assertEqual(Mensaje.objects.filter(message_id='<m1@cliente.example>').count(), 1)

    def test_una_copia_por_cada_cuenta_vicaf(self):
        creados = self.recibir(eml(cc='Lab <laboratorio@grupovicaf.com>, otra@externa.example'))
        self.assertEqual({m.cuenta for m in creados}, {self.informes, self.lab})

    def test_copia_oculta_por_el_sobre(self):
        creados = self.recibir(eml(para='otra@externa.example'), destinatarios=['laboratorio@grupovicaf.com'])
        self.assertEqual([m.cuenta for m in creados], [self.lab])

    def test_sin_cuenta_vicaf_se_rechaza(self):
        with self.assertRaises(CorreoRechazado):
            self.recibir(eml(para='alguien@externa.example'))

    def test_cuenta_inactiva_no_recibe(self):
        CuentaCorreo.objects.filter(pk=self.informes.pk).update(activa=False)
        with self.assertRaises(CorreoRechazado):
            self.recibir(eml())

    @override_settings(CORREO_MAX_ENTRANTE_BYTES=100)
    def test_correo_demasiado_grande_se_rechaza(self):
        with self.assertRaises(CorreoRechazado):
            self.recibir(eml())

    def test_marcado_como_spam_va_a_no_deseado(self):
        [m] = self.recibir(eml(cabeceras={'X-Spam-Flag': 'YES'}))
        self.assertEqual(m.carpeta.tipo, 'spam')

    def test_la_respuesta_del_cliente_vuelve_al_mismo_hilo(self):
        [m] = self.recibir(eml(in_reply_to='<orig-1@cliente.example>', message_id='<m2@cliente.example>'))
        self.assertEqual(m.hilo_id, self.m.hilo_id)

    def test_correo_mal_formado_no_rompe(self):
        crudo = b'From: raro\r\nTo: informes@grupovicaf.com\r\nSubject: =?bad?=\r\n\r\ncuerpo sin estructura'
        [m] = self.recibir(crudo)
        self.assertIn('cuerpo sin estructura', m.cuerpo_texto)


class MimeTests(BasePlataforma):
    def mensaje_saliente(self):
        m = crear_mensaje(
            self.informes, 'salida', de='informes@grupovicaf.com', de_nombre='Informes VICAF',
            para=[{'nombre': 'Ana Cliente', 'correo': 'ana@cliente.example'}],
            cc=[{'nombre': '', 'correo': 'laboratorio@grupovicaf.com'}],
            cco=[{'nombre': '', 'correo': 'gerencia@grupovicaf.example'}],
            asunto='RE: Cotización de compresión de probetas', html='<p>Adjunto <b>oferta</b></p><img src="cid:firma@vicaf">',
            in_reply_to='<orig-1@cliente.example>', references='<orig-1@cliente.example>',
            estado=Mensaje.EN_COLA, hilo=self.m.hilo,
        )
        agregar_adjunto(m, 'firma.png', 'image/png', PNG, content_id='firma@vicaf', incrustado=True)
        agregar_adjunto(m, 'oferta.pdf', 'application/pdf', b'%PDF-1.4 oferta')
        return m

    def test_cabeceras_de_hilo_y_sin_cco_visible(self):
        mime = construir_mime(self.mensaje_saliente())
        self.assertEqual(mime['In-Reply-To'], '<orig-1@cliente.example>')
        self.assertEqual(mime['References'], '<orig-1@cliente.example>')
        self.assertIn('Ana Cliente <ana@cliente.example>', str(mime['To']))
        self.assertIn('laboratorio@grupovicaf.com', str(mime['Cc']))
        self.assertIsNone(mime['Bcc'])
        self.assertNotIn(b'gerencia@', mime.as_bytes())

    def test_imagen_incrustada_y_adjunto(self):
        mime = construir_mime(self.mensaje_saliente())
        partes = {p.get_filename(): p for p in mime.walk() if p.get_filename()}
        self.assertEqual(partes['firma.png']['Content-ID'], '<firma@vicaf>')
        self.assertEqual(partes['firma.png'].get_content_disposition(), 'inline')
        self.assertEqual(partes['oferta.pdf'].get_content_disposition(), 'attachment')
        self.assertIn('cid:firma@vicaf', mime.get_body(('html',)).get_content())

    def test_ida_y_vuelta_lo_que_sale_se_recibe_igual(self):
        saliente = self.mensaje_saliente()
        [recibido] = RecepcionEML().recibir(construir_mime(saliente).as_bytes())
        self.assertEqual(recibido.cuenta, self.lab)  # iba en CC a laboratorio@
        self.assertEqual(recibido.message_id, saliente.message_id)
        self.assertEqual({a.nombre: a.incrustado for a in recibido.adjuntos.all()},
                         {'firma.png': True, 'oferta.pdf': False})


@override_settings(CORREO_ENVIO='smtp', CORREO_SMTP_HOST='smtp.prueba', CORREO_SMTP_PUERTO=1025,
                   CORREO_SMTP_TLS=False, CORREO_SMTP_USUARIO='')
class EnvioSMTPTests(MimeTests):
    def test_elige_el_servicio_segun_la_configuracion(self):
        self.assertIsInstance(servicio_envio(), ServicioEnvioSMTP)
        with override_settings(CORREO_ENVIO='simulado'):
            self.assertIsInstance(servicio_envio(), ServicioEnvioSimulado)

    @mock.patch('correo.envio.smtplib.SMTP')
    def test_envio_correcto_guarda_el_eml_y_pasa_a_enviados(self, smtp):
        smtp.return_value.__enter__.return_value.send_message.return_value = {}
        m = self.mensaje_saliente()
        self.assertEqual(enviar_mensaje(m.pk), Mensaje.ENVIADO)
        m.refresh_from_db()
        self.assertEqual(m.carpeta.tipo, 'enviados')
        self.assertTrue(m.eml.name)
        llamada = smtp.return_value.__enter__.return_value.send_message.call_args
        self.assertEqual(llamada.kwargs['from_addr'], 'informes@grupovicaf.com')
        self.assertEqual(llamada.kwargs['to_addrs'],
                         ['ana@cliente.example', 'laboratorio@grupovicaf.com', 'gerencia@grupovicaf.example'])
        with m.eml.open('rb') as f:
            guardado = BytesParser(policy=policy.default).parsebytes(f.read())
        self.assertEqual(guardado['Message-ID'], m.message_id)

    @mock.patch('correo.envio.smtplib.SMTP')
    def test_destinatario_rechazado_es_fallo_definitivo(self, smtp):
        smtp.return_value.__enter__.return_value.send_message.side_effect = smtplib.SMTPRecipientsRefused(
            {'ana@cliente.example': (550, b'No existe')})
        m = self.mensaje_saliente()
        self.assertEqual(enviar_mensaje(m.pk), Mensaje.FALLIDO)
        m.refresh_from_db()
        self.assertEqual(m.carpeta.tipo, 'salida')
        self.assertIn('No existe', m.ultimo_error)

    @mock.patch('correo.tasks.enviar_mensaje.apply_async')
    @mock.patch('correo.envio.smtplib.SMTP', side_effect=ConnectionRefusedError('sin servidor'))
    def test_sin_conexion_queda_en_cola_y_se_reintenta(self, _smtp, reprogramar):
        m = self.mensaje_saliente()
        with self.captureOnCommitCallbacks(execute=True):
            self.assertEqual(enviar_mensaje(m.pk), Mensaje.EN_COLA)
        m.refresh_from_db()
        self.assertEqual(m.intentos, 1)
        self.assertIn('No se pudo conectar', m.ultimo_error)
        reprogramar.assert_called_once_with((m.pk,), countdown=60)

    @mock.patch('correo.tasks.enviar_mensaje.apply_async')
    @mock.patch('correo.envio.smtplib.SMTP', side_effect=ConnectionRefusedError('sin servidor'))
    def test_tras_el_ultimo_intento_queda_fallido(self, _smtp, reprogramar):
        m = self.mensaje_saliente()
        Mensaje.objects.filter(pk=m.pk).update(intentos=MAX_INTENTOS - 1)
        self.assertEqual(enviar_mensaje(m.pk), Mensaje.FALLIDO)
        reprogramar.assert_not_called()

    def test_sin_servidor_configurado_no_revienta(self):
        with override_settings(CORREO_SMTP_HOST=''):
            resultado = ServicioEnvioSMTP().enviar(self.mensaje_saliente())
        self.assertFalse(resultado.ok)
        self.assertIn('CORREO_SMTP_HOST', resultado.error)


class MailpitTests(BasePlataforma):
    def setUp(self):
        super().setUp()
        cache.clear()
        self.buzon = {
            'a1': ({'To': [{'Address': 'informes@grupovicaf.com'}], 'Cc': [], 'Bcc': []},
                   eml(message_id='<a1@cliente.example>')),
            'a2': ({'To': [{'Address': 'cliente@externa.example'}], 'Cc': [], 'Bcc': []},
                   eml(para='cliente@externa.example', message_id='<a2@x>')),
            'a3': ({'To': [{'Address': 'otra@externa.example'}], 'Cc': [],
                    'Bcc': [{'Address': 'LABORATORIO@grupovicaf.com'}]},
                   eml(para='otra@externa.example', message_id='<a3@x>')),
        }

    def pedir(self, url):
        if url.endswith('/raw'):
            return self.buzon[url.split('/')[-2]][1]
        return json.dumps({'messages': [dict(r, ID=i) for i, (r, _) in self.buzon.items()]}).encode()

    def test_trae_solo_lo_dirigido_a_cuentas_vicaf_y_una_vez(self):
        with mock.patch('correo.mailpit._pedir', side_effect=self.pedir) as pedir:
            self.assertEqual(traer('http://mailpit:8025'), 2)
            self.assertEqual(traer('http://mailpit:8025'), 0)
        crudos = [c.args[0] for c in pedir.call_args_list if c.args[0].endswith('/raw')]
        self.assertEqual(sorted(crudos), ['http://mailpit:8025/api/v1/message/a1/raw',
                                          'http://mailpit:8025/api/v1/message/a3/raw'])
        self.assertTrue(Mensaje.objects.filter(cuenta=self.informes, message_id='<a1@cliente.example>').exists())
        self.assertTrue(Mensaje.objects.filter(cuenta=self.lab, message_id='<a3@x>').exists())

    def test_mailpit_caido_no_rompe(self):
        with mock.patch('correo.mailpit._pedir', side_effect=OSError('sin conexión')):
            self.assertEqual(traer('http://mailpit:8025'), 0)


class ComandosTests(BasePlataforma):
    def test_recibir_eml_desde_archivo(self):
        with tempfile.TemporaryDirectory() as carpeta:
            ruta = Path(carpeta) / 'consulta.eml'
            ruta.write_bytes(eml(asunto='Exportado de cPanel', message_id='<cp1@x>'))
            salida = StringIO()
            call_command('recibir_eml', str(ruta), stdout=salida)
            call_command('recibir_eml', str(ruta), stdout=salida)
        self.assertIn('recibido en informes@grupovicaf.com', salida.getvalue())
        self.assertIn('ya estaba recibido', salida.getvalue())
        self.assertEqual(Mensaje.objects.filter(asunto='Exportado de cPanel').count(), 1)

    @override_settings(DEBUG=True, CORREO_ENVIO='simulado')
    def test_simular_entrante_directo_y_respuesta_en_el_mismo_hilo(self):
        call_command('simular_entrante', '--para', 'laboratorio@grupovicaf.com', '--asunto', 'Muestras', stdout=StringIO())
        nuevo = Mensaje.objects.get(cuenta=self.lab, asunto='Muestras')
        self.assertEqual(nuevo.carpeta.tipo, 'entrada')
        saliente = crear_mensaje(self.informes, 'enviados', de='informes@grupovicaf.com',
                                 para=[{'nombre': 'Ana', 'correo': 'ana@cliente.example'}],
                                 asunto='Oferta', estado=Mensaje.ENVIADO)
        call_command('simular_entrante', '--responder', str(saliente.pk), stdout=StringIO())
        respuesta = Mensaje.objects.get(cuenta=self.informes, asunto='RE: Oferta')
        self.assertEqual(respuesta.hilo_id, saliente.hilo_id)
        self.assertEqual(respuesta.de, 'ana@cliente.example')

    def test_simular_entrante_no_corre_en_produccion(self):
        with self.assertRaises(CommandError):
            call_command('simular_entrante', stdout=StringIO())
