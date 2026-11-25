"""«Nueva recepción» de la lista de muestras apuntaba a «#» y no hacía nada
(pedido del cliente, 2026-11-22). Ahora abre la elección de proyecto."""
from django.test import TestCase, override_settings
from django.urls import reverse

from clientes.models import Cliente
from proyectos.models import Proyecto
from servicios.models import Cotizacion
from trabajadores.testing import crear_trabajador, rol_con_permisos


@override_settings(ROOT_URLCONF='grupovicaf.urls_lab')
class NuevaRecepcionTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        cliente = Cliente.objects.create(ruc='20111111111', razon_social='Constructora Uno SAC')
        cot = Cotizacion.objects.create(
            numero_oferta='VCF-OTE-2026-900', cliente=cliente, estado='Aceptada', asunto_servicio='x',
            persona_contacto='X', correo_contacto='x@x.invalid', telefono_contacto='1',
        )
        cls.abierto = Proyecto.objects.create(
            nombre_proyecto='Edificio Norte', codigo_proyecto='P-ABIERTO', cliente=cliente, cotizacion=cot,
        )
        Proyecto.objects.create(
            nombre_proyecto='Cerrado', codigo_proyecto='P-CERRADO', cliente=cliente, cotizacion=cot,
            estado='FINALIZADO',
        )
        Proyecto.objects.create(nombre_proyecto='Sin cotización', codigo_proyecto='P-SINCOT', cliente=cliente)
        cls.recepcion, _ = crear_trabajador('recepcion', rol_con_permisos('Recepción', 'muestras.ver', 'muestras.crear'))
        cls.lector, _ = crear_trabajador('lector', rol_con_permisos('Lector', 'muestras.ver'))

    def test_el_boton_lleva_a_elegir_proyecto(self):
        self.client.force_login(self.recepcion)
        html = self.client.get(reverse('proyectos:lista_recepciones')).content.decode()
        self.assertIn(f'href="{reverse("proyectos:crear_recepcion")}"', html)
        self.assertNotIn('href="#"\n            class="command-header__action"', html)

    def test_sin_permiso_de_crear_no_se_ofrece(self):
        self.client.force_login(self.lector)
        html = self.client.get(reverse('proyectos:lista_recepciones')).content.decode()
        self.assertNotIn('data-testid="nueva-recepcion"', html)
        self.assertEqual(self.client.get(reverse('proyectos:crear_recepcion')).status_code, 403)

    def test_lista_solo_proyectos_abiertos_con_cotizacion(self):
        self.client.force_login(self.recepcion)
        resp = self.client.get(reverse('proyectos:crear_recepcion'))
        self.assertEqual(resp.status_code, 200)
        html = resp.content.decode()
        self.assertIn(reverse('proyectos:crear_recepcion_desde_proyecto', args=[self.abierto.pk]), html)
        self.assertNotIn('P-CERRADO', html)
        self.assertNotIn('P-SINCOT', html)

    def test_busca_por_cliente_o_numero_de_oferta(self):
        self.client.force_login(self.recepcion)
        self.assertContains(self.client.get(reverse('proyectos:crear_recepcion'), {'q': 'OTE-2026-900'}), 'P-ABIERTO')
        self.assertNotContains(self.client.get(reverse('proyectos:crear_recepcion'), {'q': 'no-existe'}), 'P-ABIERTO')


