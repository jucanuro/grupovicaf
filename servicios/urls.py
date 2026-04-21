from django.urls import path
from . import views

app_name = 'servicios'

urlpatterns = [
    path('', views.lista_servicios, name='lista_servicios'),
    path('crear/', views.crear_editar_servicio, name='crear_servicio'),
    path('editar/<int:pk>/', views.crear_editar_servicio, name='editar_servicio'),
    path('eliminar/<int:pk>/', views.eliminar_servicio, name='eliminar_servicio'),

    path('ajax/crear-norma/', views.crear_norma_ajax, name='crear_norma_ajax'),
    path('ajax/crear-metodo/', views.crear_metodo_ajax, name='crear_metodo_ajax'),

    path('normas/', views.NormaListView.as_view(), name='norma_list'),
    path('normas/nuevo/', views.NormaCreateView.as_view(), name='norma_create'),
    path('normas/editar/<int:pk>/', views.NormaUpdateView.as_view(), name='norma_update'),

    path('metodos/', views.MetodoListView.as_view(), name='metodo_list'),
    path('metodos/nuevo/', views.MetodoCreateView.as_view(), name='metodo_create'),
    path('metodos/editar/<int:pk>/', views.MetodoUpdateView.as_view(), name='metodo_update'),

    path('categoria/crear-ajax/', views.crear_categoria_ajax, name='crear_categoria_ajax'),
    path('subcategoria/crear-ajax/', views.crear_subcategoria_ajax, name='crear_subcategoria_ajax'),

    path('cotizaciones/', views.lista_cotizaciones, name='lista_cotizaciones'),
    path('cotizaciones/crear/', views.crear_cotizacion, name='crear_cotizacion'),
    path('cotizaciones/editar/<int:pk>/', views.editar_cotizacion, name='editar_cotizacion'),
    path('cotizaciones/eliminar/<int:pk>/', views.eliminar_cotizacion, name='eliminar_cotizacion'),
    path('cotizaciones/<int:pk>/pdf/', views.generar_pdf_cotizacion, name='ver_pdf_cotizacion'),
    path('cotizaciones/<int:pk>/aprobar/', views.aprobar_cotizacion, name='aprobar_cotizacion'),

    path('cotizaciones/<int:pk>/condiciones/json/', views.condiciones_cotizacion_json, name='condiciones_cotizacion_json'),
    path('cotizaciones/<int:pk>/condiciones/guardar/', views.guardar_condiciones_cotizacion_json, name='guardar_condiciones_cotizacion_json'),
    path('cotizaciones/<int:pk>/condiciones/resumen/', views.resumen_condiciones_cotizacion_json, name='resumen_condiciones_cotizacion_json'),

    path('plantillas/', views.lista_plantillas, name='lista_plantillas'),
    path('plantillas/crear/', views.crear_editar_plantilla, name='crear_plantilla'),
    path('plantillas/editar/<int:pk>/', views.crear_editar_plantilla, name='editar_plantilla'),
    path('plantillas/api/detalle-json/<int:pk>/', views.obtener_detalle_plantilla_json, name='obtener_detalle_plantilla_json'),

    path('plantillas/<int:pk>/condiciones/json/', views.condiciones_plantilla_json, name='condiciones_plantilla_json'),
    path('plantillas/<int:pk>/condiciones/guardar/', views.guardar_condiciones_plantilla_json, name='guardar_condiciones_plantilla_json'),
    path('plantillas/<int:pk>/condiciones/resumen/', views.resumen_condiciones_plantilla_json, name='resumen_condiciones_plantilla_json'),

    path('api/plantilla/<int:pk>/', views.obtener_detalle_plantilla_json, name='api_plantilla_detalle'),
    path('api/ver/<int:pk>/', views.obtener_detalle_servicio_api, name='obtener_detalle_servicio_api'),
    path('api/buscar/', views.buscar_servicios_api, name='buscar_servicios_api'),
    path('cotizaciones/api/buscar/', views.buscar_cotizaciones_api, name='buscar_cotizaciones_api'),
    path('cotizaciones/api/servicios/<int:pk>/', views.obtener_detalle_servicio_api, name='obtener_detalle_servicio_para_cotizacion_api'),
]