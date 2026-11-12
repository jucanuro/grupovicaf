"""Paso 1 del módulo de correo: pantalla de entrada, ruteo por host y
enlace firmado entre laboratorio. y email. (VCF-LIMS)."""
from unittest import mock
from urllib.parse import parse_qs, urlsplit

from django.contrib.auth.models import User
from django.core import signing
from django.core.cache import cache
from django.test import TestCase, override_settings
from django.urls import reverse

from trabajadores.models import PermisoModulo
from trabajadores.testing import crear_trabajador, rol_con_permisos

from .enlaces import SALT, crear_enlace, destino_seguro
from .middleware import URLCONF_CORREO

HOST_CORREO = 'email.localhost'
HOST_LAB = 'localhost'


def ruta_correo(nombre, *args):
    return reverse(nombre, urlconf=URLCONF_CORREO, args=args)


# El correo vive en el rol 'lab': fija su URLconf y su rol aunque la suite
# corra con SITE_ROLE=web (job del CI).
@override_settings(ROOT_URLCONF='grupovicaf.urls_lab', SITE_ROLE='lab')
class BaseCorreo(TestCase):
    def setUp(self):
        cache.clear()
        self.rol_ambos = rol_con_permisos('Coordinación', 'correo.ver', 'cotizaciones.ver')
        self.rol_solo_lims = rol_con_permisos('Técnico', 'ensayos.ver')
        self.rol_solo_correo = rol_con_permisos('Recepción de correo', 'correo.ver')
        self.rol_vacio = rol_con_permisos('Sin módulos')
        self.ambos, _ = crear_trabajador('ambos', self.rol_ambos, 'Ana Torres')
        self.solo_lims, _ = crear_trabajador('solo_lims', self.rol_solo_lims)
        self.solo_correo, _ = crear_trabajador('solo_correo', self.rol_solo_correo)
        self.vacio, _ = crear_trabajador('vacio', self.rol_vacio)

    def get_correo(self, ruta, **kwargs):
        return self.client.get(ruta, HTTP_HOST=HOST_CORREO, **kwargs)

    def enlace_desde_lab(self, user, **query):
        """Pide /correo/abrir/ en el LIMS y devuelve la URL a la que redirige."""
        self.client.force_login(user)
        respuesta = self.client.get(reverse('correo:abrir'), query, HTTP_HOST=HOST_LAB)
        self.assertEqual(respuesta.status_code, 302)
        self.client.logout()
        return respuesta['Location']


class MigracionPermisoTests(TestCase):
    def test_existe_correo_ver(self):
        self.assertTrue(PermisoModulo.objects.filter(codigo='correo.ver').exists())


class LoginTests(BaseCorreo):
    def test_tras_el_login_va_a_la_pantalla_de_entrada(self):
        respuesta = self.client.post(reverse('login'), {'username': 'ambos', 'password': 'x'})
        self.assertRedirects(respuesta, reverse('inicio'), fetch_redirect_response=False)

    def test_respeta_next(self):
        respuesta = self.client.post(
            reverse('login') + '?next=/dashboard/', {'username': 'ambos', 'password': 'x', 'next': '/dashboard/'},
        )
        self.assertRedirects(respuesta, '/dashboard/', fetch_redirect_response=False)


