"""Genera el paquete de datos de la capa web para subir a producción.

AWS es la fuente de verdad del LIMS y no se toca: este comando NUNCA vuelca
`clientes`, `trabajadores`, `servicios`, `proyectos`, `actividades`, `auth` ni
`contenttypes`. Solo las apps `web_*` y `siteconfig`.

Genera dos archivos (ninguno se versiona, ver .gitignore):

- ``web_dump.json``: fixture estándar de Django, cargable con
  ``manage.py loaddata`` tal cual, en el orden correcto para las FK internas.
- ``web_dump_relink.json``: lo que NO puede ir en el fixture estándar porque
  referencia IDs de ``servicios.Servicio``/``CategoriaServicio`` que no
  coinciden entre esta base y la de producción (aquí 99 Servicio, en AWS 14):

  * ``servicios_publicados``: cada ``ServicioPublicado``, con ``servicio``
    puesto en null y sin ``categoria``/``subcategoria`` (esas columnas son
    NOT NULL en la base y apuntan a un modelo excluido — no se pueden dejar
    vacías en un fixture; las resuelve ``cargar_servicios_publicados`` en
    destino). Se guarda el nombre/código del Servicio local como pista para
    ``revincular_catalogo``.
  * ``linea_ensayos`` / ``acreditacion_servicios``: nombre/código de los
    Servicio que cada LineaServicio/Acreditacion tenía vinculados por M2M
    antes de vaciarlo (hoy son 0 en esta base, pero el comando es genérico).

Procedimiento completo documentado en CLAUDE.md
("Actualizar contenido web sin tocar el LIMS").
"""
import json
import unicodedata

from django.core import serializers
from django.core.management.base import BaseCommand

from web_acreditacion.models import Acreditacion
from web_catalogo.models import ImagenLinea, LineaServicio, PreguntaFrecuente, ServicioPublicado
from web_contacto.models import MensajeContacto, SolicitudCotizacionItem, SolicitudCotizacionWeb
from web_inicio.models import CarruselInicio
from web_nosotros.models import DocumentoNosotros, Nosotros, TipoDocumentoNosotros
from web_zonas.models import ZonaCobertura
from siteconfig.models import NegocioConfig


def normalizar(texto):
    """Minúsculas, sin tildes, sin puntuación — para comparar nombres entre bases."""
    texto = unicodedata.normalize('NFKD', texto or '').encode('ascii', 'ignore').decode('ascii')
    return ' '.join(texto.lower().split())


def snapshot_servicio(servicio):
    if servicio is None:
        return None
    return {
        'nombre': servicio.nombre,
        'nombre_normalizado': normalizar(servicio.nombre),
        'codigo_facturacion': servicio.codigo_facturacion,
    }


