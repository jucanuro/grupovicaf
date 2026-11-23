"""Comando preparar_informe_prueba: deja una solicitud lista para abrir el editor."""
from io import StringIO

from django.core.management import CommandError, call_command
from django.test import override_settings
from django.urls import reverse

from proyectos.models import ResultadoEnsayo
from proyectos.test_compresion import CompresionBase
from trabajadores.testing import crear_trabajador, rol_con_permisos


class PrepararInformePruebaTests(CompresionBase):

    def test_solo_en_desarrollo(self):
        with override_settings(DEBUG=False), self.assertRaises(CommandError):
            call_command('preparar_informe_prueba', stdout=StringIO())
        self.assertFalse(ResultadoEnsayo.objects.filter(estado=ResultadoEnsayo.ESTADO_APROBADO).exists())

    @override_settings(DEBUG=True)
    def test_aprueba_todo_y_el_editor_abre(self):
        solicitud = self.mia.solicitud
        salida = StringIO()
        call_command('preparar_informe_prueba', '--solicitud', str(solicitud.pk), stdout=salida)
        url = reverse('proyectos:editor_informe', args=[solicitud.pk])
        self.assertIn(url, salida.getvalue())
        resultados = ResultadoEnsayo.objects.filter(detalle__solicitud=solicitud)
        self.assertEqual(resultados.count(), solicitud.detalles.count())
        self.assertFalse(resultados.exclude(estado=ResultadoEnsayo.ESTADO_APROBADO).exists())

        rol = rol_con_permisos('Jefe de laboratorio', 'informes.aprobar', 'informes.ver')
        user_jefe, _ = crear_trabajador('jefe', rol, 'Carla Jefa')
        self.client.force_login(user_jefe)
        self.assertEqual(self.client.get(url).status_code, 200)

    @override_settings(DEBUG=True)
    def test_solicitud_inexistente(self):
        with self.assertRaises(CommandError):
            call_command('preparar_informe_prueba', '--solicitud', '999999', stdout=StringIO())