class PantallaEntradaTests(BaseCorreo):
    def entrada(self, user):
        self.client.force_login(user)
        return self.client.get(reverse('inicio'), HTTP_HOST=HOST_LAB)

    def test_sin_sesion_pide_login(self):
        respuesta = self.client.get(reverse('inicio'))
        self.assertEqual(respuesta.status_code, 302)
        self.assertIn(reverse('login'), respuesta['Location'])

    def test_con_ambos_permisos_ve_las_dos_tarjetas(self):
        html = self.entrada(self.ambos).content.decode()
        self.assertIn('data-tarjeta="correos"', html)
        self.assertIn('data-tarjeta="sistema"', html)
        self.assertIn('informes@grupovicaf.com', html)
        self.assertIn('Hola, Ana', html)

    def test_cada_tarjeta_y_cada_cuenta_abren_en_pestana_nueva(self):
        respuesta = self.entrada(self.ambos)
        html = respuesta.content.decode()
        self.assertContains(respuesta, f'href="{reverse("dashboard")}" target="_blank" rel="noopener"')
        self.assertContains(respuesta, f'href="{reverse("correo:abrir")}" target="_blank" rel="noopener"')
        for slug in ('informes', 'laboratorio', 'quejas'):
            self.assertIn(f'href="{reverse("correo:abrir")}?cuenta={slug}" target="_blank" rel="noopener"', html)

    def test_solo_lims_ve_solo_sistema(self):
        html = self.entrada(self.solo_lims).content.decode()
        self.assertNotIn('data-tarjeta="correos"', html)
        self.assertIn('data-tarjeta="sistema"', html)

    def test_solo_correo_ve_solo_correos(self):
        html = self.entrada(self.solo_correo).content.decode()
        self.assertIn('data-tarjeta="correos"', html)
        self.assertNotIn('data-tarjeta="sistema"', html)

    def test_sin_modulos_ve_aviso(self):
        html = self.entrada(self.vacio).content.decode()
        self.assertNotIn('data-tarjeta=', html)
        self.assertIn('no tiene módulos asignados', html)

    def test_superusuario_ve_ambas(self):
        admin = User.objects.create_superuser('admin', password='x')
        html = self.entrada(admin).content.decode()
        self.assertIn('data-tarjeta="correos"', html)
        self.assertIn('data-tarjeta="sistema"', html)

    @override_settings(CORREO_OMITIR_ENTRADA=True)
    def test_ajuste_omitir_con_un_solo_modulo(self):
        self.assertRedirects(self.entrada(self.solo_lims), reverse('dashboard'), fetch_redirect_response=False)
        self.assertRedirects(self.entrada(self.solo_correo), reverse('correo:abrir'), fetch_redirect_response=False)
        self.assertEqual(self.entrada(self.ambos).status_code, 200)

    def test_por_defecto_no_omite(self):
        self.assertEqual(self.entrada(self.solo_lims).status_code, 200)


class RuteoPorHostTests(BaseCorreo):
    def test_host_del_lims_sigue_igual(self):
        self.client.force_login(self.ambos)
        self.assertEqual(self.client.get('/dashboard/', HTTP_HOST=HOST_LAB).status_code, 200)

    def test_host_del_correo_no_expone_el_lims(self):
        self.client.force_login(self.ambos)
        for ruta in ('/dashboard/', '/admin/', '/clientes/', '/inicio/'):
            self.assertEqual(self.get_correo(ruta).status_code, 404, ruta)

    def test_host_del_correo_lleva_csp_estricta(self):
        respuesta = self.get_correo(ruta_correo('login'))
        self.assertIn("script-src 'self'", respuesta['Content-Security-Policy'])
        self.assertIn("frame-ancestors 'none'", respuesta['Content-Security-Policy'])
        self.assertEqual(respuesta['Referrer-Policy'], 'no-referrer')

    def test_host_del_lims_sin_csp_del_correo(self):
        respuesta = self.client.get(reverse('login'), HTTP_HOST=HOST_LAB)
        self.assertNotIn('Content-Security-Policy', respuesta)

    @override_settings(SITE_ROLE='web')
    def test_rol_web_ignora_el_host_del_correo(self):
        respuesta = self.client.get('/', HTTP_HOST=HOST_CORREO)
        self.assertNotIn('Content-Security-Policy', respuesta)


