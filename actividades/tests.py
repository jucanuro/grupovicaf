import json
from datetime import timedelta

from django.conf import settings
from django.core import mail
from django.test import Client, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from clientes.models import Cliente
from trabajadores.testing import crear_trabajador, rol_con_permisos

from .models import CalendarioActividad, CalendarioCategoria, CalendarioMiembro, CalendarioParticipante


def _inicio():
    return timezone.now().replace(microsecond=0) + timedelta(hours=1)


@override_settings(ROOT_URLCONF='grupovicaf.urls_lab')
class GuardarActividadTest(TestCase):
    """El calendario no guardaba: el JS mandaba la cookie «csrftoken», que no
    existe (se llama gv_<rol>_csrftoken), y el 403 se perdía en silencio."""

    @classmethod
    def setUpTestData(cls):
        rol = rol_con_permisos('Agenda', 'calendario.ver', 'calendario.crear', 'calendario.editar',
                               'ensayos.ver_todos')
        cls.user, _ = crear_trabajador('agenda', rol)
        cls.cliente = Cliente.objects.create(ruc='20111111111', razon_social='Cliente Agenda SAC',
                                             correo_contacto='cliente@agenda.invalid')
        cls.sin_correo = Cliente.objects.create(ruc='20111111112', razon_social='Sin Correo SAC')

    def payload(self, **cambios):
        inicio = _inicio()
        datos = {
            'titulo': 'Reunión con cliente',
            'clase': 'REUNION',
            'estado': 'PROGRAMADA',
            'prioridad': 'MEDIA',
            'fecha_inicio': inicio.isoformat(),
            'fecha_fin': (inicio + timedelta(hours=1)).isoformat(),
            'cliente_id': self.cliente.pk,
            'recordatorios': [{'minutos_antes': '30', 'tipo': 'APP'}],
        }
        datos.update(cambios)
        return datos

    def guardar(self, datos, client=None, token=None):
        client = client or self.client
        headers = {'HTTP_X_CSRFTOKEN': token} if token else {}
        return client.post(
            reverse('actividades:calendario_actividad_guardar_json'),
            data=json.dumps(datos), content_type='application/json', **headers,
        )

    def test_la_pagina_entrega_el_token_y_no_lee_la_cookie_csrftoken(self):
        self.client.force_login(self.user)
        html = self.client.get(reverse('actividades:calendario_dashboard')).content.decode()
        self.assertIn('const CSRF_TOKEN = ', html)
        self.assertNotIn("getCookie('csrftoken')", html)
        self.assertIn('novalidate', html)

    def test_guarda_con_el_token_de_la_pagina_y_csrf_activo(self):
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.user)
        client.get(reverse('actividades:calendario_dashboard'))
        token = client.cookies[settings.CSRF_COOKIE_NAME].value
        sin_token = self.guardar(self.payload(), client=client)
        self.assertEqual(sin_token.status_code, 403)
        resp = self.guardar(self.payload(), client=client, token=token)
        self.assertEqual(resp.status_code, 200, resp.content)
        self.assertTrue(resp.json()['success'])
        actividad = CalendarioActividad.objects.get(pk=resp.json()['id'])
        self.assertEqual(actividad.recordatorios.count(), 1)

    def test_sin_cliente_se_guarda_como_actividad_interna(self):
        """El cliente dejó de ser obligatorio (pedido del Gerente, 2026-11-23)."""
        self.client.force_login(self.user)
        resp = self.guardar(self.payload(cliente_id=None, titulo='Reunión de coordinación'))
        self.assertEqual(resp.status_code, 200, resp.content)
        actividad = CalendarioActividad.objects.get()
        self.assertIsNone(actividad.cliente)
        self.assertEqual(actividad.cliente_nombre_manual, '')

    def test_valida_fechas_y_opciones_sin_guardar_a_medias(self):
        self.client.force_login(self.user)
        p = self.payload()
        invertidas = self.guardar(self.payload(fecha_inicio=p['fecha_fin'], fecha_fin=p['fecha_inicio']))
        self.assertEqual(invertidas.status_code, 400)
        self.assertEqual(self.guardar(self.payload(clase='INVENTADA')).status_code, 400)
        malos = self.guardar(self.payload(recordatorios=[{'minutos_antes': 'diez'}]))
        self.assertEqual(malos.status_code, 400)
        self.assertEqual(CalendarioActividad.objects.count(), 0)

    def test_el_cliente_no_recibe_nada_si_no_se_marca_el_aviso(self):
        self.client.force_login(self.user)
        with self.captureOnCommitCallbacks(execute=True):
            resp = self.guardar(self.payload())
        self.assertEqual(resp.status_code, 200, resp.content)
        self.assertEqual(len(mail.outbox), 0)
        self.assertIsNone(CalendarioActividad.objects.get().aviso_cliente_enviado_en)

    def test_con_el_aviso_marcado_se_envia_un_correo_al_cliente(self):
        self.client.force_login(self.user)
        with self.captureOnCommitCallbacks(execute=True):
            resp = self.guardar(self.payload(avisar_cliente=True, descripcion='Revisaremos el informe.',
                                             observaciones='Nota interna que no sale'))
        self.assertEqual(resp.status_code, 200, resp.content)
        self.assertEqual(len(mail.outbox), 1)
        correo = mail.outbox[0]
        self.assertEqual(correo.to, ['cliente@agenda.invalid'])
        self.assertIn('Reunión con cliente', correo.subject)
        self.assertIn('Revisaremos el informe.', correo.body)
        self.assertNotIn('Nota interna', correo.body)
        self.assertIsNotNone(CalendarioActividad.objects.get().aviso_cliente_enviado_en)

    def test_el_aviso_pide_un_cliente_con_correo(self):
        self.client.force_login(self.user)
        self.assertEqual(self.guardar(self.payload(cliente_id=None, avisar_cliente=True)).status_code, 400)
        resp = self.guardar(self.payload(cliente_id=self.sin_correo.pk, avisar_cliente=True))
        self.assertEqual(resp.status_code, 400)
        self.assertIn('correo', resp.json()['error'])
        self.assertEqual(CalendarioActividad.objects.count(), 0)

    def test_sin_ver_todos_no_se_vincula_un_cliente(self):
        rol = rol_con_permisos('Agenda técnico', 'calendario.ver', 'calendario.crear')
        tecnico, _ = crear_trabajador('agenda.tecnico', rol)
        self.client.force_login(tecnico)
        self.assertEqual(self.guardar(self.payload()).status_code, 403)
        ok = self.guardar(self.payload(cliente_id=None, cliente_nombre_manual='Obra Jaén'))
        self.assertEqual(ok.status_code, 200, ok.content)


