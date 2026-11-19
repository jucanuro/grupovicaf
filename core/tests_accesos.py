"""Contraseña temporal, «Cambiar mi contraseña» y comandos de accesos."""
import csv
import os
import tempfile
from io import StringIO

from django.contrib.auth import authenticate
from django.contrib.auth.models import User
from django.core.management import CommandError, call_command
from django.test import TestCase, override_settings
from django.urls import reverse

from correo.models import AccesoCuenta, CuentaCorreo
from trabajadores.models import TrabajadorProfile
from trabajadores.testing import crear_trabajador, rol_con_permisos

CLAVE_NUEVA = 'Una-clave-nueva-77'


@override_settings(ROOT_URLCONF='grupovicaf.urls_lab', SITE_ROLE='lab')
class CambiarClaveTests(TestCase):
    def setUp(self):
        rol = rol_con_permisos('Correo', 'correo.ver')
        self.user, self.perfil = crear_trabajador('anap', rol, 'Ana Pérez')
        self.user.set_password('temporal-1234')
        self.user.save()
        self.perfil.debe_cambiar_clave = True
        self.perfil.save()
        self.client.login(username='anap', password='temporal-1234')

    def test_con_clave_temporal_todo_redirige_a_cambiarla(self):
        r = self.client.get(reverse('administracion'))
        self.assertRedirects(r, reverse('cambiar_clave'), fetch_redirect_response=False)
        self.assertEqual(self.client.get(reverse('cambiar_clave')).status_code, 200)

    def test_cambiarla_libera_el_acceso(self):
        r = self.client.post(reverse('cambiar_clave'), {
            'old_password': 'temporal-1234', 'new_password1': CLAVE_NUEVA, 'new_password2': CLAVE_NUEVA})
        self.assertEqual(r.status_code, 302)
        self.perfil.refresh_from_db()
        self.assertFalse(self.perfil.debe_cambiar_clave)
        self.assertEqual(self.client.get(reverse('administracion')).status_code, 200)  # la sesión sigue activa
        self.assertIsNotNone(authenticate(username='anap', password=CLAVE_NUEVA))

    def test_no_acepta_la_misma_clave_ni_una_corta(self):
        for nueva in ('temporal-1234', 'corta1'):
            r = self.client.post(reverse('cambiar_clave'), {
                'old_password': 'temporal-1234', 'new_password1': nueva, 'new_password2': nueva})
            self.assertEqual(r.status_code, 200)
        self.perfil.refresh_from_db()
        self.assertTrue(self.perfil.debe_cambiar_clave)

    def test_requiere_sesion(self):
        self.client.logout()
        r = self.client.get(reverse('cambiar_clave'))
        self.assertEqual(r.status_code, 302)
        self.assertIn('/?next=', r['Location'])

    def test_usuario_normal_puede_cambiarla_cuando_quiera(self):
        self.perfil.debe_cambiar_clave = False
        self.perfil.save()
        self.assertEqual(self.client.get(reverse('cambiar_clave')).status_code, 200)
        self.assertEqual(self.client.get(reverse('administracion')).status_code, 200)


class ComandosAccesosTests(TestCase):
    def setUp(self):
        rol = rol_con_permisos('Correo', 'correo.ver')
        sin = rol_con_permisos('Técnico', 'ensayos.ver')
        self.ana, self.perfil_ana = crear_trabajador('anap', rol, 'Ana')
        self.luis, self.perfil_luis = crear_trabajador('luisp', sin, 'Luis')
        self.ana.email = 'ana@grupovicaf.com'
        self.ana.save()
        self.ya, _ = crear_trabajador('yaentro', rol, 'Ya Entró')
        User.objects.filter(pk=self.ya.pk).update(last_login='2026-11-01T10:00:00Z')
        self.cuenta = CuentaCorreo.objects.create(direccion='ana@grupovicaf.com', nombre='Ana', slug='ana')
        AccesoCuenta.objects.create(usuario=self.ana, cuenta=self.cuenta, rol='gestiona')
        self.dir = tempfile.mkdtemp(prefix='accesos-')
        self.csv = os.path.join(self.dir, 'cuentas.csv')
        with open(self.csv, 'w', encoding='utf-8') as f:
            f.write('direccion;nombre;accesos\n'
                    'ana@grupovicaf.com;Ana;anap:gestiona\n'
                    'luis@grupovicaf.com;Luis;luisp:gestiona\n'
                    'ya@grupovicaf.com;Ya;yaentro:gestiona\n'
                    'fantasma@grupovicaf.com;Fantasma;noexiste:gestiona\n')

    def correr(self, *args):
        salida = StringIO()
        call_command(*args, stdout=salida)
        return salida.getvalue()

    def test_verificar_marca_lo_que_falla(self):
        with self.assertRaises(CommandError):
            self.correr('verificar_accesos', self.csv)
        texto = StringIO()
        try:
            call_command('verificar_accesos', self.csv, stdout=texto)
        except CommandError:
            pass
        salida = texto.getvalue()
        self.assertIn('✔ anap', salida)
        self.assertIn('luisp', salida)
        self.assertIn('Correo ver', salida)
        self.assertIn('falta acceso a luis@grupovicaf.com', salida)
        self.assertIn('✘ noexiste: no existe', salida)

    def test_generar_sin_aplicar_no_cambia_nada(self):
        antes = User.objects.get(pk=self.ana.pk).password
        salida = os.path.join(self.dir, 'claves.csv')
        self.correr('generar_accesos', self.csv, '--salida', salida)
        self.assertEqual(User.objects.get(pk=self.ana.pk).password, antes)
        self.assertFalse(os.path.exists(salida))

    def test_generar_aplicando(self):
        salida = os.path.join(self.dir, 'claves.csv')
        texto = self.correr('generar_accesos', self.csv, '--salida', salida, '--aplicar')
        with open(salida, encoding='utf-8') as f:
            filas = list(csv.DictReader(f, delimiter=';'))
        usuarios = {f['usuario']: f['clave_temporal'] for f in filas}
        self.assertEqual(set(usuarios), {'anap', 'luisp'})  # yaentro ya inició sesión; noexiste no existe
        for clave in usuarios.values():
            self.assertNotIn(clave, texto)  # nunca se imprimen
        self.assertEqual(os.stat(salida).st_mode & 0o777, 0o600)
        self.assertIsNotNone(authenticate(username='anap', password=usuarios['anap']))
        self.perfil_ana.refresh_from_db()
        self.assertTrue(self.perfil_ana.debe_cambiar_clave)
        # no se sobrescribe un archivo existente
        with self.assertRaises(CommandError):
            self.correr('generar_accesos', self.csv, '--salida', salida, '--aplicar')

    def test_excluir_y_renombrar(self):
        salida = os.path.join(self.dir, 'claves.csv')
        self.correr('generar_accesos', self.csv, '--salida', salida, '--aplicar', '--excluir', 'anap')
        with open(salida, encoding='utf-8') as f:
            self.assertEqual([r['usuario'] for r in csv.DictReader(f, delimiter=';')], ['luisp'])
        self.correr('renombrar_usuario', 'luisp', 'luiso')
        self.assertTrue(User.objects.filter(username='luiso').exists())
        with self.assertRaises(CommandError):
            self.correr('renombrar_usuario', 'luiso', 'anap')
