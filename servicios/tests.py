from unittest.mock import patch
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.test import TestCase, override_settings
from django.urls import reverse

from clientes.models import Cliente
from servicios.models import CategoriaServicio, Cotizacion, CotizacionDetalle, CotizacionGrupo, Servicio
from trabajadores.testing import crear_trabajador, rol_con_permisos
from web_catalogo.models import ServicioPublicado
from web_contacto.models import SolicitudCotizacionItem, SolicitudCotizacionWeb


class CotizacionTasaIgvTipoNumericoTests(TestCase):
    """Cotizacion.save() debe aceptar tasa_igv como str/int/float/Decimal
    y convertirlo con Decimal(str(valor)), nunca dejar pasar un TypeError."""

    @classmethod
    def setUpTestData(cls):
        cls.cliente = Cliente.objects.create(
            ruc="20123456789",
            razon_social="Cliente de Prueba SAC",
        )

    def _crear_cotizacion(self, tasa_igv):
        return Cotizacion.objects.create(
            cliente=self.cliente,
            asunto_servicio="Servicio de prueba",
            persona_contacto="Juan Perez",
            correo_contacto="juan@example.com",
            telefono_contacto="999999999",
            tasa_igv=tasa_igv,
        )

    def test_acepta_decimal(self):
        cot = self._crear_cotizacion(Decimal('0.18'))
        self.assertIsInstance(cot.tasa_igv, Decimal)
        self.assertEqual(cot.tasa_igv, Decimal('0.18'))

    def test_acepta_str(self):
        cot = self._crear_cotizacion("0.18")
        self.assertIsInstance(cot.tasa_igv, Decimal)
        self.assertEqual(cot.tasa_igv, Decimal('0.18'))

    def test_acepta_int(self):
        cot = self._crear_cotizacion(0)
        self.assertIsInstance(cot.tasa_igv, Decimal)
        self.assertEqual(cot.tasa_igv, Decimal('0'))

    def test_acepta_float_sin_ruido_binario(self):
        cot = self._crear_cotizacion(0.18)
        self.assertIsInstance(cot.tasa_igv, Decimal)
        # Decimal(str(0.18)) == Decimal('0.18'); Decimal(0.18) directo no.
        self.assertEqual(cot.tasa_igv, Decimal('0.18'))
        self.assertNotEqual(cot.tasa_igv, Decimal(0.18))

    def test_valor_invalido_lanza_validation_error_no_typeerror(self):
        with self.assertRaises(ValidationError):
            self._crear_cotizacion("no-es-un-numero")

    def test_tipo_no_soportado_lanza_validation_error_no_typeerror(self):
        with self.assertRaises(ValidationError):
            self._crear_cotizacion(["0.18"])


class CotizacionDetallePrecioUnitarioTipoNumericoTests(TestCase):
    """CotizacionDetalle.save() debe aceptar precio_unitario como
    str/int/float/Decimal y calcular total_detalle sin error de tipos."""

    @classmethod
    def setUpTestData(cls):
        cls.cliente = Cliente.objects.create(
            ruc="20123456780",
            razon_social="Cliente Detalle SAC",
        )
        cls.servicio = Servicio.objects.create(
            codigo_facturacion="SRV-002",
            nombre="Ensayo de prueba",
        )
        cls.cotizacion = Cotizacion.objects.create(
            cliente=cls.cliente,
            asunto_servicio="Servicio de prueba",
            persona_contacto="Ana Lopez",
            correo_contacto="ana@example.com",
            telefono_contacto="988888888",
        )
        cls.grupo = CotizacionGrupo.objects.create(
            cotizacion=cls.cotizacion,
            nombre_grupo="Grupo de prueba",
        )

    def _crear_detalle(self, precio_unitario, cantidad=3):
        return CotizacionDetalle.objects.create(
            grupo=self.grupo,
            servicio=self.servicio,
            descripcion_especifica="Detalle de prueba",
            cantidad=cantidad,
            precio_unitario=precio_unitario,
        )

    def test_acepta_decimal(self):
        det = self._crear_detalle(Decimal('19.99'))
        self.assertEqual(det.total_detalle, Decimal('59.97'))

    def test_acepta_str(self):
        det = self._crear_detalle("19.99")
        self.assertEqual(det.total_detalle, Decimal('59.97'))

    def test_acepta_int(self):
        det = self._crear_detalle(20)
        self.assertEqual(det.total_detalle, Decimal('60'))

    def test_acepta_float_sin_ruido_binario(self):
        det = self._crear_detalle(19.99)
        self.assertEqual(det.precio_unitario, Decimal('19.99'))
        self.assertEqual(det.total_detalle, Decimal('59.97'))

    def test_valor_invalido_lanza_validation_error_no_typeerror(self):
        with self.assertRaises(ValidationError):
            self._crear_detalle("no-es-un-numero")

    def test_tipo_no_soportado_lanza_validation_error_no_typeerror(self):
        with self.assertRaises(ValidationError):
            self._crear_detalle(object())