@override_settings(ROOT_URLCONF='grupovicaf.urls_lab')
class VisibilidadCalendarioTest(TestCase):
    """Reglas de quién ve qué (HU-LIMS-21, actividades/visibilidad.py)."""

    @classmethod
    def setUpTestData(cls):
        rol = rol_con_permisos('Agenda completa', 'calendario.ver', 'calendario.crear', 'calendario.editar',
                               'calendario.eliminar')
        cls.ana, cls.perfil_ana = crear_trabajador('ana', rol, 'Ana Pérez')
        cls.beto, cls.perfil_beto = crear_trabajador('beto', rol, 'Beto Ruiz')
        cls.carla, cls.perfil_carla = crear_trabajador('carla', rol, 'Carla Díaz')

        cls.supervision = CalendarioCategoria.objects.create(nombre='Supervisión DICAP', color='#7c3aed')
        CalendarioMiembro.objects.create(calendario=cls.supervision, user=cls.ana, puede_crear=True)
        CalendarioMiembro.objects.create(calendario=cls.supervision, user=cls.beto, puede_crear=False)
        cls.laboratorio = CalendarioCategoria.objects.create(nombre='Laboratorio', color='#0891b2')
        cls.casa = CalendarioCategoria.objects.create(nombre='Casa', color='#ea580c', tipo='PERSONAL',
                                                      propietario=cls.ana)

        def actividad(titulo, calendario, creador, *participantes):
            inicio = _inicio()
            a = CalendarioActividad.objects.create(
                titulo=titulo, categoria=calendario, creado_por=creador,
                fecha_inicio=inicio, fecha_fin=inicio + timedelta(hours=1),
            )
            for perfil in participantes:
                CalendarioParticipante.objects.create(actividad=a, trabajador=perfil)
            return a

        cls.de_equipo = actividad('Revisión de informes', cls.supervision, cls.ana)
        cls.con_participantes = actividad('Coordinación privada', cls.laboratorio, cls.ana, cls.perfil_beto)
        cls.personal = actividad('Pago de casa', cls.casa, cls.ana)
        cls.abierta = actividad('Calibración de prensa', cls.laboratorio, cls.beto)

    def titulos(self, user):
        self.client.force_login(user)
        inicio = _inicio()
        resp = self.client.get(reverse('actividades:calendario_eventos_json'), {
            'start': (inicio - timedelta(days=1)).isoformat(), 'end': (inicio + timedelta(days=1)).isoformat(),
        })
        self.assertEqual(resp.status_code, 200)
        return {e['title'] for e in resp.json() if e['extendedProps']['tipo'] == 'actividad'}

    def test_cada_quien_ve_lo_que_le_corresponde(self):
        self.assertEqual(self.titulos(self.ana), {
            'Revisión de informes', 'Coordinación privada', 'Pago de casa', 'Calibración de prensa'})
        # Beto: miembro de Supervisión y participante; no ve lo personal de Ana.
        self.assertEqual(self.titulos(self.beto), {
            'Revisión de informes', 'Coordinación privada', 'Calibración de prensa'})
        # Carla: no es miembro de Supervisión ni participante.
        self.assertEqual(self.titulos(self.carla), {'Calibración de prensa'})

    def test_el_superusuario_tampoco_ve_calendarios_personales_ajenos(self):
        jefe = type(self.ana).objects.create_superuser('jefe', password='x')
        titulos = self.titulos(jefe)
        self.assertIn('Revisión de informes', titulos)
        self.assertNotIn('Pago de casa', titulos)
        self.assertNotIn('Coordinación privada', titulos)

    def test_lo_que_no_se_ve_responde_404_en_detalle_mover_y_eliminar(self):
        self.client.force_login(self.carla)
        for nombre in ('calendario_actividad_detalle_json',):
            self.assertEqual(self.client.get(reverse(f'actividades:{nombre}', args=[self.personal.pk])).status_code, 404)
        inicio = _inicio()
        mover = self.client.post(
            reverse('actividades:calendario_actividad_reprogramar_json', args=[self.con_participantes.pk]),
            data=json.dumps({'fecha_inicio': inicio.isoformat(), 'fecha_fin': (inicio + timedelta(hours=2)).isoformat()}),
            content_type='application/json')
        self.assertEqual(mover.status_code, 404)
        eliminar = self.client.post(reverse('actividades:calendario_actividad_eliminar_json', args=[self.de_equipo.pk]))
        self.assertEqual(eliminar.status_code, 404)
        self.assertEqual(CalendarioActividad.objects.count(), 4)

    def test_en_un_calendario_de_equipo_solo_crean_los_miembros_que_pueden(self):
        url = reverse('actividades:calendario_actividad_guardar_json')
        inicio = _inicio()

        def crear(user, calendario):
            self.client.force_login(user)
            return self.client.post(url, data=json.dumps({
                'titulo': 'Nueva', 'categoria_id': calendario.pk,
                'fecha_inicio': inicio.isoformat(), 'fecha_fin': (inicio + timedelta(hours=1)).isoformat(),
            }), content_type='application/json')

        self.assertEqual(crear(self.ana, self.supervision).status_code, 200)
        self.assertEqual(crear(self.beto, self.supervision).status_code, 403)  # solo ve
        self.assertEqual(crear(self.carla, self.supervision).status_code, 400)  # ni lo ve
        self.assertEqual(crear(self.carla, self.laboratorio).status_code, 200)  # sin miembros: todos
        self.assertEqual(crear(self.beto, self.casa).status_code, 400)  # personal ajeno

    def test_quien_solo_ve_el_calendario_no_mueve_sus_eventos(self):
        self.client.force_login(self.beto)
        inicio = _inicio()
        resp = self.client.post(
            reverse('actividades:calendario_actividad_reprogramar_json', args=[self.de_equipo.pk]),
            data=json.dumps({'fecha_inicio': inicio.isoformat(), 'fecha_fin': (inicio + timedelta(hours=2)).isoformat()}),
            content_type='application/json')
        self.assertEqual(resp.status_code, 403)
        detalle = self.client.get(reverse('actividades:calendario_actividad_detalle_json', args=[self.de_equipo.pk]))
        self.assertFalse(detalle.json()['puede_editar'])

    def test_la_pagina_solo_lista_los_calendarios_visibles(self):
        self.client.force_login(self.carla)
        datos = self.client.get(reverse('actividades:calendario_dashboard')).context['datos_calendario']
        self.assertEqual({c['nombre'] for c in datos['calendarios']}, {'Laboratorio'})
        self.client.force_login(self.ana)
        datos = self.client.get(reverse('actividades:calendario_dashboard')).context['datos_calendario']
        por_nombre = {c['nombre']: c for c in datos['calendarios']}
        self.assertEqual(set(por_nombre), {'Supervisión DICAP', 'Laboratorio', 'Casa'})
        self.assertEqual(por_nombre['Casa']['tipo'], 'PERSONAL')
        self.assertEqual(por_nombre['Supervisión DICAP']['miembros'], 2)

    def test_el_gantt_respeta_las_mismas_reglas(self):
        rol = rol_con_permisos('Gantt', 'gantt.ver', 'calendario.ver')
        dora, _ = crear_trabajador('dora', rol)
        self.client.force_login(dora)
        resp = self.client.get(reverse('actividades:gantt_actividades_json'), {'ensayos': 'false'})
        self.assertEqual(resp.status_code, 200)
        texto = json.dumps(resp.json(), ensure_ascii=False)
        self.assertIn('Calibración de prensa', texto)
        for oculto in ('Pago de casa', 'Coordinación privada', 'Revisión de informes'):
            self.assertNotIn(oculto, texto)