@override_settings(ROOT_URLCONF='grupovicaf.urls_lab')
class ElegirProyectoPantallaCompletaTest(TestCase):
    """HU-LIMS-31: la elección de proyecto ordena por fecha y muestra el avance."""

    @classmethod
    def setUpTestData(cls):
        from datetime import timedelta
        from django.utils import timezone
        cliente = Cliente.objects.create(ruc='20222222222', razon_social='Minera Dos SAC')
        cls.proyectos = {}
        for codigo, dias in (('P-HOY', 0), ('P-VIEJO', 60), ('P-SEMANA', 3)):
            cot = Cotizacion.objects.create(
                numero_oferta=f'VCF-OTE-2026-{codigo}', cliente=cliente, estado='Aceptada', asunto_servicio='x',
                persona_contacto='X', correo_contacto='x@x.invalid', telefono_contacto='1',
            )
            p = Proyecto.objects.create(nombre_proyecto=codigo, codigo_proyecto=codigo, cliente=cliente, cotizacion=cot)
            Proyecto.objects.filter(pk=p.pk).update(creado_en=timezone.now() - timedelta(days=dias))
            cls.proyectos[codigo] = p
        cls.usuario, _ = crear_trabajador('recep2', rol_con_permisos('Recepción', 'muestras.ver', 'muestras.crear'))

    def test_agrupa_por_fecha_y_ordena_recientes_primero(self):
        self.client.force_login(self.usuario)
        html = self.client.get(reverse('proyectos:crear_recepcion')).content.decode()
        self.assertLess(html.index('P-HOY'), html.index('P-SEMANA'))
        self.assertLess(html.index('P-SEMANA'), html.index('P-VIEJO'))
        for titulo in ('Hoy', 'Esta semana', 'Anteriores'):
            self.assertIn(titulo, html)

    def test_orden_antiguos_invierte(self):
        self.client.force_login(self.usuario)
        html = self.client.get(reverse('proyectos:crear_recepcion'), {'orden': 'antiguos'}).content.decode()
        self.assertLess(html.index('P-VIEJO'), html.index('P-HOY'))

    def test_orden_invalido_cae_en_recientes(self):
        self.client.force_login(self.usuario)
        resp = self.client.get(reverse('proyectos:crear_recepcion'), {'orden': 'x; drop'})
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.context['orden'], 'recientes')

    def test_muestra_cuantas_muestras_lleva_cada_proyecto(self):
        from proyectos.models import MuestraDetalle, RecepcionMuestra, TipoMuestra
        tipo = TipoMuestra.objects.create(nombre='Concreto', sigla='CON')
        rec = RecepcionMuestra.objects.create(cotizacion=self.proyectos['P-HOY'].cotizacion, responsable_recepcion=self.usuario)
        for i in range(2):
            MuestraDetalle.objects.create(recepcion=rec, tipo_muestra=tipo, nro_item=i + 1, descripcion='d', cantidad=1, masa_aprox=1)
        self.client.force_login(self.usuario)
        resp = self.client.get(reverse('proyectos:crear_recepcion'))
        hoy = [p for g in resp.context['grupos'] for p in g['proyectos'] if p.codigo_proyecto == 'P-HOY'][0]
        self.assertEqual(hoy.total_muestras, 2)
        self.assertEqual(hoy.total_recepciones, 1)
        self.assertContains(resp, '2 muestras')


@override_settings(ROOT_URLCONF='grupovicaf.urls_lab')
class RegistroMuestrasModalTest(TestCase):
    """HU-LIMS-31: el formulario trae el modal y el servidor sigue recibiendo los mismos arreglos."""

    @classmethod
    def setUpTestData(cls):
        from proyectos.models import TipoMuestra, UnidadMedida
        cliente = Cliente.objects.create(ruc='20333333333', razon_social='Vial Tres SAC')
        cot = Cotizacion.objects.create(
            numero_oferta='VCF-OTE-2026-950', cliente=cliente, estado='Aceptada', asunto_servicio='x',
            persona_contacto='X', correo_contacto='x@x.invalid', telefono_contacto='1',
        )
        cls.proyecto = Proyecto.objects.create(nombre_proyecto='Vía', codigo_proyecto='P-VIA', cliente=cliente, cotizacion=cot)
        cls.tipo = TipoMuestra.objects.create(nombre='Suelo', sigla='SU')
        cls.unidad = UnidadMedida.objects.create(nombre='Unidad', codigo='UND')
        cls.usuario, _ = crear_trabajador('recep3', rol_con_permisos('Recepción', 'muestras.ver', 'muestras.crear', 'muestras.editar'))

    def test_formulario_trae_el_modal_y_el_script(self):
        self.client.force_login(self.usuario)
        html = self.client.get(reverse('proyectos:crear_recepcion_desde_proyecto', args=[self.proyecto.pk])).content.decode()
        for marca in ('id="modalMuestras"', 'registrar-muestras', 'recepcion_muestras.js', 'id="tbody-muestras"'):
            self.assertIn(marca, html)
        self.assertNotIn('tipo_global_search', html)

    def test_post_crea_las_muestras_de_los_arreglos(self):
        from proyectos.models import MuestraDetalle
        self.client.force_login(self.usuario)
        resp = self.client.post(reverse('proyectos:crear_recepcion_desde_proyecto', args=[self.proyecto.pk]), {
            'procedencia': 'cantera', 'responsable_entrega': 'ana', 'telefono_entrega': '1',
            'tipo_muestra_id[]': [self.tipo.pk, self.tipo.pk],
            'cantidad[]': ['2', '1'], 'unidad_medida_id[]': [self.unidad.pk, self.unidad.pk],
            'masa[]': ['1.5', ''], 'descripcion[]': ['Calicata 1', 'Calicata 2'], 'observaciones[]': ['', 'húmeda'],
        })
        self.assertEqual(resp.status_code, 302)
        muestras = list(MuestraDetalle.objects.order_by('nro_item'))
        self.assertEqual([m.descripcion for m in muestras], ['Calicata 1', 'Calicata 2'])
        self.assertEqual(muestras[0].cantidad, 2)
        self.assertEqual(str(muestras[0].masa_aprox), '1.50')

    def test_en_edicion_las_registradas_son_solo_lectura(self):
        from proyectos.models import MuestraDetalle, RecepcionMuestra
        rec = RecepcionMuestra.objects.create(cotizacion=self.proyecto.cotizacion, responsable_recepcion=self.usuario)
        MuestraDetalle.objects.create(recepcion=rec, tipo_muestra=self.tipo, nro_item=1, descripcion='ya', cantidad=1, masa_aprox=1)
        self.client.force_login(self.usuario)
        resp = self.client.get(reverse('proyectos:editar_recepcion', args=[rec.pk]))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'muestras-existentes')


