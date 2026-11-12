"""Paso 3: archivos en R2 (bucket privado, URL prefirmada de 300 s) y la
pantalla «Administrar cuentas» con su bitácora.

Las pruebas de que nadie ve ni descarga correo de una cuenta no asignada
(404, enlaces vencidos) están en tests_plataforma.PermisosTests y AdjuntosTests;
aquí se suman las del almacenamiento en R2 y las de administración.
"""
from unittest import mock

from django.contrib.auth.models import User
from django.core.exceptions import ImproperlyConfigured
from django.test import SimpleTestCase, override_settings

from trabajadores.testing import crear_trabajador, rol_con_permisos

from . import almacen
from .enlaces import url_adjunto
from .models import AccesoCuenta, Carpeta, CuentaCorreo, EventoCuenta
from .tests_plataforma import HOST, BasePlataforma, ruta

R2 = dict(CORREO_ALMACEN='r2', CORREO_R2_BUCKET='vicaf-correo', CORREO_R2_ENDPOINT='https://abc.r2.cloudflarestorage.com',
          CORREO_R2_ACCESS_KEY='clave', CORREO_R2_SECRET_KEY='secreto', CORREO_URL_FIRMADA_SEGUNDOS=300)


class AlmacenR2Tests(SimpleTestCase):
    def test_por_defecto_es_local(self):
        self.assertFalse(almacen.es_r2())

    @override_settings(CORREO_ALMACEN='r2', CORREO_R2_BUCKET='', CORREO_R2_ENDPOINT='',
                       CORREO_R2_ACCESS_KEY='', CORREO_R2_SECRET_KEY='')
    def test_r2_sin_credenciales_falla_claro(self):
        with self.assertRaisesMessage(ImproperlyConfigured, 'CORREO_R2_BUCKET'):
            almacen.crear_almacen_r2()

    @override_settings(**R2)
    def test_bucket_privado_con_urls_firmadas_de_300_s(self):
        s3 = almacen.crear_almacen_r2()
        self.assertEqual(s3.bucket_name, 'vicaf-correo')
        self.assertEqual(s3.endpoint_url, 'https://abc.r2.cloudflarestorage.com')
        self.assertIsNone(s3.default_acl)
        self.assertTrue(s3.querystring_auth)
        self.assertEqual(s3.querystring_expire, 300)
        self.assertFalse(s3.file_overwrite)
        self.assertIsNone(s3.custom_domain)

    @override_settings(**R2)
    def test_url_prefirmada_real_vence_y_fuerza_descarga(self):
        s3 = almacen.crear_almacen_r2()
        with mock.patch.object(almacen, 'almacen_correo', s3):
            url = almacen.url_prefirmada('adjuntos/2026/11/x.pdf', descarga='Cotización 1.pdf', tipo='application/pdf')
        self.assertTrue(url.startswith('https://abc.r2.cloudflarestorage.com/vicaf-correo/adjuntos/2026/11/x.pdf?'))
        self.assertIn('X-Amz-Expires=300', url)
        self.assertIn('X-Amz-Signature=', url)
        self.assertIn('response-content-disposition=attachment', url)
        self.assertNotIn('secreto', url)


class _AlmacenFalso:
    """Imita S3Storage.url sin red; abre los archivos desde el almacén temporal de las pruebas."""

    def __init__(self, real):
        self.real, self.pedidas = real, []

    def url(self, nombre, parameters=None, expire=None):
        self.pedidas.append((nombre, parameters, expire))
        return f'https://r2.example/{nombre}?firma=1'

    def __getattr__(self, nombre):
        return getattr(self.real, nombre)