class Command(BaseCommand):
    help = (
        'Genera web_dump.json y web_dump_relink.json con el contenido de las apps '
        'web_* y siteconfig, listo para cargar en producción sin tocar el LIMS.'
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--output-dir', default='.',
            help='Carpeta donde escribir web_dump.json y web_dump_relink.json (default: cwd).',
        )
        parser.add_argument('--indent', type=int, default=2)

    def handle(self, *args, **opciones):
        out_dir = opciones['output_dir'].rstrip('/')
        indent = opciones['indent']

        # --- 1. web_dump.json: fixture estándar, en orden seguro de FKs internas ---
        # ServicioPublicado NO va aquí (ver docstring): sus dependientes
        # (PreguntaFrecuente, ZonaCobertura.servicios, SolicitudCotizacionItem)
        # solo se cargan después de que cargar_servicios_publicados haya
        # recreado esas filas con su mismo pk.
        querysets_en_orden = [
            NegocioConfig.objects.all(),
            CarruselInicio.objects.all(),
            TipoDocumentoNosotros.objects.all(),
            Nosotros.objects.all(),
            DocumentoNosotros.objects.all(),
            Acreditacion.objects.all(),
            LineaServicio.objects.all(),
            ImagenLinea.objects.all(),
            ZonaCobertura.objects.all(),
            MensajeContacto.objects.all(),
            SolicitudCotizacionWeb.objects.all(),
            SolicitudCotizacionItem.objects.all(),
            PreguntaFrecuente.objects.all(),
        ]

        objetos = []
        for qs in querysets_en_orden:
            objetos.extend(qs)

        # Relaciones que cruzan a servicios.Servicio: solo se leen (nunca se
        # tocan en esta base) y se vacían más abajo en el JSON ya serializado.
        # Se revinculan en producción con revincular_catalogo.
        linea_ensayos_hints = {}
        for linea in LineaServicio.objects.prefetch_related('ensayos').all():
            servicios_vinculados = list(linea.ensayos.all())
            if servicios_vinculados:
                linea_ensayos_hints[linea.slug] = [snapshot_servicio(s) for s in servicios_vinculados]

        acreditacion_hints = {}
        for acred in Acreditacion.objects.prefetch_related('servicios_acreditados').all():
            servicios_vinculados = list(acred.servicios_acreditados.all())
            if servicios_vinculados:
                acreditacion_hints[acred.numero_acreditacion] = [
                    snapshot_servicio(s) for s in servicios_vinculados
                ]

        # serializers.serialize no soporta excluir un M2M por campo, así que
        # se post-procesa el JSON ya generado para vaciar los que apuntan a
        # servicios.Servicio (ID no portable) y los FK a auth/clientes/servicios.
        fixture_json = serializers.serialize('json', objetos, indent=indent)
        registros = json.loads(fixture_json)
        for registro in registros:
            if registro['model'] == 'web_catalogo.lineaservicio':
                registro['fields']['ensayos'] = []
            elif registro['model'] == 'web_acreditacion.acreditacion':
                registro['fields']['servicios_acreditados'] = []
            elif registro['model'] == 'web_contacto.solicitudcotizacionweb':
                registro['fields']['cliente'] = None
                registro['fields']['cotizacion'] = None
            elif registro['model'] == 'web_contacto.mensajecontacto':
                registro['fields']['atendido_por'] = None

        # --- 2. web_dump_relink.json: lo bloqueado por servicios.CategoriaServicio ---
        publicados = list(ServicioPublicado.objects.select_related('servicio').all())
        publicados_json = json.loads(
            serializers.serialize('json', publicados, indent=indent)
        )
        servicios_por_pk = {p.pk: p.servicio for p in publicados}
        servicios_publicados = []
        for registro in publicados_json:
            campos = dict(registro['fields'])
            campos.pop('servicio', None)
            campos.pop('categoria', None)
            campos.pop('subcategoria', None)
            servicio = snapshot_servicio(servicios_por_pk.get(registro['pk']))
            servicios_publicados.append({
                'pk': registro['pk'],
                'fields': campos,
                'servicio_snapshot': servicio,
            })

        relink = {
            'servicios_publicados': servicios_publicados,
            'linea_ensayos': linea_ensayos_hints,
            'acreditacion_servicios': acreditacion_hints,
        }

        ruta_fixture = f'{out_dir}/web_dump.json'
        ruta_relink = f'{out_dir}/web_dump_relink.json'
        with open(ruta_fixture, 'w', encoding='utf-8') as f:
            json.dump(registros, f, ensure_ascii=False, indent=indent)
        with open(ruta_relink, 'w', encoding='utf-8') as f:
            json.dump(relink, f, ensure_ascii=False, indent=indent)

        self.stdout.write(self.style.SUCCESS(
            f'{ruta_fixture}: {len(registros)} registros.\n'
            f'{ruta_relink}: {len(servicios_publicados)} ServicioPublicado, '
            f'{len(linea_ensayos_hints)} LineaServicio con ensayos, '
            f'{len(acreditacion_hints)} Acreditacion con servicios_acreditados.'
        ))
        self.stdout.write(
            'Siguiente paso en producción: cargar_servicios_publicados, luego '
            'loaddata web_dump.json, luego revincular_catalogo --apply. Ver CLAUDE.md.'
        )