@override_settings(ROOT_URLCONF='grupovicaf.urls_lab')
class SolicitudesWebBandejaTests(TestCase):
    """W1: la solicitud pública se convierte en cotización solo desde el LIMS."""

    @classmethod
    def setUpTestData(cls):
        categoria = CategoriaServicio.objects.create(nombre='Suelos')
        cls.servicio = Servicio.objects.create(
            codigo_facturacion='ES011-TEST', nombre='CBR', precio_base=Decimal('150.00'), unidad_base='Ensayo',
        )
        publicado = ServicioPublicado.objects.create(
            servicio=cls.servicio, categoria=categoria, slug='ensayo-cbr-test',
            titulo_publico='Ensayo CBR', resumen='r', contenido='c', activo=True,
        )
        cls.solicitud = SolicitudCotizacionWeb.objects.create(
            ruc='20123456789', razon_social='Constructora Test SAC', persona_contacto='Juan Perez',
            correo_contacto='juan@example.com', telefono_contacto='999999999',
            necesidad='CBR para vía.', origen='/servicios/ensayo-cbr-test/',
        )
        SolicitudCotizacionItem.objects.create(
            solicitud=cls.solicitud, servicio_publicado=publicado, cantidad_estimada=2,
        )
        comercial = rol_con_permisos('Comercial', 'cotizaciones.ver', 'cotizaciones.crear', 'cotizaciones.eliminar')
        cls.user_comercial, _ = crear_trabajador('comercial', comercial)
        tecnico = rol_con_permisos('Técnico', 'cotizaciones.ver')
        cls.user_tecnico, _ = crear_trabajador('tecnico', tecnico)

    def _url(self, nombre, pk=None):
        return reverse(f'servicios:{nombre}', args=[pk] if pk else [])

    def test_bandeja_lista_pendientes_y_avisa_ruc_existente(self):
        Cliente.objects.create(ruc='20123456789', razon_social='Cliente Real SAC')
        self.client.force_login(self.user_comercial)

        respuesta = self.client.get(self._url('lista_solicitudes_web'))

        self.assertContains(respuesta, 'Constructora Test SAC')
        self.assertContains(respuesta, 'Cliente Real SAC')

    def test_convertir_crea_cliente_y_cotizacion_con_numero_vcf_ote(self):
        self.client.force_login(self.user_comercial)

        respuesta = self.client.post(self._url('convertir_solicitud_web', self.solicitud.pk))

        self.solicitud.refresh_from_db()
        cotizacion = self.solicitud.cotizacion
        self.assertRedirects(respuesta, self._url('editar_cotizacion', cotizacion.pk), fetch_redirect_response=False)
        self.assertTrue(cotizacion.numero_oferta.startswith('VCF-OTE-'))
        self.assertEqual(cotizacion.cliente.origen, 'web')
        self.assertFalse(cotizacion.cliente.activo)
        detalle = cotizacion.detalles_cotizacion[0]
        self.assertEqual(detalle.servicio, self.servicio)
        self.assertEqual(detalle.cantidad, 2)

    def test_convertir_dos_veces_no_duplica_la_cotizacion(self):
        self.client.force_login(self.user_comercial)
        self.client.post(self._url('convertir_solicitud_web', self.solicitud.pk))
        self.client.post(self._url('convertir_solicitud_web', self.solicitud.pk))

        self.assertEqual(Cotizacion.objects.count(), 1)

    def test_sin_permiso_de_crear_no_puede_convertir(self):
        self.client.force_login(self.user_tecnico)

        respuesta = self.client.post(self._url('convertir_solicitud_web', self.solicitud.pk))

        self.assertEqual(respuesta.status_code, 403)
        self.assertFalse(Cotizacion.objects.exists())

    def test_descartar_borra_la_solicitud_pendiente(self):
        self.client.force_login(self.user_comercial)

        self.client.post(self._url('descartar_solicitud_web', self.solicitud.pk))

        self.assertFalse(SolicitudCotizacionWeb.objects.exists())

    def test_convertir_por_get_no_esta_permitido(self):
        self.client.force_login(self.user_comercial)

        respuesta = self.client.get(self._url('convertir_solicitud_web', self.solicitud.pk))

        self.assertEqual(respuesta.status_code, 405)


