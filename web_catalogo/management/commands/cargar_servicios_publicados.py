"""Recrea los ServicioPublicado del paquete web en producción.

Paso obligatorio ANTES de `manage.py loaddata web_dump.json`: ServicioPublicado
tiene `categoria` (FK a servicios.CategoriaServicio) NOT NULL, y ese modelo
está excluido del volcado web a propósito (AWS es la fuente de verdad del
LIMS). No se puede dejar ese campo vacío en un fixture ni resolverlo por
nombre — CategoriaServicio local es solo un placeholder de prueba ("Categoria
1", "cATEGORÍA 2", ...), no hay nada real que emparejar.

Este comando crea/actualiza cada ServicioPublicado con su mismo pk (para que
las FK internas del fixture — PreguntaFrecuente, ZonaCobertura.servicios,
SolicitudCotizacionItem — sigan resolviendo bien al cargar web_dump.json
después) y con `categoria` apuntando a una categoría placeholder explícita
("Sin categorizar (pendiente)"), dejando constancia en el mensaje de que hay
que reasignarla a mano desde el admin — igual que ya advierte
poblar_catalogo_ensayos.py para esta misma tabla.

`servicio` queda siempre en null: se revincula después con
`revincular_catalogo`, que sí conoce el catálogo real de esta base.
"""
import json

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from servicios.models import CategoriaServicio
from web_catalogo.models import ServicioPublicado

NOMBRE_CATEGORIA_PLACEHOLDER = 'Sin categorizar (pendiente)'


class Command(BaseCommand):
    help = (
        'Recrea los ServicioPublicado de web_dump_relink.json con su pk original y una '
        'categoría placeholder. Correr antes de "loaddata web_dump.json".'
    )

    def add_arguments(self, parser):
        parser.add_argument('relink_file', help='Ruta a web_dump_relink.json (de exportar_datos_web).')

    def handle(self, *args, **opciones):
        try:
            with open(opciones['relink_file'], encoding='utf-8') as f:
                relink = json.load(f)
        except FileNotFoundError as exc:
            raise CommandError(f'No existe {opciones["relink_file"]!r}.') from exc

        publicados = relink.get('servicios_publicados', [])
        if not publicados:
            self.stdout.write('No hay ServicioPublicado en el paquete. Nada que hacer.')
            return

        categoria, creada = CategoriaServicio.objects.get_or_create(
            nombre=NOMBRE_CATEGORIA_PLACEHOLDER,
        )
        if creada:
            self.stdout.write(self.style.WARNING(
                f'Creada CategoriaServicio "{NOMBRE_CATEGORIA_PLACEHOLDER}" como placeholder.'
            ))

        with transaction.atomic():
            for entrada in publicados:
                campos = dict(entrada['fields'])
                # El serializer de Django representa la FK 'linea' como su id
                # crudo; el ORM exige una instancia (o el atributo '_id') para
                # asignarla, así que se renombra antes de pasarla a defaults.
                campos['linea_id'] = campos.pop('linea', None)
                ServicioPublicado.objects.update_or_create(
                    pk=entrada['pk'],
                    defaults={
                        **campos,
                        'categoria': categoria,
                        'subcategoria': None,
                        'servicio': None,
                    },
                )

        self.stdout.write(self.style.SUCCESS(
            f'{len(publicados)} ServicioPublicado recreados con categoria='
            f'"{NOMBRE_CATEGORIA_PLACEHOLDER}" y servicio=None.'
        ))
        self.stdout.write(
            'Pendiente en el admin: reasignar la categoría real de cada uno. '
            'El vínculo a servicios.Servicio lo resuelve revincular_catalogo.'
        )
