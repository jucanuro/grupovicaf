"""Borrador local de formularios largos (HU-LIMS-27, REQ-LIMS-111 a 115): las
pantallas críticas cargan el módulo y lo conectan a su formulario."""
from django.contrib.auth.models import User
from django.test import TestCase, override_settings
from django.urls import reverse

from proyectos.test_avance import AvanceMixin


@override_settings(ROOT_URLCONF='grupovicaf.urls_lab')
class BorradorLocalPantallasTests(AvanceMixin, TestCase):

    def setUp(self):
        # Superusuario: estas pruebas miran el cableado de las pantallas, no los permisos.
        self.admin = User.objects.create_superuser('admin.borrador', 'a@x.pe', 'x')
        self.client.force_login(self.admin)
        self.proyecto = self._proyecto(2)
        self.recepcion, _ = self._recepcion(self.proyecto, 1)

    def assertConBorrador(self, r, form):
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, 'js/borrador_local.js')
        self.assertContains(r, 'BorradorLocal.iniciar')
        self.assertContains(r, form)
        # El usuario va en el <body>: el borrador es por usuario y por pantalla.
        self.assertContains(r, f'data-usuario-id="{self.admin.pk}"')

    def test_cotizacion_restaura_antes_de_armar_sus_tablas(self):
        """REQ-LIMS-111."""
        r = self.client.get(reverse('servicios:crear_cotizacion'))
        self.assertConBorrador(r, "getElementById('cotizacion-form')")
        self.assertContains(r, 'temprano: true')
        self.assertContains(r, "'initial-detalles-json': 'detalles_json'")
        html = r.content.decode()
        self.assertLess(html.index('BorradorLocal.iniciar'), html.index('js/cotizacion-config.js'))

    def test_recepcion_guarda_las_filas_de_muestras(self):
        """REQ-LIMS-112."""
        r = self.client.get(reverse('proyectos:crear_recepcion_desde_proyecto', args=[self.proyecto.pk]))
        self.assertConBorrador(r, "getElementById('recepcion-form')")
        self.assertContains(r, "'#tbody-muestras'")

    def test_solicitud_de_ensayo_guarda_filas_e_incidencias(self):
        """REQ-LIMS-113."""
        r = self.client.get(reverse('proyectos:crear_solicitud'))
        self.assertConBorrador(r, "getElementById('solicitud-form')")
        self.assertContains(r, "'se-estado-borrador': 'estado_borrador'")
        self.assertContains(r, 'id="estado_borrador"')

    def test_datos_de_probetas(self):
        """REQ-LIMS-114."""
        r = self.client.get(reverse('proyectos:datos_probetas', args=[self.recepcion.pk]))
        self.assertConBorrador(r, 'data-form-probetas')

    def test_el_modulo_no_guarda_nada_en_el_servidor(self):
        """REQ-LIMS-115: el borrador vive en el equipo; no crea cotizaciones ni gasta números de oferta."""
        from servicios.models import Cotizacion
        antes = Cotizacion.objects.count()
        self.client.get(reverse('servicios:crear_cotizacion'))
        self.assertEqual(Cotizacion.objects.count(), antes)