@override_settings(ROOT_URLCONF='grupovicaf.urls_lab', SITE_ROLE='lab', **R2)
class DescargaR2Tests(BasePlataforma):
    def test_adjunto_redirige_a_url_prefirmada_sin_pasar_por_el_servidor(self):
        adjunto = self.m.adjuntos.get()
        falso = _AlmacenFalso(almacen.almacen_correo._wrapped)
        with mock.patch.object(almacen, 'almacen_correo', falso):
            respuesta = self.client.get(url_adjunto(adjunto), HTTP_HOST=HOST)
        self.assertEqual(respuesta.status_code, 302)
        self.assertTrue(respuesta['Location'].startswith('https://r2.example/'))
        self.assertIn('no-store', respuesta['Cache-Control'])
        nombre, parametros, vence = falso.pedidas[0]
        self.assertEqual(nombre, adjunto.archivo.name)
        self.assertEqual(vence, 300)
        self.assertEqual(parametros['ResponseContentDisposition'], "attachment; filename*=UTF-8''planos.pdf")

    def test_imagen_incrustada_sigue_por_el_servidor(self):
        from .mensajeria import agregar_adjunto
        imagen = agregar_adjunto(self.m, 'logo.png', 'image/png', b'\x89PNG\r\n', content_id='logo@x', incrustado=True)
        respuesta = self.client.get(url_adjunto(imagen), HTTP_HOST=HOST)
        self.assertEqual(respuesta.status_code, 200)

    def test_enlace_vencido_no_llega_a_r2(self):
        respuesta = self.client.get(ruta('adjunto', 'token-falso'), HTTP_HOST=HOST)
        self.assertEqual(respuesta.status_code, 404)


