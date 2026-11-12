"""Diseño tipo Outlook (T29): barra de comandos, lista agrupada y redactar en el panel."""
from datetime import timedelta

from django.test import SimpleTestCase, override_settings
from django.utils import timezone

from .mensajeria import crear_mensaje
from .models import Mensaje
from .templatetags.correo_tags import grupo_fecha, icono_carpeta
from .tests_plataforma import HOST, BasePlataforma, ruta


@override_settings(ROOT_URLCONF='grupovicaf.urls_lab', SITE_ROLE='lab')
class ComandosTests(BasePlataforma):
    def accion(self, usuario, **datos):
        self.entrar(usuario)
        volver = ruta('bandeja_cuenta', 'informes') + f'?h={self.m.hilo_id}'
        datos.setdefault('origen', 'entrada')
        return self.client.post(ruta('acciones'), {'volver': volver, **datos}, HTTP_HOST=HOST)

    def test_sin_seleccion_actua_sobre_el_hilo_abierto(self):
        respuesta = self.accion(self.gestor, accion='archivar', hilo_abierto=self.m.hilo_id)
        self.m.refresh_from_db()
        self.assertEqual(self.m.carpeta.tipo, 'archivados')
        self.assertNotIn('?h=', respuesta['Location'])

    def test_hilo_abierto_ajeno_no_hace_nada(self):
        self.accion(self.ajeno, accion='eliminar', hilo_abierto=self.m.hilo_id)
        self.m.refresh_from_db()
        self.assertEqual(self.m.carpeta.tipo, 'entrada')

    def test_las_casillas_marcadas_tienen_prioridad(self):
        otro = crear_mensaje(self.informes, 'entrada', de='x@y.example', asunto='Otro asunto', html='<p>x</p>')
        self.accion(self.gestor, accion='archivar', hilos=otro.hilo_id, hilo_abierto=self.m.hilo_id)
        self.m.refresh_from_db()
        otro.refresh_from_db()
        self.assertEqual(self.m.carpeta.tipo, 'entrada')
        self.assertEqual(otro.carpeta.tipo, 'archivados')

    def test_no_leido_cierra_el_hilo_para_que_quede_no_leido(self):
        respuesta = self.accion(self.gestor, accion='no_leido', hilo_abierto=self.m.hilo_id)
        self.assertNotIn('?h=', respuesta['Location'])
        self.m.refresh_from_db()
        self.assertFalse(self.m.leido)

    def test_la_bandeja_muestra_la_barra_y_mover_a(self):
        self.entrar(self.gestor)
        respuesta = self.client.get(ruta('bandeja_cuenta', 'informes'), {'h': self.m.hilo_id}, HTTP_HOST=HOST)
        self.assertContains(respuesta, 'aria-label="Acciones de correo"')
        self.assertContains(respuesta, 'name="hilo_abierto"')
        self.assertContains(respuesta, 'value="mover:')
        self.assertContains(respuesta, 'class="filas__grupo"')


@override_settings(ROOT_URLCONF='grupovicaf.urls_lab', SITE_ROLE='lab')
class RedactarEnPanelTests(BasePlataforma):
    def test_redactar_muestra_la_lista_de_la_cuenta(self):
        self.entrar(self.gestor)
        respuesta = self.client.get(ruta('redactar'), {'cuenta': 'informes'}, HTTP_HOST=HOST, follow=True)
        self.assertContains(respuesta, 'id="form-redactar"')
        self.assertContains(respuesta, 'Cotización de compresión de probetas')  # la lista sigue a la izquierda
        self.assertNotContains(respuesta, 'Resultados del Proctor')  # pero solo de esta cuenta
        self.assertNotContains(respuesta, 'app--completo')

    def test_pantalla_completa(self):
        self.entrar(self.gestor)
        self.client.get(ruta('redactar'), {'cuenta': 'informes'}, HTTP_HOST=HOST)
        b = Mensaje.objects.get(estado_envio=Mensaje.BORRADOR)
        respuesta = self.client.get(ruta('borrador', b.pk), {'completo': '1'}, HTTP_HOST=HOST)
        self.assertContains(respuesta, 'app--completo')


class FiltrosTests(SimpleTestCase):
    def test_grupo_fecha(self):
        ahora = timezone.now()
        self.assertEqual(grupo_fecha(ahora), 'Hoy')
        self.assertEqual(grupo_fecha(ahora - timedelta(days=1)), 'Ayer')
        self.assertEqual(grupo_fecha(ahora - timedelta(days=3)), 'Esta semana')
        self.assertEqual(grupo_fecha(ahora - timedelta(days=9)), 'La semana pasada')
        self.assertEqual(grupo_fecha(ahora - timedelta(days=800)), str(timezone.localtime(ahora - timedelta(days=800)).year))

    def test_icono_carpeta(self):
        self.assertEqual(icono_carpeta('papelera'), 'papelera')
        self.assertEqual(icono_carpeta('personal'), 'carpeta')
