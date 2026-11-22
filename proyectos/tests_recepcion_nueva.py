"""«Nueva recepción» de la lista de muestras apuntaba a «#» y no hacía nada
(pedido del cliente, 2026-11-22). Ahora abre la elección de proyecto."""
from django.test import TestCase, override_settings
from django.urls import reverse

from clientes.models import Cliente
from proyectos.models import Proyecto
from servicios.models import Cotizacion
from trabajadores.testing import crear_trabajador, rol_con_permisos


@override_settings(ROOT_URLCONF='grupovicaf.urls_lab')
class NuevaRecepcionTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        cliente = Cliente.objects.create(ruc='20111111111', razon_social='Constructora Uno SAC')
        cot = Cotizacion.objects.create(
            numero_oferta='VCF-OTE-2026-900', cliente=cliente, estado='Aceptada', asunto_servicio='x',
            persona_contacto='X', correo_contacto='x@x.invalid', telefono_contacto='1',
        )
        cls.abierto = Proyecto.objects.create(
            nombre_proyecto='Edificio Norte', codigo_proyecto='P-ABIERTO', cliente=cliente, cotizacion=cot,
        )
        Proyecto.objects.create(
            nombre_proyecto='Cerrado', codigo_proyecto='P-CERRADO', cliente=cliente, cotizacion=cot,
            estado='FINALIZADO',
        )
        Proyecto.objects.create(nombre_proyecto='Sin cotización', codigo_proyecto='P-SINCOT', cliente=cliente)
        cls.recepcion, _ = crear_trabajador('recepcion', rol_con_permisos('Recepción', 'muestras.ver', 'muestras.crear'))
        cls.lector, _ = crear_trabajador('lector', rol_con_permisos('Lector', 'muestras.ver'))

    def test_el_boton_lleva_a_elegir_proyecto(self):
        self.client.force_login(self.recepcion)
        html = self.client.get(reverse('proyectos:lista_recepciones')).content.decode()
        self.assertIn(f'href="{reverse("proyectos:crear_recepcion")}"', html)
        self.assertNotIn('href="#"\n            class="command-header__action"', html)

    def test_sin_permiso_de_crear_no_se_ofrece(self):
        self.client.force_login(self.lector)
        html = self.client.get(reverse('proyectos:lista_recepciones')).content.decode()
        self.assertNotIn('data-testid="nueva-recepcion"', html)
        self.assertEqual(self.client.get(reverse('proyectos:crear_recepcion')).status_code, 403)

    def test_lista_solo_proyectos_abiertos_con_cotizacion(self):
        self.client.force_login(self.recepcion)
        resp = self.client.get(reverse('proyectos:crear_recepcion'))
        self.assertEqual(resp.status_code, 200)
        html = resp.content.decode()
        self.assertIn(reverse('proyectos:crear_recepcion_desde_proyecto', args=[self.abierto.pk]), html)
        self.assertNotIn('P-CERRADO', html)
        self.assertNotIn('P-SINCOT', html)

    def test_busca_por_cliente_o_numero_de_oferta(self):
        self.client.force_login(self.recepcion)
        self.assertContains(self.client.get(reverse('proyectos:crear_recepcion'), {'q': 'OTE-2026-900'}), 'P-ABIERTO')
        self.assertNotContains(self.client.get(reverse('proyectos:crear_recepcion'), {'q': 'no-existe'}), 'P-ABIERTO')
