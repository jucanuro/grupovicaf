"""App instalable (PWA) del correo: manifiesto y service worker, servidos desde la raíz del host.

El service worker NO guarda correos ni páginas en caché (son datos privados):
solo existe para que el navegador permita instalar la app y para mostrar un
aviso si no hay conexión.
"""
from django.http import HttpResponse, JsonResponse
from django.templatetags.static import static
from django.views.decorators.cache import cache_control
from django.views.decorators.http import require_GET

COLOR_TEMA = '#1D4ED8'

SERVICE_WORKER = """\
/* Service worker del correo VICAF: sin caché de contenido privado. */
self.addEventListener('install', function () { self.skipWaiting(); });
self.addEventListener('activate', function (e) { e.waitUntil(self.clients.claim()); });
self.addEventListener('fetch', function (e) {
    if (e.request.mode !== 'navigate') { return; }
    e.respondWith(fetch(e.request).catch(function () {
        return new Response(
            '<!doctype html><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">' +
            '<title>Sin conexión</title><body style="font-family:sans-serif;text-align:center;padding:3rem 1rem">' +
            '<h1>Sin conexión</h1><p>No se puede abrir el correo ahora. Revisa tu internet e inténtalo de nuevo.</p>',
            { status: 503, headers: { 'Content-Type': 'text/html; charset=utf-8' } });
    }));
});
"""


@require_GET
@cache_control(max_age=3600)
def manifiesto(request):
    datos = {
        'name': 'Correo VICAF',
        'short_name': 'Correo VICAF',
        'description': 'Correo corporativo de Grupo VICAF.',
        'lang': 'es',
        'id': '/',
        'start_url': '/',
        'scope': '/',
        'display': 'standalone',
        'background_color': '#FFFFFF',
        'theme_color': COLOR_TEMA,
        'icons': [
            {'src': static('correo/pwa/icono-192.png'), 'sizes': '192x192', 'type': 'image/png', 'purpose': 'any'},
            {'src': static('correo/pwa/icono-512.png'), 'sizes': '512x512', 'type': 'image/png', 'purpose': 'any'},
            {'src': static('correo/pwa/icono-512-maskable.png'), 'sizes': '512x512', 'type': 'image/png',
             'purpose': 'maskable'},
        ],
    }
    return JsonResponse(datos, content_type='application/manifest+json')


@require_GET
@cache_control(no_cache=True)
def service_worker(request):
    return HttpResponse(SERVICE_WORKER, content_type='application/javascript')
