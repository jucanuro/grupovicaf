"""Formato de registro de compresión en papel (versión 09) pasado al sistema:
verificaciones, defectos a-e, accesorios y comprobación funcional de equipos."""
from decimal import Decimal

from django.test import SimpleTestCase
from django.urls import reverse

from proyectos.calculos_compresion import verificar_diametro
from proyectos.informe_compresion import exportar_excel
from proyectos.models import Equipo, ResultadoEnsayo, SesionEnsayo
from proyectos.test_compresion import CompresionBase, TerminarTests


class VerificarDiametroTests(SimpleTestCase):

    def test_hoja_de_ejemplo_cumple(self):
        # Las dos probetas de la hoja escaneada: 97,42 / 99,26 y 96,62 / 98,24.
        self.assertEqual(verificar_diametro(Decimal('97.42'), Decimal('99.26')), (Decimal('1.89'), True))
        self.assertEqual(verificar_diametro(Decimal('96.62'), Decimal('98.24')), (Decimal('1.68'), True))

    def test_mas_de_dos_por_ciento_no_cumple(self):
        self.assertEqual(verificar_diametro(100, 103), (Decimal('3.00'), False))

    def test_sin_datos(self):
        self.assertIsNone(verificar_diametro(None, 100))


class RegistroProbetaTests(TerminarTests):

    def test_guarda_verificaciones_defectos_y_video(self):
        self.client.force_login(self.user_tec)
        self.subir_las_cinco(self.mia)
        self.client.post(self.url_registro(self.mia), {
            'accion': 'terminar', 'fecha_ensayo': self._ayer(), **self.MEDIDAS_P1,
            'verif_planitud': '0', 'tipos_defecto': ['c', 'a', 'x'], 'video_grabado': '1',
        })
        e = ResultadoEnsayo.objects.get(detalle=self.mia)
        self.assertTrue(e.terminado)
        self.assertTrue(e.verif_perpendicularidad)
        self.assertFalse(e.verif_planitud)
        self.assertEqual(e.tipos_defecto, 'a,c')
        self.assertEqual(e.defectos_texto, '(a) Espécimen mal moldeado; (c) Dimensiones atípicas')
        self.assertTrue(e.video_grabado)

    def _ayer(self):
        from datetime import date, timedelta
        return (date.today() - timedelta(days=1)).isoformat()

    def test_sin_perpendicularidad_ni_planitud_no_termina(self):
        self.client.force_login(self.user_tec)
        self.subir_las_cinco(self.mia)
        r = self.terminar(verif_perpendicularidad='', verif_planitud='')
        self.assertFalse(ResultadoEnsayo.objects.get(detalle=self.mia).terminado)
        mensajes = [str(m) for m in r.wsgi_request._messages]
        self.assertTrue(any('perpendicularidad' in m and 'planitud' in m for m in mensajes))

    def test_otros_exige_el_detalle(self):
        self.client.force_login(self.user_tec)
        self.subir_las_cinco(self.mia)
        self.terminar(tipos_defecto='e', defectos='')
        self.assertFalse(ResultadoEnsayo.objects.get(detalle=self.mia).terminado)
        self.terminar(tipos_defecto='e', defectos='Burbuja en la cara superior')
        e = ResultadoEnsayo.objects.get(detalle=self.mia)
        self.assertTrue(e.terminado)
        self.assertEqual(e.defectos_texto, 'Otros: Burbuja en la cara superior')

    def test_pantalla_muestra_el_formato(self):
        self.client.force_login(self.user_tec)
        r = self.client.get(self.url_registro(self.mia))
        self.assertContains(r, 'name="verif_perpendicularidad"')
        self.assertContains(r, 'name="tipos_defecto" value="e"')
        self.assertContains(r, 'data-verif-diametro')

    def test_excel_lleva_las_columnas_nuevas(self):
        from io import BytesIO
        from openpyxl import load_workbook
        self.client.force_login(self.user_tec)
        self.subir_las_cinco(self.mia)
        self.terminar(tipos_defecto='d')
        hoja = load_workbook(BytesIO(exportar_excel(ResultadoEnsayo.objects.filter(detalle=self.mia)))).active
        fila = {hoja.cell(1, c).value: hoja.cell(2, c).value for c in range(1, hoja.max_column + 1)}
        self.assertEqual(fila['Neoprenos'], 'VCF-EQ-NEO-079')
        self.assertEqual(fila['Usos neopreno'], '59-60')
        self.assertEqual(fila['Diámetro ≤ 2 %'], 'Cumple')
        self.assertEqual(fila['Planitud ≤ 0,05 mm'], 'Cumple')
        self.assertEqual(fila['Defectos'], '(d) Caras irregulares')


class SesionFormatoTests(CompresionBase):

    def test_guarda_accesorios_y_comprobacion(self):
        self.client.force_login(self.user_tec)
        self.abrir_sesion()
        s = SesionEnsayo.abierta_de(self.tecnico)
        self.assertEqual(s.neopreno.codigo, 'VCF-EQ-NEO-079')
        self.assertEqual(s.anillos.codigo, 'VCF-EQ-ARET-002')
        self.assertEqual(s.neopreno_usos, '59-60')
        self.assertIs(s.comprobacion['prensa_fugas'], False)
        self.assertTrue(all(i['conforme'] for i in s.comprobacion_items()))
        nombres = [n for n, _ in s.equipos_usados()]
        self.assertEqual(nombres[:5], ['Prensa', 'Vernier', 'Balanza', 'Termohigrómetro', 'Anillos retenedores'])
        self.assertIn(('Neoprenos', 'VCF-EQ-NEO-079 (usos: 59-60)'), s.equipos_usados())

    def test_equipo_que_no_pasa_la_comprobacion_no_abre_sesion(self):
        self.client.force_login(self.user_tec)
        r = self.abrir_sesion(comp_prensa_fugas='1')
        self.assertContains(r, 'Prensa no pasa la comprobación')
        self.assertIsNone(SesionEnsayo.abierta_de(self.tecnico))

    def test_falta_responder_la_comprobacion(self):
        self.client.force_login(self.user_tec)
        r = self.abrir_sesion(comp_vernier_escalas='')
        self.assertContains(r, 'Responde Sí o No.')
        self.assertIsNone(SesionEnsayo.abierta_de(self.tecnico))

    def test_sesion_anterior_sin_accesorios_sigue_funcionando(self):
        self.client.force_login(self.user_tec)
        self.abrir_sesion()
        s = SesionEnsayo.abierta_de(self.tecnico)
        SesionEnsayo.objects.filter(pk=s.pk).update(anillos=None, neopreno=None, neopreno_usos='', comprobacion={})
        s.refresh_from_db()
        self.assertEqual(len(s.equipos_usados()), 6)
        self.assertEqual(s.comprobacion_items(), [])

    def test_pantalla_de_sesion_pide_la_comprobacion(self):
        self.client.force_login(self.user_tec)
        r = self.client.get(reverse('proyectos:abrir_sesion_ensayo'))
        self.assertContains(r, 'Comprobación funcional de equipos')
        self.assertContains(r, 'name="comp_prensa_fugas"')
        self.assertContains(r, 'name="neopreno_usos"')
        self.assertTrue(Equipo.objects.filter(tipo=Equipo.TIPO_ANILLOS).exists())
