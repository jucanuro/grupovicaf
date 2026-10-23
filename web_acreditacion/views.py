from django.conf import settings
from django.core.exceptions import ObjectDoesNotExist
from django.db.models import Prefetch
from django.shortcuts import render
from django.urls import reverse
from django.views.decorators.clickjacking import xframe_options_sameorigin
from django.views.static import serve

from servicios.models import Servicio
from web_catalogo.models import LineaServicio

from .models import Acreditacion, Certificacion, primera_acreditacion

GRUPO_OTROS = {'clave': 'otros', 'nombre': 'Otros ensayos acreditados'}


def _ficha(servicio):
    """ServicioPublicado del ensayo o None (el reverse OneToOne lanza si no existe)."""
    try:
        return servicio.publicado
    except ObjectDoesNotExist:
        return None


def ensayos_acreditados_por_linea(acreditaciones):
    """Ensayos de las acreditaciones activas agrupados por línea (specs/WEB v5, REQ-WEB-53 a 61).

    Devuelve (grupos, detalle). Solo salen los campos de la lista blanca
    (REQ-WEB-60): nunca precio, unidad, código de facturación ni
    esta_acreditado. Cada ensayo va en un solo grupo (REQ-WEB-54): la primera
    línea activa que lo incluye, si no la línea de su ficha publicada, si no
    "Otros ensayos acreditados" al final.
    """
    lineas = {
        linea.id: linea
        for linea in LineaServicio.objects.publicadas().only('id', 'nombre', 'slug', 'orden').order_by('orden', 'nombre')
    }
    slugs_lineas = {linea.slug for linea in lineas.values()}
    posicion = {linea_id: indice for indice, linea_id in enumerate(lineas)}

    ensayos = {}
    for acreditacion in acreditaciones:
        etiqueta = f'{acreditacion.organismo} · N.º {acreditacion.numero_acreditacion}'
        for servicio in acreditacion.servicios_acreditados.all():
            if servicio.id in ensayos:
                if etiqueta not in ensayos[servicio.id]['acreditaciones']:
                    ensayos[servicio.id]['acreditaciones'].append(etiqueta)
                continue
            ensayos[servicio.id] = {'servicio': servicio, 'acreditaciones': [etiqueta]}

    grupos = {}
    detalle = {}
    for servicio_id, datos in ensayos.items():
        servicio = datos['servicio']
        ficha = _ficha(servicio)
        # lineas_servicio viene prefetcheado y filtrado a las activas.
        candidatas = sorted((l.id for l in servicio.lineas_servicio.all()), key=posicion.get)
        if not candidatas and ficha and ficha.linea_id in lineas:
            candidatas = [ficha.linea_id]
        linea = lineas[candidatas[0]] if candidatas else None
        grupo = {'clave': linea.slug, 'nombre': linea.nombre} if linea else GRUPO_OTROS

        # Ficha publicada = activa y sin una línea activa con el mismo slug (RN-14).
        url = None
        if ficha and ficha.activo and ficha.slug not in slugs_lineas:
            url = reverse('web_catalogo:servicio_detalle', kwargs={'slug': ficha.slug})
        nombre = ficha.titulo_publico if url else servicio.nombre
        norma = servicio.norma.codigo if servicio.norma else ''
        metodo = servicio.metodo.nombre if servicio.metodo else ''

        grupos.setdefault(grupo['clave'], {**grupo, 'ensayos': []})['ensayos'].append({
            'id': servicio_id,
            'nombre': nombre,
            'norma': norma,
            'linea': grupo['nombre'],
            'url': url,
            # Con ficha también busca por el nombre del LIMS ("Proctor" vs. título público).
            'buscar': ' '.join(dict.fromkeys(filter(None, (nombre, servicio.nombre, norma, metodo, grupo['nombre'])))),
        })
        detalle[servicio_id] = {
            'nombre': nombre,
            'linea': grupo['nombre'],
            'norma': norma,
            # En el LIMS hay normas con el nombre igual al código: no se repite.
            'norma_nombre': servicio.norma.nombre if servicio.norma and servicio.norma.nombre != norma else '',
            'metodo': metodo,
            'acreditacion': '; '.join(datos['acreditaciones']),
            'resumen': ficha.resumen if url else '',
            'url': url,
        }

    orden = {linea.slug: posicion[linea.id] for linea in lineas.values()}
    lista = sorted(grupos.values(), key=lambda g: orden.get(g['clave'], len(orden)))
    for grupo in lista:
        grupo['ensayos'].sort(key=lambda e: e['nombre'].casefold())
    return lista, detalle


def acreditacion_view(request):
    servicios_qs = (
        Servicio.objects.select_related('norma', 'metodo', 'publicado')
        .only(
            'id', 'nombre', 'norma__codigo', 'norma__nombre', 'metodo__nombre',
            'publicado__slug', 'publicado__activo', 'publicado__titulo_publico',
            'publicado__resumen', 'publicado__linea',
        )
        .prefetch_related(Prefetch('lineas_servicio', queryset=LineaServicio.objects.publicadas().only('id')))
    )
    acreditaciones = list(
        Acreditacion.objects.filter(activo=True)
        .only('id', 'organismo', 'numero_acreditacion', 'alcance', 'vigencia_desde', 'vigencia_hasta', 'documento', 'orden')
        .prefetch_related(Prefetch('servicios_acreditados', queryset=servicios_qs))
        .order_by('orden', '-vigencia_desde')
    )
    grupos_ensayos, ensayos_detalle = ensayos_acreditados_por_linea(acreditaciones)
    certificaciones = Certificacion.objects.publicadas().para_card()
    return render(request, 'web/acreditacion.html', {
        'acreditaciones': acreditaciones,
        'grupos_ensayos': grupos_ensayos,
        'ensayos_detalle': ensayos_detalle,
        'total_ensayos': len(ensayos_detalle),
        'certificaciones': certificaciones,
        'certificacion_acreditacion': primera_acreditacion(certificaciones),
    })


@xframe_options_sameorigin
def servir_certificado_dev(request, path):
    """Sirve /media/certificaciones/ en dev con X-Frame-Options SAMEORIGIN (REQ-WEB-37).

    El static() genérico de urls_web.py pasa por XFrameOptionsMiddleware (DENY)
    y el modal de /acreditacion/ no podría embeber el PDF. Solo se enruta con
    DEBUG; en producción lo sirve nginx (deploy/nginx/grupovicaf.conf).
    """
    return serve(request, f'certificaciones/{path}', document_root=settings.MEDIA_ROOT)
