"""Campana de notificaciones y menú lateral del LIMS (pedido del cliente,
2026-11-22): la campana mostraba un punto rojo fijo y no hacía nada; el menú
era una burbuja en la esquina y se pidió a la izquierda y plegable."""
from datetime import date, timedelta

from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from clientes.models import Cliente
from proyectos.models import Proyecto
from servicios.models import Cotizacion
from trabajadores.testing import crear_trabajador, rol_con_permisos


def _cotizacion(numero, cliente, estado='Pendiente', plantilla=False):
    return Cotizacion.objects.create(
        numero_oferta=None if plantilla else numero, cliente=cliente, estado=estado,
        asunto_servicio='Prueba', persona_contacto='X', correo_contacto='x@x.invalid',
        telefono_contacto='1', es_plantilla=plantilla,
    )


@override_settings(ROOT_URLCONF='grupovicaf.urls_lab')
class CampanaTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.cliente = Cliente.objects.create(ruc='20111111111', razon_social='Constructora Uno SAC')
        _cotizacion('C-1', cls.cliente)
        _cotizacion('C-2', cls.cliente)
        _cotizacion('C-3', cls.cliente, estado='Aceptada')
        _cotizacion('PL', cls.cliente, plantilla=True)
        Proyecto.objects.create(
            nombre_proyecto='Vencido', codigo_proyecto='P-V', cliente=cls.cliente,
            fecha_entrega_estimada=timezone.localdate() - timedelta(days=3),
        )
        Proyecto.objects.create(
            nombre_proyecto='Al día', codigo_proyecto='P-OK', cliente=cls.cliente,
            fecha_entrega_estimada=timezone.localdate() + timedelta(days=3),
        )
        cls.comercial, _ = crear_trabajador('comercial', rol_con_permisos('Comercial', 'cotizaciones.ver'))
        cls.jefe, _ = crear_trabajador('jefe', rol_con_permisos('Jefe', 'cotizaciones.ver', 'proyectos.ver'))
        cls.sin_permisos, _ = crear_trabajador('nadie', rol_con_permisos('Nada'))

    def avisos(self, user):
        self.client.force_login(user)
        resp = self.client.get(reverse('notificaciones'))
        self.assertEqual(resp.status_code, 200)
        return resp.json()

    def test_cuenta_solo_lo_pendiente_y_sin_plantillas(self):
        datos = self.avisos(self.comercial)
        por_clave = {a['clave']: a for a in datos['avisos']}
        self.assertEqual(por_clave['cotizaciones_pendientes']['cantidad'], 2)
        self.assertIn('estado=Pendiente', por_clave['cotizaciones_pendientes']['url'])
        self.assertNotIn('proyectos_vencidos', por_clave)  # sin proyectos.ver
        self.assertEqual(datos['total'], 2)

    def test_cada_aviso_respeta_su_permiso(self):
        claves = {a['clave'] for a in self.avisos(self.jefe)['avisos']}
        self.assertEqual(claves, {'cotizaciones_pendientes', 'proyectos_vencidos'})
        self.assertEqual(self.avisos(self.sin_permisos), {'total': 0, 'avisos': []})

    def test_exige_sesion(self):
        resp = self.client.get(reverse('notificaciones'))
        self.assertEqual(resp.status_code, 302)

    def test_la_campana_ya_no_tiene_punto_fijo(self):
        self.client.force_login(self.comercial)
        html = self.client.get(reverse('servicios:lista_cotizaciones')).content.decode()
        self.assertIn('id="notif-trigger"', html)
        self.assertIn('id="notif-badge"', html)
        self.assertIn('js/notificaciones.js', html)


@override_settings(ROOT_URLCONF='grupovicaf.urls_lab')
class MenuLateralTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        rol = rol_con_permisos('Recepción', 'muestras.ver', 'calendario.ver')
        cls.user, _ = crear_trabajador('recepcion', rol)

    def test_menu_a_la_izquierda_con_solo_los_modulos_permitidos(self):
        self.client.force_login(self.user)
        html = self.client.get(reverse('proyectos:lista_recepciones')).content.decode()
        self.assertIn('id="menu-lateral"', html)
        self.assertIn('id="menu-lateral-plegar"', html)
        self.assertNotIn('desktop-start-trigger', html)  # la burbuja ya no está
        inicio = html.index('id="menu-lateral"')
        fin = html.index('</aside>', inicio)
        menu = html[inicio:fin]
        self.assertIn(reverse('proyectos:lista_recepciones'), menu)
        self.assertIn(reverse('actividades:calendario_dashboard'), menu)
        self.assertNotIn(reverse('servicios:lista_cotizaciones'), menu)
        self.assertNotIn(reverse('trabajadores:lista_trabajadores'), menu)
