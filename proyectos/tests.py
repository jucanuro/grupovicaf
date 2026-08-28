from datetime import date, timedelta
from decimal import Decimal

from django.contrib.auth.models import User
from django.core import mail
from django.template.loader import render_to_string
from django.test import TestCase, override_settings
from django.utils import timezone
from weasyprint import HTML

from clientes.models import Cliente
from proyectos.models import (
    DetalleSolicitudEnsayo,
    MuestraDetalle,
    Proyecto,
    RecepcionMuestra,
    SolicitudEnsayo,
    TipoMuestra,
)
from proyectos.tasks import notificar_proyectos_vencidos
from servicios.models import Cotizacion, CotizacionDetalle, CotizacionGrupo, Servicio
from trabajadores.models import RolTrabajador, TrabajadorProfile


class InformePDFRenderTest(TestCase):
    """
    Verifica que WeasyPrint (y sus libs de sistema: Pango/Cairo/GDK-Pixbuf)
    puedan renderizar la plantilla real de un informe/orden de ensayo del LIMS
    dentro del contenedor.
    """

    def setUp(self):
        user = User.objects.create_user('tecnico.lab', password='x')
        rol = RolTrabajador.objects.create(nombre='Técnico de Laboratorio')
        self.trabajador = TrabajadorProfile.objects.create(
            user=user, rol=rol, nombre_completo='Juan Pérez'
        )

        cliente = Cliente.objects.create(
            ruc='20123456789',
            razon_social='Constructora de Prueba SAC',
            persona_contacto='Ana Torres',
            celular_contacto='987654321',
            correo_contacto='ana@constructora.pe',
        )

        cotizacion = Cotizacion.objects.create(
            cliente=cliente,
            numero_oferta='OF-2026-0001',
            asunto_servicio='Ensayos de suelos',
            persona_contacto='Ana Torres',
            correo_contacto='ana@constructora.pe',
            telefono_contacto='987654321',
            tasa_igv=Decimal('0.18'),
        )
        grupo = CotizacionGrupo.objects.create(cotizacion=cotizacion, nombre_grupo='Suelos')
        servicio = Servicio.objects.create(
            codigo_facturacion='SRV-001', nombre='Ensayo de Compactación Proctor'
        )
        detalle_cot = CotizacionDetalle.objects.create(
            grupo=grupo,
            servicio=servicio,
            descripcion_especifica='Proctor Modificado',
            precio_unitario=Decimal('150.00'),
        )

        tipo_muestra = TipoMuestra.objects.create(nombre='Suelo', sigla='SU')
        recepcion = RecepcionMuestra.objects.create(
            cotizacion=cotizacion,
            procedencia='Cajamarca',
            responsable_cliente='Ana Torres',
            telefono='987654321',
            responsable_recepcion=user,
        )
        muestra = MuestraDetalle.objects.create(
            recepcion=recepcion,
            tipo_muestra=tipo_muestra,
            descripcion='Muestra de suelo Km 3',
            masa_aprox=Decimal('5.00'),
        )

        self.solicitud = SolicitudEnsayo.objects.create(
            codigo_solicitud='SOL-2026-0001',
            recepcion=recepcion,
            cotizacion=cotizacion,
            fecha_entrega_programada=date(2026, 9, 1),
            elaborado_por=self.trabajador,
        )
        DetalleSolicitudEnsayo.objects.create(
            solicitud=self.solicitud,
            muestra=muestra,
            servicio_cotizado=detalle_cot,
            descripcion_ensayo='Proctor Modificado',
            norma='ASTM D1557',
            tecnico_asignado=self.trabajador,
            fecha_entrega_programada=date(2026, 9, 1),
        )

    def test_render_ensayos_pdf_produce_pdf_valido(self):
        context = {
            'solicitud': self.solicitud,
            'proyecto': None,
            'detalles': self.solicitud.detalles.select_related('muestra', 'tecnico_asignado__user'),
            'user': self.trabajador.user,
        }
        html_string = render_to_string('proyectos/ensayos_pdf.html', context)

        pdf_bytes = HTML(string=html_string, base_url='http://testserver/').write_pdf()

        self.assertTrue(pdf_bytes.startswith(b'%PDF-'))
        self.assertGreater(len(pdf_bytes), 1000)


@override_settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')
class NotificarProyectosVencidosTest(TestCase):
    """Barrido diario de proyectos con fecha_entrega_estimada vencida."""

    def setUp(self):
        self.cliente = Cliente.objects.create(
            ruc='20456789123',
            razon_social='Minera Norte SAC',
            persona_contacto='Luis Vega',
            celular_contacto='999888777',
            correo_contacto='luis@minera.pe',
        )
        self.hoy = timezone.localdate()

    def _crear(self, codigo, **kwargs):
        return Proyecto.objects.create(
            nombre_proyecto=codigo,
            codigo_proyecto=codigo,
            cliente=self.cliente,
            **kwargs,
        )

    def test_envia_digest_con_proyectos_vencidos_abiertos(self):
        self._crear('PRJ-VENCIDO', fecha_entrega_estimada=self.hoy - timedelta(days=3), estado='EN_CURSO')

        total = notificar_proyectos_vencidos()

        self.assertEqual(total, 1)
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn('PRJ-VENCIDO', mail.outbox[0].body)

    def test_ignora_cerrados_futuros_y_sin_fecha(self):
        self._crear('PRJ-VENCIDO', fecha_entrega_estimada=self.hoy - timedelta(days=3), estado='EN_CURSO')
        self._crear('PRJ-FIN', fecha_entrega_estimada=self.hoy - timedelta(days=9), estado='FINALIZADO')
        self._crear('PRJ-CAN', fecha_entrega_estimada=self.hoy - timedelta(days=9), estado='CANCELADO')
        self._crear('PRJ-SIN-FECHA', estado='EN_CURSO')
        self._crear('PRJ-FUTURO', fecha_entrega_estimada=self.hoy + timedelta(days=5), estado='EN_CURSO')

        total = notificar_proyectos_vencidos()

        self.assertEqual(total, 1)

    def test_sin_vencidos_no_envia_correo(self):
        self._crear('PRJ-OK', fecha_entrega_estimada=self.hoy + timedelta(days=2), estado='EN_CURSO')

        total = notificar_proyectos_vencidos()

        self.assertEqual(total, 0)
        self.assertEqual(mail.outbox, [])
