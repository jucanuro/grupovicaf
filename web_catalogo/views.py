from itertools import groupby

from django.core.cache import cache
from django.shortcuts import get_object_or_404, render

from .cache import KEY_CLIENTES_LIST, KEY_EQUIPO_LIST, KEY_SERVICIOS_LIST, TIMEOUT_LISTADOS
from .models import ClienteDestacado, MiembroEquipoPublicado, ServicioPublicado


def servicios_list_view(request):
    """/servicios/ agrupado por CategoriaServicio -> Subcategoria.

    Cacheado 15 min (regla 6). Solo campos públicos: nunca se pasa un
    Servicio completo del LIMS a la plantilla (regla 2 de CLAUDE.md).
    """
    categorias = cache.get(KEY_SERVICIOS_LIST)
    if categorias is None:
        publicados = (
            ServicioPublicado.objects.publicados()
            .select_related('categoria', 'subcategoria')
            .only(
                'slug', 'titulo_publico', 'resumen', 'imagen', 'imagen_alt', 'destacado', 'orden',
                'categoria__nombre', 'subcategoria__nombre',
            )
            .order_by('categoria__nombre', 'subcategoria__nombre', 'orden', 'titulo_publico')
        )

        categorias = []
        for nombre_categoria, items_categoria in groupby(publicados, key=lambda sp: sp.categoria.nombre):
            items_categoria = list(items_categoria)
            subcategorias = []
            for subcategoria, items_sub in groupby(
                items_categoria, key=lambda sp: sp.subcategoria.nombre if sp.subcategoria_id else None
            ):
                subcategorias.append({'nombre': subcategoria, 'servicios': list(items_sub)})
            categorias.append({'nombre': nombre_categoria, 'subcategorias': subcategorias})

        cache.set(KEY_SERVICIOS_LIST, categorias, TIMEOUT_LISTADOS)

    return render(request, 'web/servicios_list.html', {'categorias': categorias})


def servicio_detalle_view(request, slug):
    """/servicios/<slug>/ — sin caché (solo listados se cachean, regla 6)."""
    publicado = get_object_or_404(
        ServicioPublicado.objects.publicados()
        .select_related('categoria', 'subcategoria', 'servicio', 'servicio__norma', 'servicio__metodo')
        .only(
            'slug', 'titulo_publico', 'resumen', 'contenido', 'imagen', 'imagen_alt', 'zona_principal',
            'meta_title', 'meta_description', 'noindex', 'imagen_og',
            'categoria__nombre', 'categoria_id', 'subcategoria__nombre',
            'servicio__nombre', 'servicio__esta_acreditado',
            'servicio__norma__codigo', 'servicio__norma__nombre',
            'servicio__metodo__codigo', 'servicio__metodo__nombre',
        ),
        slug=slug,
    )
    preguntas = publicado.preguntas.filter(activo=True).only('pregunta', 'respuesta', 'orden')

    return render(request, 'web/servicio_detalle.html', {'publicado': publicado, 'preguntas': preguntas})


def clientes_list_view(request):
    """/clientes/ — muro de logos. Nunca ruc/codigo_confidencial (regla 3)."""
    clientes = cache.get(KEY_CLIENTES_LIST)
    if clientes is None:
        clientes = list(
            ClienteDestacado.objects.filter(activo=True, mostrar_logo=True)
            .select_related('cliente')
            .only('enlace', 'orden', 'cliente__razon_social', 'cliente__logo_empresa')
            .order_by('orden', 'id')
        )
        cache.set(KEY_CLIENTES_LIST, clientes, TIMEOUT_LISTADOS)

    return render(request, 'web/clientes.html', {'clientes': clientes})


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

    return render(request, 'web/equipo.html', {'roles': roles})
