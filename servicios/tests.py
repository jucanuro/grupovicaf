from decimal import Decimal

from django.core.exceptions import ValidationError
from django.test import TestCase

from clientes.models import Cliente
from servicios.models import Cotizacion, CotizacionDetalle, CotizacionGrupo, Servicio


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
