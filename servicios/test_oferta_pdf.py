"""PDF de la oferta con el diseño del Word FOR-001 v7 y catálogo de condiciones del Word."""
from decimal import Decimal
from io import BytesIO

from django.contrib.auth.models import User
from django.test import TestCase, override_settings
from django.urls import reverse
from pypdf import PdfReader

from clientes.models import Cliente
from servicios import oferta_pdf
from servicios.models import (
    CatalogoCondicionItem, CatalogoCondicionSeccion, Cotizacion, CotizacionCondicionItem,
    CotizacionCondicionSeccion, CotizacionDetalle, CotizacionGrupo, Servicio,
)
from servicios.seeds.condiciones import sembrar_condiciones


class FormatoTests(TestCase):

    def test_soles_como_el_word(self):
        self.assertEqual(oferta_pdf.soles(Decimal('1310')), 'S/ 1 310,00')
        self.assertEqual(oferta_pdf.soles(Decimal('70')), 'S/ 70,00')
        self.assertEqual(oferta_pdf.soles(Decimal('1234567.5')), 'S/ 1 234 567,50')

    def test_quita_las_llaves_de_lo_resaltado(self):
        self.assertEqual(oferta_pdf.quitar_marcas('Cantidad: {{25}} kg y {{ XX }} días'), 'Cantidad: 25 kg y XX días')


class CatalogoWordTests(TestCase):

    def test_siembra_secciones_y_grupos_del_word(self):
        CatalogoCondicionSeccion.objects.create(codigo='DATOS_PAGO', titulo='viejo', orden=9)
        sembrar_condiciones()
        activas = list(CatalogoCondicionSeccion.objects.filter(activo=True).values_list('codigo', flat=True))
        self.assertEqual(activas, ['NOTAS', 'PAGO', 'PLAZO', 'CONDICIONES', 'IMPARCIALIDAD'])
        campo = CatalogoCondicionItem.objects.get(texto='ENSAYOS EN CAMPO')
        self.assertEqual(sorted(campo.children.values_list('texto', flat=True)),
                         ['DENSIDAD MEDIANTE EL CONO Y LA ARENA', 'EXTRACCIÓN DE NÚCLEOS DIAMANTINOS'])
        self.assertTrue(CatalogoCondicionItem.objects.filter(texto__contains='{{XX}} kg').exists())
        # Alternativas resaltadas: solo la de siempre va marcada.
        pagos = CatalogoCondicionItem.objects.filter(texto__startswith='Forma de pago')
        self.assertEqual([p.texto for p in pagos if p.seleccionado_por_defecto], ['Forma de pago: Por adelantado.'])
        # Idempotente.
        n = CatalogoCondicionItem.objects.count()
        sembrar_condiciones()
        self.assertEqual(CatalogoCondicionItem.objects.count(), n)


