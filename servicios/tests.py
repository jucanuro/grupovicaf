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