@override_settings(ROOT_URLCONF='grupovicaf.urls_lab')
class MarcarCotizacionTests(TestCase):
    """REQ-LIMS-22 a 24: transiciones manuales Enviada/Rechazada (RN-08)."""

    @classmethod
    def setUpTestData(cls):
        cls.cliente = Cliente.objects.create(ruc='20123456780', razon_social='Cliente Estados SAC')
        comercial = rol_con_permisos('Comercial estados', 'cotizaciones.ver')
        cls.user_comercial, _ = crear_trabajador('comercial.estados', comercial)
        sin_permiso = rol_con_permisos('Sin cotizaciones', 'ensayos.ver')
        cls.user_sin_permiso, _ = crear_trabajador('sin.cotizaciones', sin_permiso)

    def _cotizacion(self, estado, numero):
        return Cotizacion.objects.create(
            cliente=self.cliente, numero_oferta=numero, estado=estado,
            asunto_servicio='Ensayos', persona_contacto='Ana', correo_contacto='ana@example.com',
            telefono_contacto='999999999',
        )

    def _post(self, nombre, cotizacion):
        return self.client.post(reverse(f'servicios:{nombre}', args=[cotizacion.pk]))

    def test_pendiente_pasa_a_enviada(self):
        cotizacion = self._cotizacion('Pendiente', 'T-001')
        self.client.force_login(self.user_comercial)

        respuesta = self._post('marcar_cotizacion_enviada', cotizacion)

        self.assertRedirects(respuesta, reverse('servicios:lista_cotizaciones'), fetch_redirect_response=False)
        cotizacion.refresh_from_db()
        self.assertEqual(cotizacion.estado, 'Enviada')

    def test_pendiente_y_enviada_pasan_a_rechazada(self):
        self.client.force_login(self.user_comercial)
        for estado, numero in (('Pendiente', 'T-002'), ('Enviada', 'T-003')):
            cotizacion = self._cotizacion(estado, numero)
            self._post('marcar_cotizacion_rechazada', cotizacion)
            cotizacion.refresh_from_db()
            self.assertEqual(cotizacion.estado, 'Rechazada', estado)

    def test_transiciones_no_permitidas_no_cambian_el_estado(self):
        self.client.force_login(self.user_comercial)
        casos = [
            ('marcar_cotizacion_enviada', 'Enviada'),
            ('marcar_cotizacion_enviada', 'Aceptada'),
            ('marcar_cotizacion_enviada', 'Rechazada'),
            ('marcar_cotizacion_rechazada', 'Aceptada'),
            ('marcar_cotizacion_rechazada', 'Anulada'),
            ('marcar_cotizacion_rechazada', 'Rechazada'),
        ]
        for i, (accion, estado) in enumerate(casos):
            cotizacion = self._cotizacion(estado, f'T-1{i:02d}')
            self._post(accion, cotizacion)
            cotizacion.refresh_from_db()
            self.assertEqual(cotizacion.estado, estado, accion)

    def test_get_no_cambia_el_estado(self):
        cotizacion = self._cotizacion('Pendiente', 'T-004')
        self.client.force_login(self.user_comercial)

        respuesta = self.client.get(reverse('servicios:marcar_cotizacion_enviada', args=[cotizacion.pk]))

        self.assertEqual(respuesta.status_code, 405)
        cotizacion.refresh_from_db()
        self.assertEqual(cotizacion.estado, 'Pendiente')

    def test_sin_permiso_cotizaciones_ver_da_403(self):
        cotizacion = self._cotizacion('Pendiente', 'T-005')
        self.client.force_login(self.user_sin_permiso)

        respuesta = self._post('marcar_cotizacion_enviada', cotizacion)

        self.assertEqual(respuesta.status_code, 403)
        cotizacion.refresh_from_db()
        self.assertEqual(cotizacion.estado, 'Pendiente')

    def test_la_lista_muestra_solo_los_botones_que_aplican(self):
        pendiente = self._cotizacion('Pendiente', 'T-006')
        enviada = self._cotizacion('Enviada', 'T-007')
        aceptada = self._cotizacion('Aceptada', 'T-008')
        self.client.force_login(self.user_comercial)

        html = self.client.get(reverse('servicios:lista_cotizaciones')).content.decode()

        # «Enviar» abre el correo con el cliente (Pendiente; una Enviada solo si se editó); Aceptada no lo ofrece.
        self.assertIn(reverse('servicios:enviar_cotizacion', args=[pendiente.pk]), html)
        self.assertIn(reverse('servicios:marcar_cotizacion_rechazada', args=[pendiente.pk]), html)
        self.assertNotIn(reverse('servicios:enviar_cotizacion', args=[enviada.pk]), html)  # ya enviada: no se reenvía sin cambios
        self.assertIn(reverse('servicios:marcar_cotizacion_rechazada', args=[enviada.pk]), html)
        self.assertNotIn(reverse('servicios:enviar_cotizacion', args=[aceptada.pk]), html)
        self.assertNotIn(reverse('servicios:marcar_cotizacion_rechazada', args=[aceptada.pk]), html)


