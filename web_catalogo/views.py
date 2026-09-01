from itertools import groupby

from django.core.cache import cache
from django.db.models import Count, Prefetch
from django.shortcuts import get_object_or_404, render

from servicios.models import Servicio

from .cache import KEY_CLIENTES_LIST, KEY_EQUIPO_LIST, KEY_SERVICIOS_LIST, TIMEOUT_LISTADOS
from .models import ClienteDestacado, ImagenLinea, LineaServicio, MiembroEquipoPublicado, ServicioPublicado

# Lista blanca de servicios.Servicio para cualquier vista pública (regla 2 y
# "REGLA CRÍTICA" del encargo de líneas): precio_base y codigo_facturacion
# nunca viajan al HTML público.
_ENSAYO_CAMPOS_PUBLICOS = (
    'nombre', 'esta_acreditado',
    'norma__codigo', 'norma__nombre',
    'metodo__codigo', 'metodo__nombre',
    'publicado__slug', 'publicado__activo',
)


def lineas_sidebar():
    """Las 8 líneas activas para el índice (/servicios/) y el sidebar de cada
    línea (linea_detalle.html). Comparten la misma caché de 15 min (regla 6):
    ambas vistas necesitan el mismo listado ligero, solo cambia cómo lo pintan.
    """
    lineas = cache.get(KEY_SERVICIOS_LIST)
    if lineas is None:
        lineas = list(
            LineaServicio.objects.publicadas()
            .only('slug', 'nombre', 'resumen', 'imagen', 'imagen_alt', 'icono', 'destacado', 'orden')
            # num_ensayos alimenta el badge "N ensayos" de la tarjeta bento en
            # servicios_list.html; distinct=True por si el M2M trajera join
            # duplicado con otro prefetch en el futuro.
            .annotate(num_ensayos=Count('ensayos', distinct=True))
            .order_by('orden', 'nombre')
        )
        cache.set(KEY_SERVICIOS_LIST, lineas, TIMEOUT_LISTADOS)
    return lineas


def servicios_list_view(request):
    """/servicios/ — índice de líneas comerciales (8 tarjetas, ver LineaServicio)."""
    return render(request, 'web/servicios_list.html', {'lineas': lineas_sidebar()})


def servicio_detalle_view(request, slug):
    """/servicios/<slug>/ — línea comercial o ensayo individual, sin caché.

    LineaServicio y ServicioPublicado comparten el prefijo /servicios/<slug>/
    para que una línea (p. ej. mecanica-de-suelos) pueda enlazar a sus
    ensayos individuales (p. ej. ensayo-cbr) bajo la misma jerarquía de URL.
    Se prueba primero LineaServicio; si no hay match se cae al
    ServicioPublicado de siempre (comportamiento sin cambios).
    """
    linea = (
        LineaServicio.objects.publicadas()
        .prefetch_related(
            Prefetch(
                'ensayos',
                queryset=(
                    Servicio.objects.select_related('norma', 'metodo', 'publicado')
                    .only(*_ENSAYO_CAMPOS_PUBLICOS)
                    .order_by('nombre')
                ),
            ),
            Prefetch(
                'galeria',
                queryset=(
                    ImagenLinea.objects.publicadas()
                    .only(
                        'linea_id', 'imagen', 'ancho', 'alto',
                        'imagen_miniatura', 'ancho_miniatura', 'alto_miniatura',
                        'alt_text', 'orden',
                    )
                    .order_by('orden', 'id')
                ),
            ),
        )
        .only(
            'slug', 'nombre', 'titulo_h1', 'resumen', 'contenido', 'imagen', 'imagen_alt',
            'meta_title', 'meta_description', 'noindex', 'imagen_og',
        )
        .filter(slug=slug)
        .first()
    )
    if linea is not None:
        return render(request, 'web/linea_detalle.html', {
            'linea': linea,
            'todas_las_lineas': lineas_sidebar(),
        })

    publicado = get_object_or_404(
        ServicioPublicado.objects.publicados()
        .select_related('categoria', 'subcategoria', 'linea', 'servicio', 'servicio__norma', 'servicio__metodo')
        .only(
            'slug', 'titulo_publico', 'resumen', 'contenido', 'imagen', 'imagen_alt', 'zona_principal',
            'meta_title', 'meta_description', 'noindex', 'imagen_og',
            'categoria__nombre', 'categoria_id', 'subcategoria__nombre',
            'linea__slug', 'linea__nombre', 'linea_id',
            'servicio__nombre', 'servicio__esta_acreditado',
            'servicio__norma__codigo', 'servicio__norma__nombre',
            'servicio__metodo__codigo', 'servicio__metodo__nombre',
        ),
        slug=slug,
    )
    preguntas = publicado.preguntas.filter(activo=True).only('pregunta', 'respuesta', 'orden')

    return render(request, 'web/servicio_detalle.html', {'publicado': publicado, 'preguntas': preguntas})


def clientes_destacados():
    """Muro de logos (companion de clientes.Cliente). Nunca ruc/codigo_confidencial
    (regla 3). Compartido por /clientes/ y el muro de la home (misma caché de 15 min).
    """
    clientes = cache.get(KEY_CLIENTES_LIST)
    if clientes is None:
        clientes = list(
            ClienteDestacado.objects.filter(activo=True, mostrar_logo=True)
            .select_related('cliente')
            .only('enlace', 'orden', 'cliente__razon_social', 'cliente__logo_empresa')
            .order_by('orden', 'id')
        )
        cache.set(KEY_CLIENTES_LIST, clientes, TIMEOUT_LISTADOS)
    return clientes


def clientes_list_view(request):
    """/clientes/ — muro de logos."""
    return render(request, 'web/clientes.html', {'clientes': clientes_destacados()})


def equipo_list_view(request):
    """/equipo/ agrupado por RolTrabajador. Nunca firma_electronica (regla 3)."""
    roles = cache.get(KEY_EQUIPO_LIST)
    if roles is None:
        miembros = (
            MiembroEquipoPublicado.objects.filter(activo=True)
            .select_related('perfil', 'perfil__rol')
            .only(
                'bio_publica', 'mostrar_correo', 'orden',
                'perfil__nombre_completo', 'perfil__titulo_profesional', 'perfil__foto',
                'perfil__linkedin', 'perfil__correo_contacto', 'perfil__rol__nombre', 'perfil__rol_id',
            )
            .order_by('perfil__rol__nombre', 'orden', 'id')
        )

        roles = []
        for nombre_rol, items_rol in groupby(miembros, key=lambda m: m.perfil.rol.nombre):
            roles.append({'nombre': nombre_rol, 'miembros': list(items_rol)})

        cache.set(KEY_EQUIPO_LIST, roles, TIMEOUT_LISTADOS)

    total_areas = len(roles)
    total_personas = sum(len(rol['miembros']) for rol in roles)

    return render(request, 'web/equipo.html', {
        'roles': roles,
        'total_areas': total_areas,
        'total_personas': total_personas,
    })