@override_settings(ROOT_URLCONF='grupovicaf.urls_lab')
class PdfOfertaTests(TestCase):

    def setUp(self):
        self.user = User.objects.create_superuser('jefe', 'j@x.pe', 'x')
        cliente = Cliente.objects.create(ruc='20604828865', razon_social='Kiavaca EIRL')
        self.cot = Cotizacion.objects.create(
            cliente=cliente, asunto_servicio='Diseño de mezclas comprobado', persona_contacto='-',
            correo_contacto='arq@example.com', telefono_contacto='-', tasa_igv=Decimal('0.18'),
            numero_oferta='VCF-OTE-2025-552',
        )
        CotizacionGrupo.objects.create(cotizacion=self.cot, nombre_grupo='ENSAYOS DE LABORATORIO', orden=0)
        cat = CotizacionGrupo.objects.create(cotizacion=self.cot, nombre_grupo='ENSAYOS DE LABORATORIO', orden=1)
        sub = CotizacionGrupo.objects.create(cotizacion=self.cot, nombre_grupo='Agregado Grueso', orden=2)
        otra = CotizacionGrupo.objects.create(cotizacion=self.cot, nombre_grupo='COMPROBACIÓN DE DISEÑOS', orden=3)
        s1 = Servicio.objects.create(codigo_facturacion='X1', nombre='Contenido de Humedad', esta_acreditado=True)
        s2 = Servicio.objects.create(codigo_facturacion='X2', nombre='Elaboración de probetas')
        CotizacionDetalle.objects.create(grupo=sub, servicio=s1, norma_manual='ASTM C566-19',
                                         descripcion_especifica='Contenido de Humedad', precio_unitario=Decimal('25'))
        CotizacionDetalle.objects.create(grupo=otra, servicio=s2, norma_manual='ASTM C31', cantidad=12,
                                         descripcion_especifica='Elaboración de probetas', precio_unitario=Decimal('10'))
        self.assertIsNotNone(cat)
        notas = CotizacionCondicionSeccion.objects.create(cotizacion=self.cot, codigo='NOTAS', titulo='NOTAS:',
                                                          tipo='notas', orden=1, seleccionada=True)
        CotizacionCondicionItem.objects.create(seccion=notas, texto_base='(*) Acreditados', texto_final='(*) Acreditados',
                                               seleccionado=True)
        pago = CotizacionCondicionSeccion.objects.create(cotizacion=self.cot, codigo='PAGO', orden=2, seleccionada=True,
                                                         titulo='FORMAS DE PAGO y CONTRATACIÓN DEL SERVICIO')
        CotizacionCondicionItem.objects.create(seccion=pago, texto_base='x', texto_final='Forma de pago: Por adelantado.',
                                               seleccionado=True)
        CotizacionCondicionItem.objects.create(seccion=pago, texto_base='x', texto_final='Forma de pago: 50/50.',
                                               seleccionado=False)
        cond = CotizacionCondicionSeccion.objects.create(cotizacion=self.cot, codigo='CONDICIONES', orden=3,
                                                         seleccionada=True, titulo='CONDICIONES Y DETALLES DEL SERVICIO')
        grupo = CotizacionCondicionItem.objects.create(seccion=cond, tipo_nodo='grupo', texto_base='G',
                                                       texto_final='ENSAYOS EN CONCRETO', seleccionado=True)
        CotizacionCondicionItem.objects.create(seccion=cond, parent=grupo, texto_base='x', seleccionado=True,
                                               texto_final='Cantidad de muestra requerida: {{25}} kg.')
        vacio = CotizacionCondicionItem.objects.create(seccion=cond, tipo_nodo='grupo', texto_base='G',
                                                       texto_final='ALQUILER DE EQUIPOS', seleccionado=False)
        CotizacionCondicionItem.objects.create(seccion=cond, parent=vacio, texto_base='x', texto_final='no va',
                                               seleccionado=False)

    def test_filas_con_categorias_y_subcategorias(self):
        filas = oferta_pdf.filas_items(self.cot)
        resumen = [(f['tipo'], f['codigo'], f['texto']) for f in filas]
        self.assertEqual(resumen, [
            ('categoria', 'A', 'ENSAYOS DE LABORATORIO'),
            ('subcategoria', 'a', 'Agregado Grueso'),
            ('item', '1,00', 'Contenido de Humedad (*)'),
            ('subcategoria', 'b', 'COMPROBACIÓN DE DISEÑOS'),
            ('item', '1,00', 'Elaboración de probetas'),
        ])
        self.assertEqual(filas[-1]['cantidad'], '12')
        self.assertEqual(filas[-1]['parcial'], 'S/ 120,00')

    def test_secciones_numeradas_y_solo_lo_marcado(self):
        notas, secciones = oferta_pdf.secciones_condiciones(self.cot, lambda t: t)
        self.assertEqual(len(notas), 1)
        self.assertEqual([(s['numero'], s['titulo']) for s in secciones],
                         [(2, 'FORMAS DE PAGO y CONTRATACIÓN DEL SERVICIO'), (3, 'CONDICIONES Y DETALLES DEL SERVICIO')])
        self.assertEqual(len(secciones[0]['nodos']), 1)
        grupos = [n for n in secciones[1]['nodos'] if n['grupo']]
        self.assertEqual([g['texto'] for g in grupos], ['ENSAYOS EN CONCRETO'])

    def test_vista_devuelve_el_pdf_con_el_diseno_del_word(self):
        self.client.force_login(self.user)
        r = self.client.get(reverse('servicios:ver_pdf_cotizacion', args=[self.cot.pk]))
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r['Content-Type'], 'application/pdf')
        self.assertIn('VCF-OTE-2025-552.pdf', r['Content-Disposition'])
        texto = ' '.join(p.extract_text() for p in PdfReader(BytesIO(r.content)).pages)
        for esperado in ('OFERTA No.', 'VCF-OTE-2025-552', 'Kiavaca EIRL', 'ENSAYOS DE LABORATORIO',
                         'COSTO DIRECTO SIN IGV', 'S/ 145,00', 'NOTAS:', 'Cantidad de muestra requerida: 25 kg.',
                         'Versión: 07', 'Página 1 de', '4.', 'CONTACTOS AUTORIZADOS DEL LABORATORIO',
                         'DATOS PARA CONTRATO', 'Aceptó', 'www.grupovicaf.com'):
            self.assertIn(esperado, texto)
        self.assertNotIn('{{', texto)
        self.assertNotIn('no va', texto)
        self.assertNotIn('50/50', texto)


