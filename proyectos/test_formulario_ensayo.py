"""Formulario de resultados configurable por servicio (HU-LIMS-36, REQ-LIMS-163 a 170)."""
from datetime import date, timedelta

from django.core.exceptions import ValidationError
from django.test import SimpleTestCase
from django.urls import reverse

from proyectos import formularios_ensayo as fe
from proyectos.models import CambioResultado, FotoEnsayo, PlantillaFormulario, ResultadoEnsayo
from proyectos.test_compresion import CompresionBase, jpeg

CAMPOS = [
    {'clave': 'humedad', 'etiqueta': 'Contenido de humedad', 'tipo': 'numero', 'unidad': '%', 'requerido': True, 'grupo': 'Resultados'},
    {'clave': 'masa_seca', 'etiqueta': 'Masa seca', 'tipo': 'numero', 'unidad': 'g', 'grupo': 'Resultados'},
    {'clave': 'secado', 'etiqueta': 'Secado a masa constante', 'tipo': 'cumple', 'requerido': True, 'grupo': 'Verificaciones'},
]


class ReglasDeCamposTests(SimpleTestCase):
    def test_valida_la_lista_de_campos(self):
        self.assertEqual(fe.validar_campos(CAMPOS), [])
        self.assertTrue(fe.validar_campos([{'clave': 'Mal Clave', 'etiqueta': 'x', 'tipo': 'numero'}]))
        self.assertTrue(fe.validar_campos([{'clave': 'a', 'etiqueta': 'x', 'tipo': 'raro'}]))
        self.assertTrue(fe.validar_campos([{'clave': 'a', 'etiqueta': 'x', 'tipo': 'seleccion'}]))
        self.assertTrue(fe.validar_campos(CAMPOS + [CAMPOS[0]]))

    def test_lee_y_muestra_cada_tipo(self):
        num = {'etiqueta': 'N', 'tipo': 'numero', 'unidad': '%'}
        self.assertEqual(fe.leer_valor(num, '12,50'), ('12.5', None))
        self.assertIsNotNone(fe.leer_valor(num, 'abc')[1])
        self.assertEqual(fe.leer_valor(num, ''), (None, None))
        self.assertEqual(fe.mostrar(num, '12.5'), '12.5 %')
        cump = {'etiqueta': 'C', 'tipo': 'cumple'}
        self.assertEqual(fe.mostrar(cump, 'no_cumple'), 'No cumple')
        self.assertIsNotNone(fe.leer_valor(cump, 'quizas')[1])
        fecha = {'etiqueta': 'F', 'tipo': 'fecha'}
        self.assertIsNotNone(fe.leer_valor(fecha, '2999-01-01')[1])
        sel = {'etiqueta': 'S', 'tipo': 'seleccion', 'opciones': ['A', 'B']}
        self.assertEqual(fe.leer_valor(sel, 'A'), ('A', None))
        self.assertIsNotNone(fe.leer_valor(sel, 'Z')[1])

    def test_faltantes_son_solo_los_obligatorios(self):
        esquema = {'campos': fe.normalizar_campos(CAMPOS)}
        self.assertEqual(fe.faltantes(esquema, {}), ['Contenido de humedad', 'Secado a masa constante'])
        self.assertEqual(fe.faltantes(esquema, {'humedad': '8', 'secado': 'cumple'}), [])