@override_settings(ROOT_URLCONF='grupovicaf.urls_lab')
class CodigoLaboratorioVistaPreviaTest(TestCase):
    """El modal muestra el ID de laboratorio que se asignará (V-M-año-SIGLA-NNNN)."""

    @classmethod
    def setUpTestData(cls):
        from proyectos.models import TipoMuestra
        cliente = Cliente.objects.create(ruc='20444444444', razon_social='Obra Cuatro SAC')
        cot = Cotizacion.objects.create(
            numero_oferta='VCF-OTE-2026-960', cliente=cliente, estado='Aceptada', asunto_servicio='x',
            persona_contacto='X', correo_contacto='x@x.invalid', telefono_contacto='1',
        )
        cls.proyecto = Proyecto.objects.create(nombre_proyecto='Obra', codigo_proyecto='P-OBRA', cliente=cliente, cotizacion=cot)
        cls.tipo = TipoMuestra.objects.create(nombre='Suelo natural', sigla='SN')
        cls.usuario, _ = crear_trabajador('recep4', rol_con_permisos('Recepción', 'muestras.ver', 'muestras.crear'))

    def test_tipos_traen_prefijo_y_siguiente_numero(self):
        import json
        from django.utils import timezone
        self.client.force_login(self.usuario)
        resp = self.client.get(reverse('proyectos:crear_recepcion_desde_proyecto', args=[self.proyecto.pk]))
        tipos = json.loads(resp.context['tipos_muestra_json'])
        sn = [t for t in tipos if t['prefijo'] == 'SN'][0]
        self.assertEqual(sn['codigo_prefijo'], f'V-M-{timezone.now().year}-SN-')
        self.assertEqual(sn['siguiente'], 1)

    def test_el_siguiente_numero_sigue_a_lo_ya_registrado(self):
        import json
        from proyectos.models import MuestraDetalle, RecepcionMuestra
        rec = RecepcionMuestra.objects.create(cotizacion=self.proyecto.cotizacion, responsable_recepcion=self.usuario)
        MuestraDetalle.objects.create(recepcion=rec, tipo_muestra=self.tipo, nro_item=1, descripcion='a', cantidad=1, masa_aprox=1)
        self.client.force_login(self.usuario)
        resp = self.client.get(reverse('proyectos:crear_recepcion_desde_proyecto', args=[self.proyecto.pk]))
        sn = [t for t in json.loads(resp.context['tipos_muestra_json']) if t['prefijo'] == 'SN'][0]
        self.assertEqual(sn['siguiente'], 2)

    def test_crear_tipo_devuelve_siguiente_y_limita_la_sigla_a_5(self):
        self.client.force_login(self.usuario)
        url = reverse('proyectos:crear_tipo_muestra_ajax')
        ok = self.client.post(url, {'nombre': 'Roca fresca', 'sigla': 'rf'})
        self.assertEqual(ok.status_code, 200)
        self.assertEqual(ok.json()['siguiente'], 1)
        largo = self.client.post(url, {'nombre': 'Algo', 'sigla': 'ABCDEFG'})
        self.assertEqual(largo.status_code, 400)


@override_settings(ROOT_URLCONF='grupovicaf.urls_lab')
class SiglaDeTipoRepetidaTest(TestCase):
    """«Carbón» con la sigla CA (de «Calicatas») no debe caer en silencio en otro tipo."""

    @classmethod
    def setUpTestData(cls):
        from proyectos.models import TipoMuestra
        TipoMuestra.objects.create(nombre='Calicatas', sigla='CA')
        cls.usuario, _ = crear_trabajador('recep5', rol_con_permisos('Recepción', 'muestras.ver', 'muestras.crear'))

    def test_sigla_ya_usada_por_otro_nombre_da_error_claro(self):
        from proyectos.models import TipoMuestra
        self.client.force_login(self.usuario)
        resp = self.client.post(reverse('proyectos:crear_tipo_muestra_ajax'), {'nombre': 'Carbón', 'sigla': 'ca'})
        self.assertEqual(resp.status_code, 400)
        self.assertIn('Calicatas', resp.json()['message'])
        self.assertEqual(TipoMuestra.objects.count(), 1)

    def test_mismo_nombre_y_sigla_reutiliza_el_existente(self):
        self.client.force_login(self.usuario)
        resp = self.client.post(reverse('proyectos:crear_tipo_muestra_ajax'), {'nombre': 'calicatas', 'sigla': 'CA'})
        self.assertEqual(resp.status_code, 200)
        self.assertFalse(resp.json()['nuevo'])
