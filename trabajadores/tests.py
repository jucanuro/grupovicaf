import importlib

from django.apps import apps
from django.test import TestCase

from .models import PermisoModulo
from .testing import rol_con_permisos

migracion_ver_todos = importlib.import_module('trabajadores.migrations.0007_permiso_ensayos_ver_todos')


class PermisoEnsayosVerTodosMigracionTests(TestCase):
    def test_lo_reciben_los_roles_que_ven_ensayos_salvo_tecnicos(self):
        supervisor = rol_con_permisos('Supervisor de Laboratorio', 'ensayos.ver')
        tecnico = rol_con_permisos('Técnico de Laboratorio', 'ensayos.ver')
        comercial = rol_con_permisos('Comercial', 'cotizaciones.ver')
        PermisoModulo.objects.filter(codigo='ensayos.ver_todos').delete()

        migracion_ver_todos.forwards(apps, None)

        self.assertTrue(supervisor.permisos.filter(codigo='ensayos.ver_todos').exists())
        self.assertFalse(tecnico.permisos.filter(codigo='ensayos.ver_todos').exists())
        self.assertFalse(comercial.permisos.filter(codigo='ensayos.ver_todos').exists())