class FormularioPorServicioTests(CompresionBase):
    def setUp(self):
        super().setUp()
        self.plantilla = PlantillaFormulario.objects.create(
            nombre='Humedad', campos=CAMPOS, instrucciones='Pesa dos veces.',
        )
        self.plantilla.servicios.add(self.proctor.servicio_cotizado.servicio)
        self.client.force_login(self.user_tec)

    def guardar(self, **datos):
        base = {'accion': 'guardar', 'fecha_ensayo': (date.today() - timedelta(days=1)).isoformat()}
        base.update(datos)
        return self.client.post(self.url_registro(self.proctor), base)

    def subir_seis(self):
        for tipo in FotoEnsayo.TIPOS_COMPRESION:
            ancho, alto = FotoEnsayo.PROPORCIONES[tipo]
            self.subir(self.proctor, tipo, jpeg(ancho * 100, alto * 100))

    def test_la_pantalla_dibuja_los_campos_del_servicio_y_agrupa(self):
        html = self.client.get(self.url_registro(self.proctor)).content.decode()
        for marca in ('name="dato_humedad"', 'name="dato_masa_seca"', 'name="dato_secado"', 'Resultados', 'Verificaciones',
                      'Pesa dos veces.', 'data-requerido'):
            self.assertIn(marca, html)
        self.assertNotIn('name="resumen"', html)

    def test_guarda_los_datos_y_el_ensayo_recuerda_su_esquema(self):
        self.guardar(dato_humedad='12,5', dato_secado='cumple')
        e = ResultadoEnsayo.objects.get(detalle=self.proctor)
        self.assertEqual(e.datos, {'humedad': '12.5', 'secado': 'cumple'})
        self.assertEqual([c['clave'] for c in e.esquema['campos']], ['humedad', 'masa_seca', 'secado'])
        # Si la plantilla cambia después, el ensayo ya creado conserva su formulario.
        self.plantilla.campos = CAMPOS[:1]
        self.plantilla.save()
        e.refresh_from_db()
        self.assertEqual(len(e.esquema['campos']), 3)

    def test_no_termina_sin_obligatorios_ni_fotos(self):
        self.guardar(dato_humedad='12', accion='terminar')
        e = ResultadoEnsayo.objects.get(detalle=self.proctor)
        faltan = e.faltantes_para_terminar()
        self.assertIn('«Secado a masa constante»', faltan)
        self.assertNotIn('«Contenido de humedad»', faltan)
        self.assertTrue(any('Antes del ensayo' in f for f in faltan))
        self.assertFalse(e.terminado)

    def test_termina_con_todo_y_sin_resumen_ni_hoja(self):
        self.subir_seis()
        self.guardar(dato_humedad='12', dato_secado='cumple', accion='terminar')
        e = ResultadoEnsayo.objects.get(detalle=self.proctor)
        self.assertTrue(e.terminado)
        self.assertEqual(e.resumen, '')
        self.assertFalse(e.hoja_calculo)

    def test_un_valor_invalido_se_rechaza_con_mensaje(self):
        r = self.guardar(dato_humedad='mucha', follow=True) if False else self.client.post(
            self.url_registro(self.proctor),
            {'accion': 'guardar', 'fecha_ensayo': (date.today() - timedelta(days=1)).isoformat(), 'dato_humedad': 'mucha'},
            follow=True,
        )
        self.assertContains(r, 'debe ser un número')

    def test_corregir_un_dato_guarda_valor_anterior_quien_y_cuando(self):
        self.guardar(dato_humedad='12')
        self.guardar(dato_humedad='13')
        c = CambioResultado.objects.get(resultado__detalle=self.proctor, campo='dato:humedad')
        self.assertEqual((c.etiqueta, c.anterior, c.nuevo, c.usuario), ('Contenido de humedad', '12 %', '13 %', self.user_tec))
        self.assertIsNotNone(c.registrado_en)

    def test_el_autoguardado_tambien_guarda_los_campos(self):
        self.client.post(self.url_registro(self.proctor), {'accion': 'autoguardar', 'dato_humedad': '9,1'})
        self.assertEqual(ResultadoEnsayo.objects.get(detalle=self.proctor).datos, {'humedad': '9.1'})

    def test_las_fotos_antes_de_llenar_el_formulario_crean_el_ensayo_con_su_esquema(self):
        self.subir(self.proctor, 'antes', jpeg(400, 700))
        e = ResultadoEnsayo.objects.get(detalle=self.proctor)
        self.assertEqual(len(e.esquema['campos']), 3)

    def test_la_revision_y_el_informe_leen_lo_registrado(self):
        self.guardar(dato_humedad='12', dato_secado='cumple')
        e = ResultadoEnsayo.objects.get(detalle=self.proctor)
        self.assertIn(('Resultados', 'Contenido de humedad', '12 %'), e.filas_formulario)
        self.assertIn(('Verificaciones', 'Secado a masa constante', 'Cumple'), e.filas_formulario)

    def test_sin_plantilla_usa_el_formulario_basico_con_resumen(self):
        self.plantilla.activo = False
        self.plantilla.save()
        html = self.client.get(self.url_registro(self.proctor)).content.decode()
        self.assertIn('name="resumen"', html)
        self.assertNotIn('name="dato_humedad"', html)

    def test_la_plantilla_rechaza_campos_mal_definidos(self):
        p = PlantillaFormulario(nombre='Mala', campos=[{'clave': 'X Y', 'etiqueta': 'a', 'tipo': 'numero'}])
        with self.assertRaises(ValidationError):
            p.full_clean()