@override_settings(ROOT_URLCONF='grupovicaf.urls_lab')
class CrearCalendarioTest(TestCase):

    @classmethod
    def setUpTestData(cls):
        cls.solo_ver, _ = crear_trabajador('solo.ver', rol_con_permisos('Ver', 'calendario.ver'))
        cls.creador, _ = crear_trabajador('creador', rol_con_permisos('Crear', 'calendario.ver', 'calendario.crear'))
        _, cls.perfil_otro = crear_trabajador('otro', rol_con_permisos('Otro', 'calendario.ver'))

    def crear(self, user, **datos):
        self.client.force_login(user)
        return self.client.post(reverse('actividades:calendario_categoria_crear_json'),
                                data=json.dumps(datos), content_type='application/json')

    def test_cualquiera_crea_su_calendario_personal(self):
        resp = self.crear(self.solo_ver, nombre='Estudio', color='#16a34a', tipo='PERSONAL')
        self.assertEqual(resp.status_code, 200, resp.content)
        cal = CalendarioCategoria.objects.get(nombre='Estudio')
        self.assertEqual((cal.tipo, cal.propietario), ('PERSONAL', self.solo_ver))
        # Otro usuario puede tener su propio «Estudio».
        self.assertEqual(self.crear(self.creador, nombre='Estudio', color='#16a34a', tipo='PERSONAL').status_code, 200)
        self.assertEqual(self.crear(self.solo_ver, nombre='estudio', color='#16a34a', tipo='PERSONAL').status_code, 400)

    def test_el_de_equipo_pide_permiso_y_guarda_sus_miembros(self):
        self.assertEqual(self.crear(self.solo_ver, nombre='Supervisión', color='#7c3aed', tipo='EQUIPO').status_code, 403)
        resp = self.crear(self.creador, nombre='Supervisión', color='#7c3aed', tipo='EQUIPO',
                          miembros=[self.perfil_otro.pk], miembros_crean=[])
        self.assertEqual(resp.status_code, 200, resp.content)
        cal = CalendarioCategoria.objects.get(nombre='Supervisión')
        self.assertEqual(
            set(cal.miembros.values_list('user__username', 'puede_crear')),
            {('creador', True), ('otro', False)},
        )

    def test_valida_nombre_y_color(self):
        self.assertEqual(self.crear(self.solo_ver, nombre='<b>', color='#16a34a').status_code, 400)
        self.assertEqual(self.crear(self.solo_ver, nombre='Casa', color='red;}').status_code, 400)
        self.assertEqual(self.crear(self.solo_ver, nombre='Casa', color='#16a34a', tipo='OTRO').status_code, 400)
