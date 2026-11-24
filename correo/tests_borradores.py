"""Borradores de una cuenta compartida: los ve y edita quien gestiona la cuenta."""
from .mensajeria import crear_mensaje, nuevo_message_id
from .models import Carpeta, Mensaje
from .tests_plataforma import BasePlataforma


class BorradoresCompartidosTests(BasePlataforma):
    def setUp(self):
        super().setUp()
        self.de_jefe = crear_mensaje(
            self.informes, 'borradores', de=self.informes.direccion, de_nombre='Informes', para=[],
            asunto='Borrador del jefe', html='<p>x</p>', estado=Mensaje.BORRADOR, creado_por=self.jefe,
            message_id=nuevo_message_id(self.informes), leido=True)

    def test_quien_gestiona_ve_y_abre_los_borradores_de_la_cuenta(self):
        self.entrar(self.gestor)
        carpeta = Carpeta.objects.get(cuenta=self.informes, tipo='borradores')
        self.assertContains(self.get('carpeta', 'informes', carpeta.pk), 'Borrador del jefe')
        self.assertEqual(self.get('borrador', self.de_jefe.pk).status_code, 200)

    def test_quien_solo_lee_no_puede_abrirlos_y_se_le_explica(self):
        self.entrar(self.lector)
        r = self.get('borrador', self.de_jefe.pk)
        self.assertEqual(r.status_code, 403)
        self.assertContains(r, 'Tu rol en esta cuenta no permite esta acción', status_code=403)

    def test_quien_no_tiene_la_cuenta_no_ve_ni_que_existe(self):
        self.entrar(self.ajeno)
        self.assertEqual(self.get('borrador', self.de_jefe.pk).status_code, 404)
