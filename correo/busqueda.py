"""Búsqueda de texto completo en PostgreSQL (SearchVector + índice GIN).

Pesos: A asunto · B remitente, destinatarios y nombres de adjuntos · C cuerpo.
Configuración 'spanish' sobre texto sin tildes (extensión unaccent), así
"compresion" encuentra "compresión". En sqlite (dev sin Docker) cae a
icontains para no romper el desarrollo local.
"""
import re

from django.contrib.postgres.search import SearchQuery, SearchRank, SearchVector
from django.db import connection
from django.db.models import F, Func, Q, TextField, Value
from django.db.models.functions import Cast, Coalesce

from .models import Mensaje
from .sanitizar import sin_tildes


def _es_postgres():
    return connection.vendor == 'postgresql'


def _sin_tildes_sql(expresion):
    return Func(Coalesce(expresion, Value('')), function='unaccent', output_field=TextField())


def indexar(mensaje):
    """Recalcula Mensaje.busqueda de un mensaje (tras crearlo o editarlo)."""
    if not _es_postgres():
        return
    nombres_adjuntos = ' '.join(mensaje.adjuntos.values_list('nombre', flat=True))
    vector = (
        SearchVector(_sin_tildes_sql(F('asunto')), weight='A', config='spanish')
        + SearchVector(
            _sin_tildes_sql(F('de')), _sin_tildes_sql(F('de_nombre')),
            _sin_tildes_sql(Cast('para', TextField())), _sin_tildes_sql(Cast('cc', TextField())),
            _sin_tildes_sql(Value(nombres_adjuntos)),
            weight='B', config='spanish',
        )
        + SearchVector(_sin_tildes_sql(F('cuerpo_texto')), weight='C', config='spanish')
    )
    Mensaje.objects.filter(pk=mensaje.pk).update(busqueda=vector)


def buscar(queryset, texto):
    texto = (texto or '').strip()
    if not texto:
        return queryset
    if _es_postgres():
        consulta = SearchQuery(sin_tildes(texto), config='spanish', search_type='websearch')
        return (
            queryset.filter(busqueda=consulta)
            .annotate(rango=SearchRank(F('busqueda'), consulta))
            .order_by('-rango', '-fecha')
        )
    filtro = Q()
    for palabra in texto.split():
        filtro &= (
            Q(asunto__icontains=palabra) | Q(cuerpo_texto__icontains=palabra) | Q(de__icontains=palabra)
            | Q(de_nombre__icontains=palabra) | Q(adjuntos__nombre__icontains=palabra)
        )
    return queryset.filter(filtro).distinct()


def buscar_al_escribir(queryset, texto):
    """Como `buscar`, pero cada palabra cuenta como prefijo («factu» encuentra
    «factura»): es la búsqueda de las sugerencias mientras se escribe."""
    palabras = re.findall(r'\w+', sin_tildes(texto or '').lower())[:6]
    if not palabras:
        return queryset.none()
    if not _es_postgres():
        return buscar(queryset, ' '.join(palabras))
    consulta = SearchQuery(' & '.join(f'{p}:*' for p in palabras), config='spanish', search_type='raw')
    return (
        queryset.filter(busqueda=consulta)
        .annotate(rango=SearchRank(F('busqueda'), consulta))
        .order_by('-rango', '-fecha')
    )


def filtrar_direccion(queryset, campo, correo):
    """Mensajes cuyo JSON `para`/`cc` contiene la dirección (texto parcial)."""
    return queryset.annotate(**{f'_{campo}_txt': Cast(campo, TextField())}).filter(
        **{f'_{campo}_txt__icontains': correo}
    )
