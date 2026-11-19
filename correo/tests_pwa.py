"""App instalable (PWA) del correo."""
import json

from django.urls import reverse

from .tests_plataforma import BasePlataforma


class PwaTests(BasePlataforma):
    def test_manifiesto_valido_y_sin_sesion(self):
        r = self.get('manifest')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r['Content-Type'], 'application/manifest+json')
        datos = json.loads(r.content)
        self.assertEqual(datos['display'], 'standalone')
        self.assertEqual(datos['start_url'], '/')
        tamanos = {(i['sizes'], i['purpose']) for i in datos['icons']}
        self.assertIn(('192x192', 'any'), tamanos)
        self.assertIn(('512x512', 'maskable'), tamanos)

    def test_service_worker_en_la_raiz_sin_guardar_correo(self):
        r = self.get('service_worker')
        self.assertEqual(r.status_code, 200)
        self.assertIn('javascript', r['Content-Type'])
        self.assertIn('no-cache', r['Cache-Control'])
        texto = r.content.decode()
        self.assertNotIn('caches.', texto)  # no se guarda contenido privado

    def test_las_paginas_del_correo_enlazan_el_manifiesto(self):
        self.entrar(self.gestor)
        html = self.get('bandeja').content.decode()
        self.assertIn('rel="manifest"', html)
        self.assertIn('correo/js/pwa.js', html)

    def test_pantallas_del_lims_no_cargan_la_pwa(self):
        # sin_acceso.html vive en el host del LIMS y extiende la misma base
        self.entrar(self.sin_modulo)
        r = self.client.get(reverse('correo:abrir'), HTTP_HOST='laboratorio.localhost', follow=False)
        self.assertNotIn(b'rel="manifest"', r.content)
