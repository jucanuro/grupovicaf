"""Pasos 4 y 5: webhook firmado de Cloudflare, rebotes de SES y cabecera de configuración."""
import json
import time
from unittest import mock

from django.test import Client, override_settings

from .almacen import almacen_correo
from .models import EventoMensaje, Mensaje
from .tests_correo_real import eml
from .tests_plataforma import BasePlataforma
from .webhooks import firma_entrante

HOST = 'email.localhost'
SECRETO = 'secreto-de-pruebas'


@override_settings(CORREO_WEBHOOK_SECRET=SECRETO, ALLOWED_HOSTS=['*'])
class WebhookCloudflareTests(BasePlataforma):
    def enviar(self, crudo, *, para='informes@grupovicaf.com', fecha=None, secreto=SECRETO, firma=None):
        fecha = str(fecha if fecha is not None else int(time.time()))
        firma = firma or firma_entrante(secreto, fecha, para, crudo)
        return Client().post(
            '/api/entrante/', data=crudo, content_type='message/rfc822', HTTP_HOST=HOST,
            HTTP_X_VICAF_FECHA=fecha, HTTP_X_VICAF_PARA=para, HTTP_X_VICAF_FIRMA=firma,
        )

    def test_correo_firmado_entra_a_la_bandeja(self):
        crudo = eml(asunto='Desde Cloudflare', message_id='<cf1@cliente.example>')
        r = self.enviar(crudo)
        self.assertEqual(r.status_code, 202)
        m = Mensaje.objects.get(cuenta=self.informes, asunto='Desde Cloudflare')
        self.assertEqual(m.estado_envio, Mensaje.RECIBIDO)
        self.assertEqual(m.carpeta.tipo, 'entrada')
        # El archivo temporal no se queda en el almacén.
        self.assertFalse(almacen_correo.exists(f'entrantes/{r.json()["sha256"]}.eml'))

    def test_reintento_del_worker_no_duplica(self):
        crudo = eml(asunto='Una vez', message_id='<cf2@cliente.example>')
        self.assertEqual(self.enviar(crudo).status_code, 202)
        self.assertEqual(self.enviar(crudo).status_code, 202)
        self.assertEqual(Mensaje.objects.filter(asunto='Una vez').count(), 1)

    def test_copia_oculta_llega_por_el_sobre(self):
        crudo = eml(para='otro@cliente.example', asunto='Cco', message_id='<cf3@cliente.example>')
        self.assertEqual(self.enviar(crudo, para='laboratorio@grupovicaf.com').status_code, 202)
        self.assertTrue(Mensaje.objects.filter(cuenta=self.lab, asunto='Cco').exists())

    @override_settings(CORREO_ENTRADA_ALIAS={'entrada.grupovicaf.com': 'grupovicaf.com'})
    def test_dominio_piloto_equivale_al_real(self):
        crudo = eml(para='informes@entrada.grupovicaf.com', asunto='Piloto', message_id='<cf4@cliente.example>')
        self.assertEqual(self.enviar(crudo, para='informes@entrada.grupovicaf.com').status_code, 202)
        self.assertTrue(Mensaje.objects.filter(cuenta=self.informes, asunto='Piloto').exists())

    def test_firma_incorrecta(self):
        crudo = eml()
        r = self.enviar(crudo, firma='0' * 64)
        self.assertEqual(r.status_code, 401)
        self.assertFalse(Mensaje.objects.filter(message_id='<m1@cliente.example>').exists())

    def test_secreto_distinto(self):
        self.assertEqual(self.enviar(eml(), secreto='otro').status_code, 401)

    def test_cuerpo_alterado_no_pasa(self):
        crudo = eml(asunto='Original')
        firma = firma_entrante(SECRETO, str(int(time.time())), 'informes@grupovicaf.com', crudo)
        r = self.enviar(crudo + b'x', firma=firma)
        self.assertEqual(r.status_code, 401)

    def test_firma_vencida(self):
        self.assertEqual(self.enviar(eml(), fecha=int(time.time()) - 3600).status_code, 401)

    def test_destinatario_desconocido_se_rechaza(self):
        r = self.enviar(eml(para='nadie@grupovicaf.com'), para='nadie@grupovicaf.com')
        self.assertEqual(r.status_code, 404)

    def test_cuenta_inactiva_se_rechaza(self):
        self.lab.activa = False
        self.lab.save()
        self.assertEqual(self.enviar(eml(), para='laboratorio@grupovicaf.com').status_code, 404)

    @override_settings(CORREO_WEBHOOK_SECRET='')
    def test_sin_secreto_configurado(self):
        self.assertEqual(self.enviar(eml()).status_code, 503)

    @override_settings(CORREO_MAX_ENTRANTE_BYTES=100)
    def test_demasiado_grande(self):
        self.assertEqual(self.enviar(b'x' * 500).status_code, 413)

    def test_solo_post(self):
        r = Client().get('/api/entrante/', HTTP_HOST=HOST)
        self.assertEqual(r.status_code, 405)

    def test_html_peligroso_se_limpia(self):
        crudo = eml(asunto='XSS', html='<p>Hola</p><script>alert(1)</script>', message_id='<cf9@cliente.example>')
        self.enviar(crudo)
        m = Mensaje.objects.get(asunto='XSS')
        self.assertNotIn('<script', m.cuerpo_html)