@override_settings(ROOT_URLCONF='grupovicaf.urls_lab', SITE_ROLE='lab')
class AdministrarTests(BasePlataforma):
    def setUp(self):
        super().setUp()
        rol_admin = rol_con_permisos('Administración del correo', 'correo.ver', 'correo.administrar')
        self.admin, _ = crear_trabajador('admin_correo', rol_admin, 'Ada Admin')
        self.portal = User.objects.create_user('cliente_portal', password='x')

    def get(self, _vista, *args, **params):
        return self.client.get(ruta(_vista, *args), params, HTTP_HOST=HOST)

    def test_sin_administrar_nada_es_403(self):
        self.entrar(self.gestor)
        self.assertEqual(self.get('admin_cuentas').status_code, 403)
        self.assertNotContains(self.get('bandeja'), 'Administrar cuentas')

    def test_admin_del_correo_ve_todas_las_cuentas(self):
        self.entrar(self.admin)
        respuesta = self.get('admin_cuentas')
        self.assertContains(respuesta, 'informes@grupovicaf.com')
        self.assertContains(respuesta, 'laboratorio@grupovicaf.com')
        self.assertContains(respuesta, 'Nueva cuenta')

    def test_quien_administra_una_cuenta_solo_ve_esa(self):
        self.entrar(self.jefe)  # administra «informes»
        respuesta = self.get('admin_cuentas')
        self.assertContains(respuesta, 'informes@grupovicaf.com')
        self.assertNotContains(respuesta, 'laboratorio@grupovicaf.com')
        self.assertNotContains(respuesta, 'Nueva cuenta')
        self.assertEqual(self.get('admin_cuenta', 'laboratorio').status_code, 404)

    def test_crear_cuenta_con_carpetas_acceso_y_bitacora(self):
        self.entrar(self.admin)
        respuesta = self.post('admin_cuenta_crear', direccion='Ventas@GrupoVicaf.com', nombre='Ventas', darme_acceso='1')
        cuenta = CuentaCorreo.objects.get(direccion='ventas@grupovicaf.com')
        self.assertRedirects(respuesta, ruta('admin_cuenta', cuenta.slug), fetch_redirect_response=False)
        self.assertEqual(cuenta.slug, 'ventas')
        self.assertTrue(Carpeta.objects.filter(cuenta=cuenta, tipo='entrada').exists())
        self.assertEqual(AccesoCuenta.objects.get(cuenta=cuenta, usuario=self.admin).rol, AccesoCuenta.ADMINISTRA)
        self.assertEqual(list(cuenta.bitacora.values_list('tipo', flat=True)),
                         [EventoCuenta.DIO_ACCESO, EventoCuenta.CREO])
        self.assertEqual(cuenta.bitacora.last().usuario, self.admin)

    def test_solo_el_dominio_de_la_empresa_y_sin_duplicados(self):
        self.entrar(self.admin)
        self.post('admin_cuenta_crear', direccion='ventas@gmail.com', nombre='X')
        self.post('admin_cuenta_crear', direccion='informes@grupovicaf.com', nombre='X')
        self.assertEqual(CuentaCorreo.objects.count(), 2)

    def test_quien_solo_administra_una_cuenta_no_crea_cuentas(self):
        self.entrar(self.jefe)
        self.assertEqual(self.post('admin_cuenta_crear', direccion='nueva@grupovicaf.com').status_code, 403)
        self.assertFalse(CuentaCorreo.objects.filter(direccion='nueva@grupovicaf.com').exists())

    def test_dar_cambiar_y_quitar_acceso_queda_en_la_bitacora(self):
        self.entrar(self.jefe)
        self.post('admin_acceso_dar', 'informes', usuario=self.ajeno.pk, rol='lectura')
        acceso = AccesoCuenta.objects.get(cuenta=self.informes, usuario=self.ajeno)
        self.assertEqual(acceso.rol, 'lectura')
        self.post('admin_acceso_rol', 'informes', acceso.pk, rol='gestiona')
        acceso.refresh_from_db()
        self.assertEqual(acceso.rol, 'gestiona')
        self.post('admin_acceso_quitar', 'informes', acceso.pk)
        self.assertFalse(AccesoCuenta.objects.filter(pk=acceso.pk).exists())
        tipos = list(self.informes.bitacora.values_list('tipo', flat=True))
        self.assertEqual(tipos, [EventoCuenta.QUITO_ACCESO, EventoCuenta.CAMBIO_ROL, EventoCuenta.DIO_ACCESO])
        self.assertTrue(all(e.usuario == self.jefe for e in self.informes.bitacora.all()))

    def test_no_se_da_acceso_a_usuarios_del_portal(self):
        self.entrar(self.admin)
        self.post('admin_acceso_dar', 'informes', usuario=self.portal.pk, rol='lectura')
        self.assertFalse(AccesoCuenta.objects.filter(usuario=self.portal).exists())

    def test_no_se_toca_un_acceso_de_otra_cuenta(self):
        self.entrar(self.jefe)
        ajeno = AccesoCuenta.objects.get(cuenta=self.lab, usuario=self.ajeno)
        self.assertEqual(self.post('admin_acceso_quitar', 'informes', ajeno.pk).status_code, 404)
        self.assertEqual(self.post('admin_acceso_quitar', 'laboratorio', ajeno.pk).status_code, 404)
        self.assertTrue(AccesoCuenta.objects.filter(pk=ajeno.pk).exists())

    def test_la_cuenta_no_se_queda_sin_administrador(self):
        self.entrar(self.jefe)
        propio = AccesoCuenta.objects.get(cuenta=self.informes, usuario=self.jefe)
        self.post('admin_acceso_rol', 'informes', propio.pk, rol='lectura')
        self.post('admin_acceso_quitar', 'informes', propio.pk)
        propio.refresh_from_db()
        self.assertEqual(propio.rol, AccesoCuenta.ADMINISTRA)

    def test_solo_el_admin_del_correo_desactiva(self):
        self.entrar(self.jefe)
        self.assertEqual(self.post('admin_cuenta_guardar', 'informes', nombre='Informes', activa='0').status_code, 403)
        self.informes.refresh_from_db()
        self.assertTrue(self.informes.activa)
        self.entrar(self.admin)
        self.post('admin_cuenta_guardar', 'informes', nombre='Informes VICAF', activa='0')
        self.informes.refresh_from_db()
        self.assertFalse(self.informes.activa)
        self.assertEqual(self.informes.nombre, 'Informes VICAF')
        self.entrar(self.gestor)
        self.assertEqual(self.get('bandeja_cuenta', 'informes').status_code, 404)

    def test_administrar_no_da_acceso_a_leer(self):
        self.entrar(self.admin)
        self.assertEqual(self.get('bandeja_cuenta', 'informes').status_code, 404)
        self.assertEqual(self.get('mensaje', self.m.pk).status_code, 404)

    def test_avisa_si_falta_el_permiso_correo_en_el_rol(self):
        sin_correo, _ = crear_trabajador('tecnico', rol_con_permisos('Técnico lab', 'ensayos.ver'))
        self.entrar(self.admin)
        self.post('admin_acceso_dar', 'informes', usuario=sin_correo.pk, rol='lectura')
        self.assertContains(self.get('admin_cuenta', 'informes'), 'Sin permiso Correo en su rol')
