"""Autocompletado de destinatarios (correo/directorio.py y api_contactos).

Privacidad: solo se sugieren contactos de las cuentas que el usuario puede
abrir, el equipo VICAF son trabajadores (no usuarios del portal) y los
clientes del LIMS exigen `clientes.ver`.
"""
from unittest import skipUnless

from django.contrib.auth.models import User
from django.test import override_settings

from clientes.models import Cliente
from trabajadores.testing import crear_trabajador, rol_con_permisos

from .mensajeria import crear_mensaje
from .models import AccesoCuenta, Mensaje
from .tests_plataforma import ES_POSTGRES, HOST, BasePlataforma, ruta
from .views_redactar import _fmt


@override_settings(ROOT_URLCONF='grupovicaf.urls_lab', SITE_ROLE='lab')
class DirectorioTests(BasePlataforma):
    def setUp(self):
        super().setUp()
        crear_mensaje(self.lab, 'entrada', de='secreto@competencia.example', de_nombre='Socio Secreto',
                      asunto='Solo para laboratorio', html='<p>x</p>')
        Cliente.objects.create(ruc='20111111111', razon_social='Constructora Andina SAC',
                               correo_contacto='compras@andina.example', persona_contacto='Rosa Díaz')
        User.objects.create_user('cliente_portal', email='portal@cliente.example', first_name='Portal')

    def sugerir(self, usuario=None, **params):
        self.entrar(usuario or self.gestor)
        respuesta = self.client.get(ruta('api_contactos'), params, HTTP_HOST=HOST)
        self.assertEqual(respuesta.status_code, 200)
        return [r['correo'] for r in respuesta.json()['resultados']]

    def test_sin_texto_devuelve_los_recientes_de_mis_cuentas(self):
        self.assertEqual(self.sugerir(q=''), ['ana@cliente.example'])

    def test_no_sugiere_contactos_de_cuentas_ajenas(self):
        self.assertNotIn('secreto@competencia.example', self.sugerir(q='secreto'))
        self.assertNotIn('secreto@competencia.example', self.sugerir(q=''))
        self.assertIn('secreto@competencia.example', self.sugerir(self.ajeno, q='secreto'))

    def test_sugiere_cuentas_vicaf(self):
        self.assertEqual(self.sugerir(q='labor'), ['laboratorio@grupovicaf.com'])

    def test_sugiere_al_equipo_pero_no_a_usuarios_del_portal(self):
        jefe = self.jefe
        jefe.email = 'jorge.jefe@grupovicaf.com'
        jefe.save()
        self.assertIn('jorge.jefe@grupovicaf.com', self.sugerir(q='jorge'))
        self.assertEqual(self.sugerir(q='portal'), [])

    def test_clientes_del_lims_solo_con_permiso(self):
        self.assertIn('compras@andina.example', self.sugerir(q='andina'))
        sin_permiso, _ = crear_trabajador('sin_clientes', rol_con_permisos('Solo correo', 'correo.ver'))
        AccesoCuenta.objects.create(usuario=sin_permiso, cuenta=self.informes, rol=AccesoCuenta.GESTIONA)
        self.assertEqual(self.sugerir(sin_permiso, q='andina'), [])

    @skipUnless(ES_POSTGRES, 'unaccent solo existe en PostgreSQL')
    def test_no_distingue_tildes(self):
        self.assertIn('compras@andina.example', self.sugerir(q='diaz'))

    def test_excluye_los_ya_elegidos(self):
        self.assertEqual(self.sugerir(q='', excluir='ana@cliente.example'), [])

    def test_primero_lo_que_empieza_por_el_texto(self):
        self.jefe.email = 'informes.jefe@otro.example'
        self.jefe.save()
        self.assertEqual(self.sugerir(q='informes')[0], 'informes@grupovicaf.com')

    def test_sin_modulo_de_correo_no_hay_sugerencias(self):
        self.entrar(self.sin_modulo)
        self.assertEqual(self.client.get(ruta('api_contactos'), {'q': 'ana'}, HTTP_HOST=HOST).status_code, 403)


