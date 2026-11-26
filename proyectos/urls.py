# proyectos/urls.py
from django.urls import path, re_path
from . import views
from . import views_compresion
from . import views_informe_compresion
from . import views_informe_editor

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
    path('resultados/', views_compresion.mis_ensayos_compresion, name='mis_ensayos_compresion'),
    path('programa/', views_compresion.programa_dia, name='programa_dia'),
    path('programa/<str:fecha>/cliente/<int:cliente_id>/', views_compresion.programa_cliente, name='programa_cliente'),
    path('programa/<str:fecha>/cliente/<int:cliente_id>/medidas/', views_compresion.programa_medidas, name='programa_medidas'),
    path('resultados/solicitud/<int:solicitud_id>/', views_compresion.resultados_solicitud, name='resultados_solicitud'),
    path('resultados/solicitud/<int:solicitud_id>/medidas/', views_compresion.medidas_solicitud, name='medidas_solicitud'),
    path('resultados/<int:detalle_id>/', views_compresion.registrar_ensayo_compresion, name='registrar_compresion'),
    path('resultados/<int:detalle_id>/foto/<str:tipo>/', views_compresion.subir_foto_compresion, name='subir_foto_compresion'),
    path('resultados/foto/<int:foto_id>/', views_compresion.foto_compresion, name='foto_compresion'),
    path('resultados/foto/<int:foto_id>/borrar/', views_compresion.borrar_foto_compresion, name='borrar_foto_compresion'),
    path('resultados/sesion/abrir/', views_compresion.abrir_sesion_ensayo, name='abrir_sesion_ensayo'),
    path('resultados/sesion/cerrar/', views_compresion.cerrar_sesion_ensayo, name='cerrar_sesion_ensayo'),
    path('resultados/<int:detalle_id>/hoja/', views_compresion.hoja_resultado, name='hoja_resultado'),
    # Rutas anteriores de compresión: redirigen a «Resultados de ensayo».
    re_path(r'^compresion/(?P<resto>.*)$', views_compresion.redirigir_compresion),
    path('equipos/', views_compresion.lista_equipos, name='lista_equipos'),
    path('equipos/nuevo/', views_compresion.editar_equipo, name='crear_equipo'),
    path('equipos/nuevo/ajax/', views_compresion.crear_equipo_ajax, name='crear_equipo_ajax'),
    path('resultados/<int:detalle_id>/video/', views_compresion.video_ensayo, name='video_ensayo'),
    path('resultados/<int:detalle_id>/video/subir/', views_compresion.subir_video_ensayo, name='subir_video_ensayo'),
    path('equipos/<int:equipo_id>/', views_compresion.editar_equipo, name='editar_equipo'),
    path('resultados/revision/', views_informe_compresion.revision_compresion_lista, name='revision_compresion_lista'),
    path('resultados/revision/<int:solicitud_id>/', views_informe_compresion.revision_compresion, name='revision_compresion'),
    path('resultados/informe/<int:informe_id>/pdf/', views_informe_compresion.pdf_informe_compresion, name='pdf_informe_compresion'),
    path('resultados/excel/', views_informe_compresion.excel_compresion, name='excel_compresion'),
    path('resultados/informe/<int:solicitud_id>/editor/', views_informe_editor.editor_informe, name='editor_informe'),
    path('resultados/informe/<int:solicitud_id>/guardar/', views_informe_editor.guardar_informe, name='guardar_informe'),
    path('resultados/informe/<int:solicitud_id>/vista-previa/', views_informe_editor.vista_previa_informe, name='vista_previa_informe'),
    path('resultados/informe/<int:solicitud_id>/version/<int:version_id>/restaurar/', views_informe_editor.restaurar_version, name='restaurar_version_informe'),
    path('resultados/informe/<int:solicitud_id>/emitir/', views_informe_editor.emitir_informe, name='emitir_informe'),

    # --- INFORMES FINALES Y CERTIFICACIÓN ---
    path('informes/', views.lista_informes_finales, name='lista_informes'),
    path('informe/gestionar/', views.gestionar_informe_final, name='gestionar_informe'),
    path('informe/gestionar/<int:solicitud_id>/', views.gestionar_informe_final, name='gestionar_informe'),
    path('informe/<int:informe_id>/descargar/', views.descargar_pdf_informe, name='descargar_pdf_informe'),
    path('v/<slug:slug_validacion>/', views.validar_informe_publico, name='validar_informe_publico'),
]