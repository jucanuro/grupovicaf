"""Borradores: cada quien ve y abre los suyos; quien administra la cuenta ve todos."""
from django.contrib.auth.models import Permission  # noqa: F401  (lo usa BasePlataforma)

from .models import Mensaje
from .mensajeria import crear_mensaje, nuevo_message_id
from .tests_plataforma import BasePlataforma


class BorradoresAjenosTests(BasePlataforma):
    def setUp(self):
        super().setUp()
        self.de_jefe = crear_mensaje(
            self.informes, 'borradores', de=self.informes.direccion, de_nombre='Informes', para=[],
            asunto='Borrador del jefe', html='<p>x</p>', estado=Mensaje.BORRADOR, creado_por=self.jefe,
            message_id=nuevo_message_id(self.informes), leido=True)
        self.de_gina = crear_mensaje(
            self.informes, 'borradores', de=self.informes.direccion, de_nombre='Informes', para=[],
            asunto='Borrador de Gina', html='<p>x</p>', estado=Mensaje.BORRADOR, creado_por=self.gestor,
            message_id=nuevo_message_id(self.informes), leido=True)

    def _lista(self, usuario):
        from .models import Carpeta
        self.entrar(usuario)
        carpeta = Carpeta.objects.get(cuenta=self.informes, tipo='borradores')
        return self.get('carpeta', 'informes', carpeta.pk)

    def test_quien_gestiona_ve_solo_sus_borradores(self):
        r = self._lista(self.gestor)
        self.assertContains(r, 'Borrador de Gina')
        self.assertNotContains(r, 'Borrador del jefe')

    def test_quien_administra_ve_todos(self):
        r = self._lista(self.jefe)
        self.assertContains(r, 'Borrador de Gina')
        self.assertContains(r, 'Borrador del jefe')

    def test_abrir_el_borrador_de_otra_persona_explica_el_motivo(self):
        self.entrar(self.gestor)
        r = self.get('borrador', self.de_jefe.pk)
        self.assertEqual(r.status_code, 403)
        self.assertContains(r, 'Este borrador es de otra persona', status_code=403)