@override_settings(ROOT_URLCONF='grupovicaf.urls_lab', SITE_ROLE='lab')
class DestinatariosTests(BasePlataforma):
    def test_nombres_con_coma_van_entre_comillas_y_vuelven_igual(self):
        personas = [{'nombre': 'Pérez, Jorge', 'correo': 'j@x.example'}, {'nombre': '', 'correo': 'a@b.example'}]
        texto = _fmt(personas)
        self.assertEqual(texto, '"Pérez, Jorge" <j@x.example>, a@b.example')
        self.entrar(self.gestor)
        self.client.get(ruta('redactar'), {'cuenta': 'informes'}, HTTP_HOST=HOST)
        borrador = Mensaje.objects.get(estado_envio=Mensaje.BORRADOR)
        respuesta = self.client.post(ruta('borrador_guardar', borrador.pk), {'para': texto + '; c@d.example'},
                                     HTTP_HOST=HOST, HTTP_X_REQUESTED_WITH='fetch')
        self.assertTrue(respuesta.json()['ok'])
        borrador.refresh_from_db()
        self.assertEqual([p['correo'] for p in borrador.para], ['j@x.example', 'a@b.example', 'c@d.example'])
        self.assertEqual(borrador.para[0]['nombre'], 'Pérez, Jorge')

    def test_direccion_invalida_se_avisa(self):
        self.entrar(self.gestor)
        self.client.get(ruta('redactar'), {'cuenta': 'informes'}, HTTP_HOST=HOST)
        borrador = Mensaje.objects.get(estado_envio=Mensaje.BORRADOR)
        respuesta = self.client.post(ruta('borrador_enviar', borrador.pk), {'para': 'malo@, bien@x.example'},
                                     HTTP_HOST=HOST, follow=True)
        self.assertContains(respuesta, 'no es un correo válido')
        borrador.refresh_from_db()
        self.assertEqual(borrador.estado_envio, Mensaje.BORRADOR)


@override_settings(ROOT_URLCONF='grupovicaf.urls_lab', SITE_ROLE='lab')
class BuscadorSugerenciasTests(BasePlataforma):
    """Barra de búsqueda: sugerencias mientras se escribe (api_buscar)."""

    def sugerencias(self, q, usuario=None):
        self.entrar(usuario or self.gestor)
        respuesta = self.client.get(ruta('api_buscar'), {'q': q}, HTTP_HOST=HOST)
        self.assertEqual(respuesta.status_code, 200)
        return respuesta.json()

    def test_sugiere_personas_y_correos(self):
        datos = self.sugerencias('ana')
        self.assertEqual(datos['personas'][0]['correo'], 'ana@cliente.example')
        self.assertIn('contacto', datos['personas'][0]['url'])
        self.assertEqual([c['asunto'] for c in datos['correos']], ['Cotización de compresión de probetas'])
        self.assertTrue(datos['correos'][0]['adjunto'])
        self.assertIn(f'?h={self.m.hilo_id}', datos['correos'][0]['url'])

    def test_palabra_a_medio_escribir(self):
        asuntos = [c['asunto'] for c in self.sugerencias('probet')['correos']]
        self.assertEqual(asuntos, ['Cotización de compresión de probetas'])

    @skipUnless(ES_POSTGRES, 'unaccent solo existe en PostgreSQL')
    def test_sin_tildes(self):
        self.assertEqual(len(self.sugerencias('cotizacion compres')['correos']), 1)

    def test_nunca_correos_de_cuentas_ajenas(self):
        self.assertEqual(self.sugerencias('proctor')['correos'], [])
        self.assertEqual(len(self.sugerencias('proctor', self.ajeno)['correos']), 1)
        self.assertEqual(self.sugerencias('cotizacion', self.ajeno)['correos'], [])

    def test_ni_papelera_ni_borradores(self):
        from .mensajeria import carpeta, mover
        mover([self.m], carpeta(self.informes, 'papelera'), self.gestor)
        self.assertEqual(self.sugerencias('probetas')['correos'], [])

    def test_texto_corto_o_raro_no_consulta(self):
        self.assertEqual(self.sugerencias('a'), {'personas': [], 'correos': []})
        self.assertEqual(self.sugerencias('&|!:*')['correos'], [])

    def test_sin_modulo_de_correo_403(self):
        self.entrar(self.sin_modulo)
        self.assertEqual(self.client.get(ruta('api_buscar'), {'q': 'ana'}, HTTP_HOST=HOST).status_code, 403)

    def test_la_barra_es_un_combobox_accesible(self):
        self.entrar(self.gestor)
        html = self.client.get(ruta('bandeja'), HTTP_HOST=HOST).content.decode()
        self.assertIn('role="combobox"', html)
        self.assertIn('aria-controls="q-rapida-lista"', html)
        self.assertIn('role="listbox"', html)
