from django.core.cache import cache
from django.test import TestCase, override_settings
from django.urls import reverse

from servicios.models import Metodo, Norma, Servicio
from siteconfig.models import NegocioConfig
from web_acreditacion.models import Certificacion

from .views import _metricas_credibilidad


def _valor(etiqueta):
    return next((m['valor'] for m in _metricas_credibilidad() if m['etiqueta'] == etiqueta), None)


class MetricaEnsayosAcreditadosTestCase(TestCase):
    @classmethod
    def setUpTestData(cls):
        norma = Norma.objects.create(codigo='NTP-TEST', nombre='Norma de prueba')
        metodo = Metodo.objects.create(codigo='M-TEST', nombre='Método de prueba')
        for i in range(3):
            Servicio.objects.create(
                codigo_facturacion=f'T{i:03d}', nombre=f'Ensayo {i}',
                norma=norma, metodo=metodo, esta_acreditado=True,
            )

    def test_numero_oficial_manda_sobre_el_conteo(self):
        NegocioConfig.objects.filter(pk=1).update(ensayos_acreditados=6)
        self.assertEqual(_valor('Ensayos acreditados'), '6')

    def test_sin_numero_oficial_cae_al_conteo(self):
        NegocioConfig.objects.filter(pk=1).update(ensayos_acreditados=None)
        self.assertEqual(_valor('Ensayos acreditados'), '3')


@override_settings(ROOT_URLCONF='grupovicaf.urls_web')
class HomeCertificacionesTests(TestCase):
    """Sección resumida de certificaciones en la home (specs/WEB v4, T19; v6, T22; v7 horizontales, T23)."""

    def setUp(self):
        cache.clear()
        # La card solo usa archivo.url: basta el nombre, sin escribir en /media/.
        for i in range(5):
            Certificacion.objects.create(
                titulo=f'Extra {i}', descripcion='Corta.', tipo='otro', institucion='Entidad',
                archivo=f'certificaciones/extra-{i}.pdf', orden=10 + i,
            )

    def get_html(self):
        respuesta = self.client.get(reverse('web_home'))
        self.assertEqual(respuesta.status_code, 200)
        return respuesta.content.decode()

    def test_maximo_4_cards_en_orden_y_ver_todas(self):
        # REQ-WEB-49: INACAL (orden 0) + Extra 0 a 2; la ISO de la semilla no tiene PDF.
        html = self.get_html()
        self.assertEqual(html.count('<article class="group relative flex h-full'), 4)
        for titulo in ('Acreditación INACAL LE-230', 'Extra 0', 'Extra 1', 'Extra 2'):
            self.assertIn(f'data-cert-titulo="{titulo}"', html)
        self.assertNotIn('data-cert-titulo="Extra 3"', html)  # 'Extra 3' sí va en el JSON-LD
        self.assertLess(html.index('data-cert-titulo="Extra 0"'), html.index('data-cert-titulo="Extra 2"'))
        self.assertIn('<ul class="reveal-group mx-auto flex max-w-[1200px] flex-wrap justify-center gap-6" role="list">', html)
        self.assertIn(f'href="{reverse("web_acreditacion:acreditacion")}" class="btn-secondary-inverse shrink-0"', html)
        self.assertIn('Ver todas<span class="sr-only"> las acreditaciones y certificaciones</span>', html)
        self.assertEqual(html.count('id="modal-certificacion"'), 1)
        self.assertIn('web/js/certificaciones.js', html)

    def test_mismas_cards_que_acreditacion_sobre_fondo_azul(self):
        # REQ-WEB-73: cards completas (tipo, descripción, vigencia), con borde
        # y sombra claros, y "Ver todas" en la fila del título.
        html = self.get_html()
        seccion = html[html.index('<span class="eyebrow-inverse">'):html.index('id="modal-certificacion"')]
        self.assertEqual(seccion.count('data-sello-generico'), 4)
        self.assertEqual(seccion.count('Ver documento\n'), 4)
        self.assertEqual(seccion.count('Corta.'), 3)
        self.assertEqual(seccion.count('>Otro</span>'), 3)
        self.assertEqual(seccion.count('border-white/25'), 4)
        titulo = seccion.index('id="acreditacion-titulo"')
        self.assertLess(titulo, seccion.index('Ver todas<span'))
        self.assertLess(seccion.index('Ver todas<span'), seccion.index('class="body-copy-inverse'))

    def test_sin_la_imagen_grande_del_certificado(self):
        # REQ-WEB-49 / CA-08.9
        html = self.get_html()
        self.assertNotIn('GRUPO-VICAF-CERTIFICADO', html)
        self.assertNotIn('<img src="/media/certificaciones/inacal', html)
        for viejo in ('modal-certificado-inacal', 'modal-certificado.js', 'data-modal-cert-open'):
            self.assertNotIn(viejo, html)

    def test_textos_solo_cajamarca(self):
        # REQ-WEB-52 (D-VCF-002): ni el texto de la sección ni la meta description.
        html = self.get_html()
        self.assertNotIn('norte del per', html.lower())
        self.assertIn('reconocidos por entidades públicas y privadas de Cajamarca.', html)
        self.assertIn(
            '<meta name="description" content="Laboratorio de ensayo de materiales y geotecnia '
            'acreditado por INACAL, con sede en Cajamarca.">', html,
        )

    def test_accesos_inacal_abren_la_acreditacion_en_el_modal(self):
        # REQ-WEB-50: badge del hero, franja de credibilidad y la card.
        html = self.get_html()
        self.assertEqual(html.count('data-cert-titulo="Acreditación INACAL LE-230"'), 3)

    def test_sin_certificaciones_publicadas(self):
        Certificacion.objects.update(activo=False)
        html = self.get_html()
        self.assertNotIn('group relative flex h-full', html)
        self.assertNotIn('modal-certificacion', html)
        self.assertNotIn('certificaciones.js', html)
        # Los accesos INACAL y "Ver todas" llevan a /acreditacion/.
        url = reverse('web_acreditacion:acreditacion')
        self.assertGreaterEqual(html.count(f'href="{url}"'), 3)


class PaginaNoEncontradaTests(TestCase):
    def test_404_con_marca_un_h1_y_noindex(self):
        respuesta = self.client.get('/esta-pagina-no-existe/')

        self.assertEqual(respuesta.status_code, 404)
        self.assertTemplateUsed(respuesta, 'web/404.html')
        html = respuesta.content.decode()
        self.assertEqual(html.count('<h1'), 1)
        self.assertIn('noindex', html)
        self.assertIn('/servicios/', html)