@override_settings(ROOT_URLCONF='grupovicaf.urls_lab')
class PlantillaMismoDisenoTests(TestCase):
    """HU-LIMS-28: la plantilla se arma con la misma pantalla que la cotización
    (pasos en pills, detalle en modal, contenido con el mismo editor)."""

    def setUp(self):
        from servicios.models import Metodo, Norma
        self.user = User.objects.create_superuser('jefe.pl', 'j@x.pe', 'x')
        self.client.force_login(self.user)
        self.norma = Norma.objects.create(codigo='ASTM C39/C39M-24', nombre='Compresión de cilindros')
        self.metodo = Metodo.objects.create(codigo='M-01', nombre='Método uno')
        self.servicio = Servicio.objects.create(codigo_facturacion='PL1', nombre='Compresión de probetas',
                                                norma=self.norma, metodo=self.metodo, precio_base=Decimal('25'))

    def guardar(self, **extra):
        import json
        detalles = [
            {'tipo_fila': 'categoria', 'descripcion_especifica': 'CONCRETO'},
            {'tipo_fila': 'servicio', 'servicio_id': self.servicio.pk, 'cantidad': 2, 'precio_unitario': 25,
             'norma_id': self.norma.pk, 'metodo_id': self.metodo.pk, 'unidad_medida': 'Ensayo'},
        ]
        datos = {'nombre': 'Plantilla de prueba', 'asunto_servicio': 'Compresión', 'forma_pago': 'Contado',
                 'tiempo_entrega': '5', 'activo': 'True', 'detalles_json': json.dumps(detalles), 'condiciones_json': '[]'}
        datos.update(extra)
        return self.client.post(reverse('servicios:crear_plantilla'), datos, HTTP_X_REQUESTED_WITH='XMLHttpRequest')

    def test_la_pantalla_usa_pills_modal_y_el_mismo_script(self):
        r = self.client.get(reverse('servicios:crear_plantilla'))
        self.assertEqual(r.status_code, 200)
        for esperado in ('class="cot-tabs"', 'data-tab="contenido"', 'id="modalDetalle"', 'Detalle de la plantilla',
                         'id="btn-agregar-detalle"', 'js/cotizacion-config.js', 'esPlantilla: true',
                         'BorradorLocal.iniciar', 'id="cotizacion-form"'):
            self.assertContains(r, esperado)
        # El panel de selección antiguo ya no está en la página.
        self.assertNotContains(r, 'toggleRegistroPanel')
        self.assertNotContains(r, 'acordeon_plantilla.js')

    def test_la_cotizacion_sigue_con_su_modal(self):
        r = self.client.get(reverse('servicios:crear_cotizacion'))
        self.assertContains(r, 'Detalle de la cotización')
        self.assertContains(r, 'id="modalDetalle"')

    def test_guarda_por_fetch_con_la_norma_y_el_metodo_por_codigo(self):
        from servicios.models import PlantillaCotizacion, PlantillaDetalle
        r = self.guardar()
        self.assertEqual(r.status_code, 200, r.content)
        self.assertEqual(r.json()['status'], 'success')
        self.assertIn('/servicios/plantillas/', r.json()['redirect_url'])
        detalle = PlantillaDetalle.objects.get(grupo__plantilla__nombre_plantilla='Plantilla de prueba')
        self.assertEqual(detalle.norma_manual, 'ASTM C39/C39M-24')
        self.assertEqual(detalle.metodo_manual, 'M-01')
        self.assertEqual(detalle.cantidad, 2)
        self.assertEqual(PlantillaCotizacion.objects.count(), 1)

    def test_un_error_responde_json_sin_recargar_y_sin_guardar_a_medias(self):
        from servicios.models import PlantillaCotizacion
        r = self.guardar(detalles_json='{no es json')
        self.assertEqual(r.status_code, 400)
        self.assertEqual(r.json()['status'], 'error')
        self.assertTrue(r.json()['message'])
        self.assertEqual(PlantillaCotizacion.objects.count(), 0)

    def test_al_editar_carga_los_items_con_la_norma_para_mostrar(self):
        import json
        from servicios.models import PlantillaCotizacion
        self.guardar()
        plantilla = PlantillaCotizacion.objects.get()
        r = self.client.get(reverse('servicios:editar_plantilla', args=[plantilla.pk]))
        self.assertEqual(r.status_code, 200)
        items = json.loads(r.context['detalles_cotizacion_json'])
        servicio = next(i for i in items if i['tipo_fila'] == 'servicio')
        self.assertEqual(servicio['norma_nombre'], 'ASTM C39/C39M-24 / M-01')
        self.assertEqual(servicio['norma_id'], self.norma.pk)

    def test_plantillas_guardadas_antes_traen_norma_y_metodo_juntos(self):
        import json
        from servicios.models import PlantillaCotizacion, PlantillaDetalle, PlantillaGrupo
        p = PlantillaCotizacion.objects.create(nombre_plantilla='Vieja', asunto_referencial='x')
        g = PlantillaGrupo.objects.create(plantilla=p, nombre_grupo='ENSAYOS DE LABORATORIO', orden=0)
        PlantillaDetalle.objects.create(grupo=g, servicio=self.servicio, norma_manual='ASTM C39 / M-01',
                                        descripcion_especifica='x', precio_unitario=Decimal('10'))
        r = self.client.get(reverse('servicios:editar_plantilla', args=[p.pk]))
        servicio = json.loads(r.context['detalles_cotizacion_json'])[0]
        self.assertEqual(servicio['norma_nombre'], 'ASTM C39 / M-01')  # no repite el método
