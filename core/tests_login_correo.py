from django.contrib.auth import authenticate
from django.contrib.auth.models import User
from django.test import TestCase


class LoginPorCorreoTests(TestCase):
    def setUp(self):
        self.ana = User.objects.create_user('anap', 'ana.perez@grupovicaf.com', 'clave-segura-1')
        User.objects.create_user('compartido1', 'comun@grupovicaf.com', 'clave-segura-1')
        User.objects.create_user('compartido2', 'COMUN@grupovicaf.com', 'clave-segura-1')

    def entrar(self, usuario, clave='clave-segura-1'):
        return authenticate(username=usuario, password=clave)

    def test_entra_con_usuario(self):
        self.assertEqual(self.entrar('anap'), self.ana)

    def test_entra_con_correo_sin_importar_mayusculas(self):
        self.assertEqual(self.entrar('  ANA.Perez@grupovicaf.com '), self.ana)

    def test_clave_incorrecta_no_entra(self):
        self.assertIsNone(self.entrar('ana.perez@grupovicaf.com', 'otra'))

    def test_correo_compartido_no_entra_por_correo(self):
        self.assertIsNone(self.entrar('comun@grupovicaf.com'))
        self.assertIsNotNone(self.entrar('compartido1'))

    def test_usuario_inactivo_no_entra_por_correo(self):
        self.ana.is_active = False
        self.ana.save()
        self.assertIsNone(self.entrar('ana.perez@grupovicaf.com'))
