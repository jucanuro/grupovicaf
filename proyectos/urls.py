# proyectos/urls.py
from django.urls import path
from . import views
from . import views_compresion

app_name = 'proyectos'

urlpatterns = [
    # --- PROYECTOS Y API ---
    path('pendientes/', views.lista_proyectos_pendientes, name='lista_proyectos_pendientes'),
    path('api/cotizacion-detalles/<int:cotizacion_id>/', views.api_obtener_detalles_cotizacion, name='api_cotizacion_detalles'),
    path('tipo-muestra/crear-ajax/', views.crear_tipo_muestra_ajax, name='crear_tipo_muestra_ajax'),

    # --- RECEPCIÓN DE MUESTRAS ---
    path('recepciones/', views.RecepcionMuestraListView.as_view(), name='lista_recepciones'),
    path('recepcion/nueva/', views.gestionar_recepcion_muestra, name='crear_recepcion'),
    path('recepcion/nueva/<int:proyecto_id>/', views.gestionar_recepcion_muestra, name='crear_recepcion_desde_proyecto'),
    path('recepcion/editar/<int:pk>/', views.gestionar_recepcion_muestra, name='editar_recepcion'),
    path('recepcion/<int:recepcion_id>/muestras/', views.lista_muestras_recepcion, name='lista_muestras_recepcion'),
    path('recepcion/<int:recepcion_id>/pdf/', views.generar_pdf_recepcion, name='generar_pdf_recepcion'),
    path('recepcion/<int:recepcion_id>/whatsapp/', views.generar_y_enviar_whatsapp, name='enviar_recepcion_whatsapp'),

    # --- SOLICITUDES DE ENSAYO ---
    path('solicitudes/', views.lista_solicitudes, name='lista_solicitudes'),
    path('ensayo/nuevo/', views.gestionar_solicitud_ensayo, name='crear_solicitud'),
    path('ensayo/editar/<int:pk>/', views.gestionar_solicitud_ensayo, name='editar_solicitud'),
    path('ensayo/<int:solicitud_id>/pdf/', views.generar_pdf_ensayo, name='generar_pdf_ensayo'),
    path('solicitudes/estado/<int:pk>/<str:nuevo_estado>/', views.cambiar_estado_solicitud, name='cambiar_estado'),

    # --- ENSAYO DE COMPRESIÓN: REGISTRO Y FOTOS (HU-LIMS-14) ---
    path('compresion/', views_compresion.mis_ensayos_compresion, name='mis_ensayos_compresion'),
    path('compresion/<int:detalle_id>/', views_compresion.registrar_ensayo_compresion, name='registrar_compresion'),
    path('compresion/<int:detalle_id>/foto/<str:tipo>/', views_compresion.subir_foto_compresion, name='subir_foto_compresion'),
    path('compresion/foto/<int:foto_id>/', views_compresion.foto_compresion, name='foto_compresion'),
    path('compresion/sesion/abrir/', views_compresion.abrir_sesion_ensayo, name='abrir_sesion_ensayo'),
    path('compresion/sesion/cerrar/', views_compresion.cerrar_sesion_ensayo, name='cerrar_sesion_ensayo'),
    path('recepcion/<int:recepcion_id>/probetas/', views_compresion.datos_probetas_recepcion, name='datos_probetas'),
    path('equipos/', views_compresion.lista_equipos, name='lista_equipos'),
    path('equipos/nuevo/', views_compresion.editar_equipo, name='crear_equipo'),
    path('equipos/<int:equipo_id>/', views_compresion.editar_equipo, name='editar_equipo'),

    # --- INFORMES FINALES Y CERTIFICACIÓN ---
    path('informes/', views.lista_informes_finales, name='lista_informes'),
    path('informe/gestionar/', views.gestionar_informe_final, name='gestionar_informe'),
    path('informe/gestionar/<int:solicitud_id>/', views.gestionar_informe_final, name='gestionar_informe'),
    path('informe/<int:informe_id>/descargar/', views.descargar_pdf_informe, name='descargar_pdf_informe'),
    path('v/<slug:slug_validacion>/', views.validar_informe_publico, name='validar_informe_publico'),
]