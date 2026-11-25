"""Galería de fotos del ensayo general: varias fotos que se agregan, se quitan
con trazabilidad y al menos una para terminar."""
from datetime import date, timedelta

from django.urls import reverse

from proyectos.models import CambioResultado, FotoEnsayo, ResultadoEnsayo
from proyectos.test_compresion import CompresionBase, jpeg
from proyectos.test_informe_compresion import hoja


class GaleriaGeneralTests(CompresionBase):

    def subir_general(self, ancho=1200, alto=500):
        return self.subir(self.proctor, 'general', jpeg(ancho, alto))

    def test_agrega_varias_fotos_sin_recortar(self):
        self.client.force_login(self.user_tec)
        for _ in range(3):
            r = self.subir_general()
            self.assertEqual(r.status_code, 200, r.content)
        fotos = FotoEnsayo.objects.filter(ensayo__detalle=self.proctor)
        self.assertEqual(fotos.count(), 3)
        # Conserva su proporción (1200x500), no se recorta a 4:3.
        self.assertEqual((fotos.first().ancho, fotos.first().alto), (1200, 500))
        self.assertEqual(r.json()['total'], 3)

    def test_tope_de_fotos(self):
        self.client.force_login(self.user_tec)
        for _ in range(FotoEnsayo.MAX_FOTOS_GENERAL):
            self.subir_general(300, 200)
        self.assertEqual(self.subir_general(300, 200).status_code, 400)

    def test_compresion_no_admite_galeria(self):
        self.client.force_login(self.user_tec)
        self.assertEqual(self.subir(self.mia, 'general', jpeg(300, 200)).status_code, 404)

    def test_quitar_queda_en_trazabilidad(self):
        self.client.force_login(self.user_tec)
        foto_id = self.subir_general().json()['id']
        r = self.client.post(reverse('proyectos:borrar_foto_compresion', args=[foto_id]))
        self.assertEqual(r.status_code, 200)
        self.assertFalse(FotoEnsayo.objects.filter(pk=foto_id).exists())
        self.assertTrue(CambioResultado.objects.filter(resultado__detalle=self.proctor, nuevo='(borrada)').exists())

    def test_otro_tecnico_no_quita(self):
        self.client.force_login(self.user_tec)
        foto_id = self.subir_general().json()['id']
        self.client.force_login(self.user_otro)
        self.assertEqual(self.client.post(reverse('proyectos:borrar_foto_compresion', args=[foto_id])).status_code, 404)

    def test_terminar_pide_al_menos_una_foto(self):
        self.client.force_login(self.user_tec)
        datos = {'accion': 'terminar', 'fecha_ensayo': (date.today() - timedelta(days=1)).isoformat(),
                 'resumen': 'Resumen', 'hoja_calculo': hoja()}
        r = self.client.post(self.url_registro(self.proctor), datos, follow=True)
        self.assertContains(r, 'al menos una foto')
        self.subir_general()
        datos['hoja_calculo'] = hoja()
        self.client.post(self.url_registro(self.proctor), datos)
        self.assertTrue(ResultadoEnsayo.objects.get(detalle=self.proctor).terminado)

    def test_pantalla_muestra_la_galeria_y_tomar_foto(self):
        self.client.force_login(self.user_tec)
        self.subir_general()
        r = self.client.get(self.url_registro(self.proctor))
        self.assertContains(r, 'data-galeria-lista')
        self.assertContains(r, 'data-galeria-archivos')
        self.assertContains(r, 'multiple')
        self.assertContains(r, 'Tomar foto')
        self.assertContains(r, 'camara_foto.js')
        self.assertContains(r, 'data-borrar=')