class FormularioCompletoParaTodosTests(CompresionBase):
    """HU-LIMS-37: el FOR-009 completo sirve a todo ensayo; en los que no son compresión se llena lo que corresponda."""

    def setUp(self):
        super().setUp()
        self.client.force_login(self.user_tec)

    def subir_seis(self, detalle):
        for tipo in FotoEnsayo.TIPOS_COMPRESION:
            ancho, alto = FotoEnsayo.PROPORCIONES[tipo]
            self.subir(detalle, tipo, jpeg(ancho * 100, alto * 100))

    def test_un_ensayo_general_muestra_todas_las_secciones_del_for_009(self):
        html = self.client.get(self.url_registro(self.proctor)).content.decode()
        for marca in ('data-datos-cliente', 'data-medidas', 'data-paso-carga', 'name="carga_kn"', 'name="tipo_fractura"',
                      'name="tipos_defecto"', 'name="verif_planitud"', 'data-sesion-card', 'data-datos-generales'):
            self.assertIn(marca, html)

    def test_en_un_ensayo_general_nada_del_for_009_es_obligatorio(self):
        self.client.post(self.url_registro(self.proctor), {
            'accion': 'guardar', 'fecha_ensayo': (date.today() - timedelta(days=1)).isoformat(), 'masa_g': '1500',
        })
        e = ResultadoEnsayo.objects.get(detalle=self.proctor)
        faltan = e.faltantes_para_terminar()
        self.assertTrue(all('foto' in f for f in faltan), faltan)
        self.assertEqual(str(e.masa_g), '1500.0')

    def test_termina_solo_con_fecha_y_las_seis_fotos(self):
        self.subir_seis(self.proctor)
        r = self.client.post(self.url_registro(self.proctor), {
            'accion': 'terminar', 'fecha_ensayo': (date.today() - timedelta(days=1)).isoformat(),
        })
        self.assertTrue(ResultadoEnsayo.objects.get(detalle=self.proctor).terminado, r.status_code)

    def test_la_compresion_sigue_exigiendo_sus_medidas(self):
        self.subir_seis(self.mia)
        self.client.post(self.url_registro(self.mia), {
            'accion': 'terminar', 'fecha_ensayo': (date.today() - timedelta(days=1)).isoformat(),
        })
        self.assertFalse(ResultadoEnsayo.objects.get(detalle=self.mia).terminado)

    def test_el_autoguardado_guarda_medidas_de_un_ensayo_general(self):
        self.client.post(self.url_registro(self.proctor), {
            'accion': 'autoguardar', 'masa_g': '2000', 'tipo_fractura': '3', 'tipos_defecto': ['a', 'b'],
        })
        e = ResultadoEnsayo.objects.get(detalle=self.proctor)
        self.assertEqual((str(e.masa_g), e.tipo_fractura, e.tipos_defecto), ('2000.0', 3, 'a,b'))

    def test_el_panel_de_fotos_trae_el_asistente_y_grupos_plegables(self):
        html = self.client.get(self.url_registro(self.proctor)).content.decode()
        for marca in ('data-asistente', 'data-asist-camara', 'capture="environment"', 'data-asist-archivos',
                      'class="grupo-fotos"', 'data-asist-webcam'):
            self.assertIn(marca, html)
        self.assertEqual(html.count('class="grupo-fotos"'), 3)


