"""URLconf del host del correo (email.<dominio>).

Lo activa correo.middleware.CorreoHostMiddleware en el rol 'lab'. No incluye
admin/ ni ninguna ruta del LIMS.
"""
from django.urls import path

from correo import views_correo as v
from correo import views_firmas as f
from correo import views_redactar as r
from correo import views_admin as ad

urlpatterns = [
    # Sesión
    path('entrar/', v.entrar, name='entrar'),
    path('login/', v.ir_al_login, name='login'),
    path('salir/', v.salir, name='salir'),

    # Bandejas y carpetas
    path('', v.bandeja, name='bandeja'),
    path('c/<slug:cuenta>/bandeja/', v.bandeja, name='bandeja_cuenta'),
    path('c/<slug:cuenta>/carpeta/<int:carpeta_id>/', v.carpeta_vista, name='carpeta'),
    path('c/<slug:cuenta>/carpetas/nueva/', v.carpeta_nueva, name='carpeta_nueva'),
    path('c/<slug:cuenta>/carpeta/<int:carpeta_id>/eliminar/', v.carpeta_eliminar, name='carpeta_eliminar'),

    # Lectura y acciones
    path('m/<int:pk>/', v.mensaje_completo, name='mensaje'),
    path('m/<int:pk>/cuerpo/', v.mensaje_cuerpo, name='mensaje_cuerpo'),
    path('m/<int:pk>/imprimir/', v.imprimir, name='imprimir'),
    path('m/<int:pk>/reintentar/', r.reintentar, name='reintentar'),
    path('acciones/', v.acciones, name='acciones'),
    path('h/<int:pk>/asignar/', v.asignar, name='asignar'),
    path('h/<int:pk>/atendido/', v.atendido, name='atendido'),
    path('a/<str:token>/', v.adjunto, name='adjunto'),

    # Búsqueda e historial
    path('buscar/', v.buscar, name='buscar'),
    path('api/buscar/', v.api_buscar, name='api_buscar'),
    path('contacto/', v.contacto, name='contacto'),

    # Redactar
    path('redactar/', r.redactar, name='redactar'),
    path('redactar/<int:pk>/', r.borrador, name='borrador'),
    path('redactar/<int:pk>/guardar/', r.guardar, name='borrador_guardar'),
    path('redactar/<int:pk>/enviar/', r.enviar, name='borrador_enviar'),
    path('redactar/<int:pk>/descartar/', r.descartar, name='borrador_descartar'),
    path('redactar/<int:pk>/adjuntos/', r.adjuntos, name='borrador_adjuntos'),
    path('redactar/<int:pk>/adjuntos/<int:adjunto_id>/quitar/', r.adjunto_quitar, name='borrador_adjunto_quitar'),
    path('redactar/<int:pk>/cotizacion/', r.adjuntar_cotizacion_vista, name='borrador_cotizacion'),
    path('api/contactos/', r.api_contactos, name='api_contactos'),
    path('api/cotizaciones/', r.api_cotizaciones, name='api_cotizaciones'),

    # Firmas
    path('firmas/', f.firmas, name='firmas'),
    path('firmas/nueva/', f.firma_editar, name='firma_nueva'),
    path('firmas/<int:pk>/', f.firma_editar, name='firma_editar'),
    path('firmas/<int:pk>/eliminar/', f.firma_eliminar, name='firma_eliminar'),
    path('firmas/<int:pk>/vista/', f.firma_vista, name='firma_vista'),

    # Administrar cuentas y accesos (Paso 3)
    path('administrar/', ad.lista, name='admin_cuentas'),
    path('administrar/nueva/', ad.crear, name='admin_cuenta_crear'),
    path('administrar/<slug:slug>/', ad.detalle, name='admin_cuenta'),
    path('administrar/<slug:slug>/guardar/', ad.guardar, name='admin_cuenta_guardar'),
    path('administrar/<slug:slug>/accesos/', ad.acceso_dar, name='admin_acceso_dar'),
    path('administrar/<slug:slug>/accesos/<int:pk>/rol/', ad.acceso_rol, name='admin_acceso_rol'),
    path('administrar/<slug:slug>/accesos/<int:pk>/quitar/', ad.acceso_quitar, name='admin_acceso_quitar'),
]