@override_settings(CORREO_SES_TOKEN='tok-ses', ALLOWED_HOSTS=['*'])
class EventosSESTests(BasePlataforma):
    def setUp(self):
        super().setUp()
        from .mensajeria import crear_mensaje
        self.hilo_msg = crear_mensaje(
            self.informes, 'enviados', de='informes@grupovicaf.com',
            para=[{'nombre': '', 'correo': 'x@cliente.example'}], asunto='Propuesta', texto='Hola',
            message_id='<salida1@grupovicaf.com>', estado=Mensaje.ENVIADO,
        )

    def aviso(self, evento, token='tok-ses', tipo='Notification', **extra):
        sobre = {'Type': tipo, 'Message': json.dumps(evento), **extra}
        return Client().post(f'/api/ses/{token}/', data=json.dumps(sobre), content_type='text/plain', HTTP_HOST=HOST)

    def rebote(self, tipo='Permanent'):
        return {
            'eventType': 'Bounce',
            'bounce': {'bounceType': tipo, 'bouncedRecipients': [
                {'emailAddress': 'x@cliente.example', 'diagnosticCode': 'smtp; 550 5.1.1 user unknown'}]},
            'mail': {'commonHeaders': {'messageId': '<salida1@grupovicaf.com>'}},
        }

    def test_rebote_permanente_marca_fallido(self):
        self.assertEqual(self.aviso(self.rebote()).status_code, 204)
        m = Mensaje.objects.get(pk=self.hilo_msg.pk)
        self.assertEqual(m.estado_envio, Mensaje.FALLIDO)
        self.assertIn('user unknown', m.ultimo_error)
        self.assertTrue(EventoMensaje.objects.filter(mensaje=m, detalle__accion='rebote').exists())

    def test_rebote_temporal_no_cambia_nada(self):
        self.aviso(self.rebote('Transient'))
        self.assertEqual(Mensaje.objects.get(pk=self.hilo_msg.pk).estado_envio, Mensaje.ENVIADO)

    def test_queja_queda_en_la_bitacora(self):
        evento = {'eventType': 'Complaint', 'complaint': {'complainedRecipients': [{'emailAddress': 'x@cliente.example'}]},
                  'mail': {'commonHeaders': {'messageId': '<salida1@grupovicaf.com>'}}}
        self.aviso(evento)
        self.assertTrue(EventoMensaje.objects.filter(mensaje=self.hilo_msg, detalle__accion='queja').exists())
        self.assertEqual(Mensaje.objects.get(pk=self.hilo_msg.pk).estado_envio, Mensaje.ENVIADO)

    def test_evento_de_mensaje_desconocido(self):
        evento = self.rebote()
        evento['mail']['commonHeaders']['messageId'] = '<otro@x>'
        self.assertEqual(self.aviso(evento).status_code, 204)

    def test_rebote_se_reconoce_por_la_etiqueta_de_ses(self):
        evento = self.rebote()
        evento['mail'] = {'messageId': '010001abc-000000', 'commonHeaders': {'messageId': '010001abc-000000'},
                          'tags': {'vicaf_mensaje': [str(self.hilo_msg.pk)]}}
        self.assertEqual(self.aviso(evento).status_code, 204)
        self.assertEqual(Mensaje.objects.get(pk=self.hilo_msg.pk).estado_envio, Mensaje.FALLIDO)

    def test_token_incorrecto(self):
        self.assertEqual(self.aviso(self.rebote(), token='malo').status_code, 404)
        self.assertEqual(Mensaje.objects.get(pk=self.hilo_msg.pk).estado_envio, Mensaje.ENVIADO)

    @override_settings(CORREO_SES_TOKEN='')
    def test_sin_token_configurado(self):
        self.assertEqual(self.aviso(self.rebote(), token='x').status_code, 404)

    def test_confirmacion_de_suscripcion_valida_el_host(self):
        with mock.patch('correo.webhooks.urllib.request.urlopen') as abrir:
            r = self.aviso({}, tipo='SubscriptionConfirmation', SubscribeURL='https://evil.example/confirm')
            self.assertEqual(r.status_code, 502)
            abrir.assert_not_called()
            abrir.return_value.__enter__.return_value.status = 200
            r = self.aviso({}, tipo='SubscriptionConfirmation',
                           SubscribeURL='https://sns.us-east-1.amazonaws.com/?Action=ConfirmSubscription&Token=t')
            self.assertEqual(r.status_code, 200)
            abrir.assert_called_once()

    @override_settings(CORREO_SES_TOPIC_ARN='arn:aws:sns:us-east-1:1:vicaf')
    def test_tema_distinto_se_rechaza(self):
        self.assertEqual(self.aviso(self.rebote(), TopicArn='arn:aws:sns:us-east-1:1:otro').status_code, 403)


class CabeceraSESTests(BasePlataforma):
    @override_settings(CORREO_SES_CONFIG_SET='vicaf-correo')
    def test_el_mime_lleva_el_conjunto_de_configuracion(self):
        from .envio import construir_mime
        from .mensajeria import crear_mensaje
        m = crear_mensaje(self.informes, 'enviados', de='informes@grupovicaf.com',
                          para=[{'nombre': '', 'correo': 'x@cliente.example'}], asunto='S', texto='t',
                          message_id='<c1@grupovicaf.com>')
        self.assertEqual(construir_mime(m)['X-SES-CONFIGURATION-SET'], 'vicaf-correo')
        self.assertEqual(construir_mime(m)['X-SES-MESSAGE-TAGS'], f'vicaf_mensaje={m.pk}')

    def test_sin_conjunto_no_hay_cabecera(self):
        from .envio import construir_mime
        from .mensajeria import crear_mensaje
        m = crear_mensaje(self.informes, 'enviados', de='informes@grupovicaf.com',
                          para=[{'nombre': '', 'correo': 'x@cliente.example'}], asunto='S', texto='t',
                          message_id='<c2@grupovicaf.com>')
        self.assertIsNone(construir_mime(m)['X-SES-CONFIGURATION-SET'])