class RegistroPantallaCompletaTests(CompresionBase):
    """HU-LIMS-38: pantalla completa, sesión dentro del registro, requisitos y fotos sin botones por recuadro."""

    def setUp(self):
        super().setUp()
        self.client.force_login(self.user_tec)

    def test_la_pantalla_es_completa_con_requisitos_y_la_sesion_integrada(self):
        html = self.client.get(self.url_registro(self.mia)).content.decode()
        for marca in ('rs-completo', 'data-requisitos', 'data-sesion-card', 'data-abrir-sesion', 'id="form-sesion"',
                      'name="temperatura_inicial"', 'name="comp_', 'Para terminar este ensayo necesitas'):
            self.assertIn(marca, html)

    def test_los_recuadros_ya_no_tienen_botones_de_camara_ni_galeria(self):
        html = self.client.get(self.url_registro(self.mia)).content.decode()
        self.assertEqual(html.count('data-entrada'), 0)
        self.assertEqual(html.count('Repetir esta foto'), 6)
        self.assertNotIn('Galería</label>', html.replace('\n', ''))

    def datos_sesion(self):
        from proyectos.models import Equipo, SesionEnsayo
        datos = {'fecha': date.today().isoformat(), 'temperatura_inicial': '19.0', 'humedad_inicial': '66', 'neopreno_usos': '59-60'}
        for campo, tipo in SesionEnsayo.EQUIPOS + SesionEnsayo.ACCESORIOS:
            equipo = Equipo.disponibles(tipo, date.today()).first()
            datos[campo] = equipo.pk if equipo else ''
        for clave, _, _, esperado in SesionEnsayo.COMPROBACION:
            datos['comp_' + clave] = '1' if esperado else '0'
        return datos

    def test_abre_la_sesion_sin_salir_del_registro(self):
        from proyectos.models import SesionEnsayo
        r = self.client.post(reverse('proyectos:abrir_sesion_ensayo'), self.datos_sesion(), HTTP_X_REQUESTED_WITH='XMLHttpRequest')
        self.assertEqual(r.status_code, 200, r.content)
        self.assertTrue(r.json()['ok'])
        self.assertIn('Sesión del', r.json()['resumen'])
        self.assertEqual(SesionEnsayo.objects.count(), 1)
        html = self.client.get(self.url_registro(self.mia)).content.decode()
        self.assertNotIn('name="temperatura_inicial"', html)
        self.assertIn('Sesión abierta: este ensayo la usa al terminar', html)

    def test_una_sesion_invalida_devuelve_los_errores_en_json(self):
        from proyectos.models import SesionEnsayo
        datos = self.datos_sesion()
        datos['temperatura_inicial'] = '99'
        r = self.client.post(reverse('proyectos:abrir_sesion_ensayo'), datos, HTTP_X_REQUESTED_WITH='XMLHttpRequest')
        self.assertEqual(r.status_code, 400)
        self.assertFalse(r.json()['ok'])
        self.assertTrue(r.json()['errores'])
        self.assertEqual(SesionEnsayo.objects.count(), 0)

    def test_no_abre_una_segunda_sesion(self):
        self.client.post(reverse('proyectos:abrir_sesion_ensayo'), self.datos_sesion(), HTTP_X_REQUESTED_WITH='XMLHttpRequest')
        r = self.client.post(reverse('proyectos:abrir_sesion_ensayo'), self.datos_sesion(), HTTP_X_REQUESTED_WITH='XMLHttpRequest')
        self.assertEqual(r.status_code, 409)
