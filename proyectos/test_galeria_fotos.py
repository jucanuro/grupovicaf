"""Fotos del ensayo (HU-LIMS-36): todo ensayo lleva las mismas 6 fotos (2 antes, 2 durante, 2 después).
La galería libre del ensayo general se retiró: solo se muestra si el ensayo ya tenía fotos así."""
from datetime import date, timedelta

from django.urls import reverse

from proyectos.models import CambioResultado, FotoEnsayo, ResultadoEnsayo
from proyectos.test_compresion import CompresionBase, jpeg


class FotosDelEnsayoGeneralTests(CompresionBase):

    def subir_todas(self, detalle):
        for tipo in FotoEnsayo.TIPOS_COMPRESION:
            ancho, alto = FotoEnsayo.PROPORCIONES[tipo]
            self.assertEqual(self.subir(detalle, tipo, jpeg(ancho * 100, alto * 100)).status_code, 200)

    def test_el_ensayo_general_tambien_lleva_las_seis_fotos_en_orden(self):
        self.client.force_login(self.user_tec)
        html = self.client.get(self.url_registro(self.proctor)).content.decode()
        orden = ['data-slot="antes"', 'data-slot="antes_pizarra"', 'data-slot="durante"',
                 'data-slot="carga"', 'data-slot="despues"', 'data-slot="despues_pizarra"']
        posiciones = [html.index(x) for x in orden]
        self.assertEqual(posiciones, sorted(posiciones))
        self.assertEqual(html.count('data-slot='), 6)

    def test_la_galeria_libre_ya_no_se_admite(self):
        self.client.force_login(self.user_tec)
        self.assertEqual(self.subir(self.proctor, 'general', jpeg(300, 200)).status_code, 404)

    def test_terminar_pide_las_seis_fotos(self):
        self.client.force_login(self.user_tec)
        datos = {'accion': 'terminar', 'fecha_ensayo': (date.today() - timedelta(days=1)).isoformat(), 'resumen': 'Resumen'}
        r = self.client.post(self.url_registro(self.proctor), datos, follow=True)
        self.assertContains(r, 'la foto «Antes del ensayo»')
        self.subir_todas(self.proctor)
        self.client.post(self.url_registro(self.proctor), datos)
        self.assertTrue(ResultadoEnsayo.objects.get(detalle=self.proctor).terminado)

    def test_una_foto_se_reemplaza_y_queda_en_la_trazabilidad(self):
        self.client.force_login(self.user_tec)
        self.subir(self.proctor, 'antes', jpeg(400, 700))
        self.subir(self.proctor, 'antes', jpeg(400, 700))
        self.assertEqual(FotoEnsayo.objects.filter(ensayo__detalle=self.proctor, tipo='antes').count(), 1)
        self.assertTrue(CambioResultado.objects.filter(resultado__detalle=self.proctor, campo='foto').exists())

    def test_las_seis_fotos_no_se_borran(self):
        self.client.force_login(self.user_tec)
        self.subir(self.proctor, 'antes', jpeg(400, 700))
        foto_id = FotoEnsayo.objects.get(ensayo__detalle=self.proctor, tipo='antes').pk
        r = self.client.post(reverse('proyectos:borrar_foto_compresion', args=[foto_id]))
        self.assertEqual(r.status_code, 400)
        self.assertTrue(FotoEnsayo.objects.filter(pk=foto_id).exists())

    def test_las_fotos_de_la_galeria_vieja_se_siguen_viendo(self):
        self.client.force_login(self.user_tec)
        ensayo = ResultadoEnsayo.crear_para(self.proctor)
        antigua = FotoEnsayo(ensayo=ensayo, tipo='general')
        from django.core.files.base import ContentFile
        antigua.imagen.save('vieja.jpg', ContentFile(jpeg(300, 200).read() if hasattr(jpeg(300, 200), 'read') else jpeg(300, 200)), save=True)
        html = self.client.get(self.url_registro(self.proctor)).content.decode()
        self.assertIn('Fotos anteriores del ensayo', html)