class EnlaceFirmadoTests(BaseCorreo):
    def test_abrir_sin_permiso_correo_es_403(self):
        self.client.force_login(self.solo_lims)
        self.assertEqual(self.client.get(reverse('correo:abrir')).status_code, 403)

    def test_abrir_cuenta_inexistente_es_404(self):
        self.client.force_login(self.ambos)
        self.assertEqual(self.client.get(reverse('correo:abrir'), {'cuenta': 'otra'}).status_code, 404)

    def test_abrir_redirige_al_host_del_correo_con_enlace(self):
        url = urlsplit(self.enlace_desde_lab(self.ambos, cuenta='informes'))
        self.assertEqual(url.hostname, HOST_CORREO)
        self.assertEqual(url.path, ruta_correo('entrar'))
        self.assertIn('t', parse_qs(url.query))

    @override_settings(CORREO_BASE_URL='https://email.grupovicaf.com')
    def test_usa_la_url_base_configurada(self):
        self.assertTrue(self.enlace_desde_lab(self.ambos).startswith('https://email.grupovicaf.com/entrar/?t='))

    def test_enlace_abre_sesion_y_lleva_a_la_cuenta(self):
        url = urlsplit(self.enlace_desde_lab(self.ambos, cuenta='informes'))
        respuesta = self.get_correo(f'{url.path}?{url.query}')
        self.assertRedirects(respuesta, ruta_correo('bandeja_cuenta', 'informes'), fetch_redirect_response=False)
        bandeja = self.get_correo(ruta_correo('bandeja_cuenta', 'informes'))
        self.assertEqual(bandeja.status_code, 200)
        self.assertContains(bandeja, 'informes@grupovicaf.com')

    def test_enlace_es_de_un_solo_uso(self):
        url = urlsplit(self.enlace_desde_lab(self.ambos))
        self.assertEqual(self.get_correo(f'{url.path}?{url.query}').status_code, 302)
        self.client.logout()
        self.assertEqual(self.get_correo(f'{url.path}?{url.query}').status_code, 400)

    def test_enlace_vencido_no_sirve(self):
        token = crear_enlace(self.ambos)
        with mock.patch('django.core.signing.time.time', return_value=10**10):
            respuesta = self.get_correo(ruta_correo('entrar'), data={'t': token})
        self.assertEqual(respuesta.status_code, 400)

    def test_enlace_alterado_no_sirve(self):
        token = crear_enlace(self.ambos)
        self.assertEqual(self.get_correo(ruta_correo('entrar'), data={'t': token[:-2] + 'xx'}).status_code, 400)

    def test_enlace_firmado_con_otro_salt_no_sirve(self):
        token = signing.dumps({'u': self.ambos.pk, 'n': 'x', 'd': '/'}, salt='otro')
        self.assertEqual(self.get_correo(ruta_correo('entrar'), data={'t': token}).status_code, 400)

    def test_enlace_de_usuario_sin_permiso_es_403(self):
        token = signing.dumps({'u': self.solo_lims.pk, 'n': 'y', 'd': '/'}, salt=SALT)
        self.assertEqual(self.get_correo(ruta_correo('entrar'), data={'t': token}).status_code, 403)

    def test_enlace_de_usuario_inactivo_es_403(self):
        token = crear_enlace(self.ambos)
        self.ambos.is_active = False
        self.ambos.save()
        self.assertEqual(self.get_correo(ruta_correo('entrar'), data={'t': token}).status_code, 403)

    def test_destino_externo_se_descarta(self):
        token = signing.dumps({'u': self.ambos.pk, 'n': 'z', 'd': '//evil.example/x'}, salt=SALT)
        respuesta = self.get_correo(ruta_correo('entrar'), data={'t': token})
        self.assertRedirects(respuesta, '/', fetch_redirect_response=False)

    def test_destino_seguro(self):
        for malo in ('https://evil.example/', '//evil.example', '/\\evil.example', 'javascript:alert(1)', '', None):
            self.assertEqual(destino_seguro(malo), '/', malo)
        self.assertEqual(destino_seguro('/c/informes/bandeja/'), '/c/informes/bandeja/')


class HostCorreoTests(BaseCorreo):
    def test_sin_sesion_manda_al_login_del_lims(self):
        respuesta = self.get_correo(ruta_correo('bandeja_cuenta', 'informes'))
        self.assertRedirects(
            respuesta, ruta_correo('login') + '?next=/c/informes/bandeja/', fetch_redirect_response=False,
        )
        login = self.get_correo(respuesta['Location'])
        destino = urlsplit(login['Location'])
        self.assertEqual(destino.hostname, HOST_LAB)
        self.assertEqual(destino.path, reverse('correo:abrir'))
        self.assertEqual(parse_qs(destino.query)['next'], ['/c/informes/bandeja/'])

    def test_sesion_del_lims_no_vale_en_el_correo(self):
        """Las cookies son por host: force_login en el cliente de pruebas no
        distingue hosts, así que se comprueba que la sesión del correo exige
        además el permiso, no solo estar autenticado."""
        self.client.force_login(self.solo_lims)
        self.assertEqual(self.get_correo(ruta_correo('bandeja')).status_code, 403)

    def test_cuenta_ajena_es_404(self):
        self.client.force_login(self.ambos)
        self.assertEqual(self.get_correo(ruta_correo('bandeja_cuenta', 'no-existe')).status_code, 404)

    def test_bandeja_unificada_lista_las_cuentas(self):
        self.client.force_login(self.ambos)
        respuesta = self.get_correo(ruta_correo('bandeja'))
        self.assertContains(respuesta, 'Bandeja unificada')
        for direccion in ('Informes y cotizaciones', 'Laboratorio', 'Quejas y reportes'):
            self.assertContains(respuesta, direccion)

    def test_salir_cierra_la_sesion_del_correo(self):
        self.client.force_login(self.ambos)
        respuesta = self.client.post(ruta_correo('salir'), HTTP_HOST=HOST_CORREO)
        self.assertEqual(urlsplit(respuesta['Location']).hostname, HOST_LAB)
        self.assertEqual(self.get_correo(ruta_correo('bandeja')).status_code, 302)

    def test_salir_solo_por_post(self):
        self.client.force_login(self.ambos)
        self.assertEqual(self.get_correo(ruta_correo('salir')).status_code, 405)
