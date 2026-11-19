import tempfile
from io import StringIO
from pathlib import Path

from django.core.management import call_command

from .models import Mensaje
from .tests_plataforma import BasePlataforma


def eml(asunto, de, para, mid, cuerpo='hola'):
    return (f'From: {de}\r\nTo: {para}\r\nSubject: {asunto}\r\nMessage-ID: {mid}\r\n'
            f'Date: Mon, 10 Nov 2025 10:00:00 -0500\r\nContent-Type: text/plain; charset=utf-8\r\n\r\n{cuerpo}\r\n').encode()


class ImportarMaildirTests(BasePlataforma):
    def maildir(self):
        raiz = Path(tempfile.mkdtemp(prefix='maildir-'))
        for sub in ('cur', 'new', '.Sent/cur', '.Archivo viejo/cur'):
            (raiz / sub).mkdir(parents=True)
        (raiz / 'cur' / '1:2,S').write_bytes(eml('Entrada leída', 'c@cliente.example', 'informes@grupovicaf.com', '<a1@x>'))
        (raiz / 'new' / '2').write_bytes(eml('Entrada nueva', 'c@cliente.example', 'informes@grupovicaf.com', '<a2@x>'))
        (raiz / '.Sent' / 'cur' / '3:2,S').write_bytes(eml('Respuesta', 'informes@grupovicaf.com', 'c@cliente.example', '<a3@x>'))
        (raiz / '.Archivo viejo' / 'cur' / '4:2,S').write_bytes(eml('Viejo', 'c@cliente.example', 'informes@grupovicaf.com', '<a4@x>'))
        return str(raiz)

    def correr(self, *args):
        salida = StringIO()
        call_command('importar_maildir', *args, stdout=salida, stderr=StringIO())
        return salida.getvalue()

    def test_importa_carpetas_estados_y_es_idempotente(self):
        raiz = self.maildir()
        previos = Mensaje.objects.filter(cuenta=self.informes).count()  # el del escenario base
        self.correr('informes@grupovicaf.com', raiz)
        ms = Mensaje.objects.filter(cuenta=self.informes)
        self.assertEqual(ms.count(), previos + 4)
        self.assertTrue(ms.get(asunto='Entrada leída').leido)
        self.assertFalse(ms.get(asunto='Entrada nueva').leido)
        enviado = ms.get(asunto='Respuesta')
        self.assertEqual(enviado.carpeta.tipo, 'enviados')
        self.assertEqual(enviado.estado_envio, Mensaje.ENVIADO)
        self.assertEqual(ms.get(asunto='Viejo').carpeta.nombre, 'Archivo viejo')
        self.assertEqual(ms.get(asunto='Viejo').fecha.year, 2025)
        self.correr('informes@grupovicaf.com', raiz)
        self.assertEqual(Mensaje.objects.filter(cuenta=self.informes).count(), previos + 4)

    def test_simular_no_guarda(self):
        previos = Mensaje.objects.filter(cuenta=self.informes).count()
        self.correr('informes@grupovicaf.com', self.maildir(), '--simular')
        self.assertEqual(Mensaje.objects.filter(cuenta=self.informes).count(), previos)


class CargarCuentasTests(BasePlataforma):
    def csv(self, texto):
        ruta = Path(tempfile.mkdtemp(prefix='cuentas-')) / 'c.csv'
        ruta.write_text(texto, encoding='utf-8')
        return str(ruta)

    def test_crea_cuentas_y_accesos_sin_duplicar(self):
        from .models import AccesoCuenta, CuentaCorreo
        self.jefe.is_superuser = True
        self.jefe.save()
        ruta = self.csv('direccion;nombre;accesos\nventas@grupovicaf.com;Ventas;gestor:gestiona,lector:lectura\n')
        for _ in range(2):
            call_command('cargar_cuentas', ruta, '--actor', 'jefe', stdout=StringIO())
        cuenta = CuentaCorreo.objects.get(direccion='ventas@grupovicaf.com')
        self.assertEqual(CuentaCorreo.objects.filter(direccion='ventas@grupovicaf.com').count(), 1)
        self.assertEqual(AccesoCuenta.objects.get(cuenta=cuenta, usuario=self.gestor).rol, 'gestiona')
        self.assertEqual(AccesoCuenta.objects.get(cuenta=cuenta, usuario=self.lector).rol, 'lectura')
        self.assertEqual(AccesoCuenta.objects.get(cuenta=cuenta, usuario=self.jefe).rol, 'administra')
