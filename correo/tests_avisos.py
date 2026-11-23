"""Avisos de correo nuevo: contador y mensajes llegados desde la última consulta."""
from .mensajeria import crear_mensaje
from .models import Asignacion, Mensaje
from .tests_plataforma import HOST, BasePlataforma


class AvisosTests(BasePlataforma):
    def avisos(self, **params):
        return self.get('api_avisos', **params)

    def test_requiere_sesion_y_permiso(self):
        self.assertEqual(self.avisos().status_code, 401)
        self.entrar(self.sin_modulo)
        self.assertEqual(self.avisos().status_code, 403)

    def test_cuenta_solo_lo_suyo(self):
        self.entrar(self.gestor)  # informes: 1 sin leer; laboratorio no es suyo
        datos = self.avisos().json()
        self.assertEqual(datos['total'], 1)
        self.assertEqual(datos['cuentas'], {'informes': 1})
        self.entrar(self.ajeno)
        self.assertEqual(self.avisos().json()['cuentas'], {'laboratorio': 1})

    def test_primera_consulta_no_avisa_y_la_siguiente_si(self):
        self.entrar(self.gestor)
        primera = self.avisos().json()
        self.assertEqual(primera['nuevos'], [])
        nuevo = crear_mensaje(self.informes, 'entrada', de='pedro@pyme.example', de_nombre='Pedro', asunto='Cotización urgente')
        crear_mensaje(self.informes, 'spam', de='spam@malo.example', asunto='Gana dinero')
        crear_mensaje(self.lab, 'entrada', de='obra@otra.example', asunto='De otra cuenta')
        datos = self.avisos(desde=primera['ultimo']).json()
        self.assertEqual([n['id'] for n in datos['nuevos']], [nuevo.pk])
        self.assertEqual(datos['nuevos'][0]['de'], 'Pedro')
        self.assertEqual(datos['total'], 2)  # el spam y la otra cuenta no cuentan
        # ya vistos: con la nueva referencia no se repite
        self.assertEqual(self.avisos(desde=datos['ultimo']).json()['nuevos'], [])

    def test_lo_leido_no_avisa_y_desde_invalido_no_rompe(self):
        self.entrar(self.gestor)
        base = self.avisos().json()['ultimo']
        m = crear_mensaje(self.informes, 'entrada', de='x@y.example', asunto='Ya leído', leido=True)
        self.assertEqual(self.avisos(desde=base).json()['nuevos'], [])
        self.assertEqual(self.avisos(desde='abc').status_code, 200)
        self.assertGreaterEqual(self.avisos().json()['ultimo'], m.pk)

    def test_la_pantalla_trae_el_aviso(self):
        self.entrar(self.gestor)
        html = self.get('bandeja').content.decode()
        self.assertIn('data-avisos=', html)
        self.assertIn('correo/js/avisos.js', html)
        self.assertIn('data-avisos-abrir', html)  # la campana abre el panel
        self.assertIn('data-avisos-panel', html)
        self.assertIn('data-avisos-sonido', html)  # el sonido se apaga desde el panel

    def test_panel_trae_sin_leer_por_cuenta_con_enlace(self):
        self.entrar(self.gestor)
        datos = self.avisos().json()
        self.assertEqual([c['slug'] for c in datos['por_cuenta']], ['informes'])
        self.assertEqual(datos['por_cuenta'][0]['no_leidos'], 1)
        self.assertEqual(len(datos['sin_leer']), 1)
        fila = datos['sin_leer'][0]
        self.assertEqual(fila['de'], 'Ana Cliente')
        self.assertIn(f'?h={self.m.hilo_id}', fila['url'])
        self.assertEqual(self.client.get(fila['url'], HTTP_HOST=HOST).status_code, 200)

    def test_pendientes_asignados_fallidos_y_borradores(self):
        Asignacion.objects.create(hilo=self.m.hilo, asignado_a=self.gestor, asignado_por=self.jefe)
        Asignacion.objects.create(hilo=self.m_lab.hilo, asignado_a=self.gestor)  # cuenta ajena: no cuenta
        crear_mensaje(self.informes, 'salida', de='informes@grupovicaf.com', asunto='Rebotó',
                      estado=Mensaje.FALLIDO, creado_por=self.gestor, leido=True)
        crear_mensaje(self.informes, 'borradores', de='informes@grupovicaf.com', asunto='Mío',
                      estado=Mensaje.BORRADOR, creado_por=self.gestor, leido=True)
        crear_mensaje(self.informes, 'borradores', de='informes@grupovicaf.com', asunto='De Jorge',
                      estado=Mensaje.BORRADOR, creado_por=self.jefe, leido=True)
        self.entrar(self.gestor)
        p = self.avisos().json()['pendientes']
        self.assertEqual(p['asignados']['n'], 1)
        self.assertEqual(p['asignados']['lista'][0]['id'], self.m.pk)
        self.assertEqual(p['fallidos']['n'], 1)
        self.assertEqual(p['fallidos']['lista'][0]['asunto'], 'Rebotó')
        self.assertEqual(p['borradores']['n'], 1)  # solo los suyos
        self.assertIn('/redactar/', p['borradores']['lista'][0]['url'])
        self.assertEqual(p['borradores']['lista'][0]['de'], 'Sin destinatario')
        # Atendido deja de estar pendiente
        Asignacion.objects.filter(asignado_a=self.gestor).update(estado=Asignacion.ATENDIDO)
        self.assertEqual(self.avisos().json()['pendientes']['asignados']['n'], 0)