class EnviarCotizacionCorreoTests(TestCase):
    """«Enviar» abre el correo con el cliente como destinatario y la cotización adjunta."""

    @classmethod
    def setUpTestData(cls):
        from correo.models import AccesoCuenta, CuentaCorreo
        cls.cliente = Cliente.objects.create(ruc='20123456781', razon_social='Cliente Correo SAC')
        rol = rol_con_permisos('Comercial correo', 'cotizaciones.ver', 'correo.ver')
        cls.user, _ = crear_trabajador('comercial.correo', rol)
        cls.cuenta = CuentaCorreo.objects.create(direccion='ventas@vicaf.pe', nombre='Ventas VICAF', slug='ventas-cot')
        AccesoCuenta.objects.create(usuario=cls.user, cuenta=cls.cuenta, rol=AccesoCuenta.GESTIONA)

    def _cotizacion(self, estado='Pendiente', correo='ana@example.com'):
        return Cotizacion.objects.create(
            cliente=self.cliente, numero_oferta='T-900', estado=estado, asunto_servicio='Ensayos de concreto',
            persona_contacto='Ana Pérez', correo_contacto=correo, telefono_contacto='999999999',
        )

    def test_crea_borrador_para_el_cliente_y_lleva_al_correo(self):
        from correo.models import Mensaje
        cot = self._cotizacion()
        self.client.force_login(self.user)
        with patch('correo.tasks.adjuntar_cotizacion') as adjuntar, self.captureOnCommitCallbacks(execute=True):
            r = self.client.post(reverse('servicios:enviar_cotizacion_correo', args=[cot.pk]))
        self.assertEqual(r.status_code, 302)
        self.assertIn('/entrar/', r['Location'])
        borrador = Mensaje.objects.get(estado_envio=Mensaje.BORRADOR)
        cot.refresh_from_db()
        self.assertEqual(cot.mensaje_envio, borrador.pk)
        self.assertEqual(cot.estado, 'Pendiente')  # abrir el borrador no cuenta como enviada
        self.assertEqual(borrador.para, [{'nombre': 'Ana Pérez', 'correo': 'ana@example.com'}])
        self.assertEqual(borrador.cuenta, self.cuenta)
        self.assertIn('T-900', borrador.asunto)
        adjuntar.delay.assert_called_once_with(borrador.pk, cot.pk, self.user.pk)

    def test_sin_correo_del_cliente_no_crea_borrador(self):
        from correo.models import Mensaje
        cot = self._cotizacion(correo='')
        type(cot.cliente).objects.filter(pk=cot.cliente_id).update(correo_contacto='')
        self.client.force_login(self.user)
        self.client.post(reverse('servicios:enviar_cotizacion_correo', args=[cot.pk]), follow=True)
        self.assertFalse(Mensaje.objects.filter(estado_envio=Mensaje.BORRADOR).exists())
        cot.refresh_from_db()
        self.assertEqual(cot.estado, 'Pendiente')

    def test_enviar_vuelve_a_aparecer_solo_si_se_edito_una_enviada(self):
        cot = self._cotizacion(estado='Enviada')
        self.client.force_login(self.user)
        url = reverse('servicios:lista_cotizaciones')
        html = self.client.get(url).content.decode()
        self.assertNotIn(reverse('servicios:enviar_cotizacion', args=[cot.pk]), html)
        Cotizacion.objects.filter(pk=cot.pk).update(requiere_reenvio=True)
        html = self.client.get(url).content.decode()
        self.assertIn(reverse('servicios:enviar_cotizacion', args=[cot.pk]), html)
        # Al salir el correo (enviar_mensaje), la cotización queda enviada y el botón desaparece.
        from correo.models import Mensaje
        from correo.tasks import enviar_mensaje
        with patch('correo.tasks.adjuntar_cotizacion'):
            self.client.post(reverse('servicios:enviar_cotizacion_correo', args=[cot.pk]))
        cot.refresh_from_db()
        Mensaje.objects.filter(pk=cot.mensaje_envio).update(estado_envio=Mensaje.EN_COLA)
        with override_settings(CORREO_ENVIO='simulado'):
            enviar_mensaje.apply(args=[cot.mensaje_envio])
        cot.refresh_from_db()
        self.assertFalse(cot.requiere_reenvio)
        self.assertEqual((cot.estado, cot.canal_envio), ('Enviada', 'correo'))

    def test_la_verificacion_publica_solo_confirma_numero_y_fecha(self):
        cot = self._cotizacion(estado='Pendiente')
        Cotizacion.objects.filter(pk=cot.pk).update(monto_total=Decimal('999.99'))
        self.client.logout()
        r = self.client.get(reverse('servicios:verificar_cotizacion', args=['T-900']))
        self.assertEqual(r.status_code, 200)
        html = r.content.decode()
        self.assertIn('T-900', html)
        self.assertIn('noindex', html)
        for dato_privado in ('999', 'Cliente Correo SAC', 'ana@example.com', '20123456781'):
            self.assertNotIn(dato_privado, html)
        self.assertEqual(self.client.get(reverse('servicios:verificar_cotizacion', args=['NO-EXISTE'])).status_code, 404)

    def test_una_aceptada_no_se_envia(self):
        cot = self._cotizacion(estado='Aceptada')
        self.client.force_login(self.user)
        r = self.client.post(reverse('servicios:enviar_cotizacion_correo', args=[cot.pk]))
        self.assertEqual(r.status_code, 302)
        cot.refresh_from_db()
        self.assertEqual(cot.estado, 'Aceptada')
