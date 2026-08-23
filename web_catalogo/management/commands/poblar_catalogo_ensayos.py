"""Crea los ServicioPublicado placeholder de los 7 ensayos pedidos para F5.

Idempotente (update_or_create por slug). El contenido real lo redacta el
equipo después: aquí solo se deja el placeholder marcado (regla 16 de
CLAUDE.md — nunca texto de relleno inventado que pueda publicarse por
accidente).

Vinculación con servicios.Servicio: solo se vincula cuando hay un único
Servicio candidato inequívoco. Cuando hay varias variantes del mismo
ensayo en el LIMS (p. ej. Proctor Estándar vs Modificado) o ninguna
coincidencia, el registro se crea sin vincular (servicio=None) y se avisa
en la salida del comando — vincular después es un clic en el admin
(autocomplete_fields).
"""
from django.core.management.base import BaseCommand
from django.db import transaction

from servicios.models import CategoriaServicio, Servicio
from web_catalogo.models import ServicioPublicado

PLACEHOLDER_RESUMEN = 'PENDIENTE DE REDACCIÓN — resumen comercial del ensayo.'
PLACEHOLDER_CONTENIDO = (
    'PENDIENTE DE REDACCIÓN.\n\n'
    'Este contenido debe describir el ensayo, su alcance, la norma técnica '
    'aplicable y por qué es relevante para el cliente (600-1000 palabras). '
    'No publicar sin reemplazar este placeholder.'
)

# slug -> (titulo_publico, id de Servicio si es inequívoco o None, nota)
ENSAYOS = [
    ('ensayo-cbr', 'Ensayo CBR', 85, 'Servicio único: CBR (ES011).'),
    ('ensayo-proctor', 'Ensayo Proctor', None,
     'Ambiguo: existen Proctor Estándar (ES009, id 83) y Proctor Modificado '
     '(ES010, id 84). Vincular manualmente el que corresponda.'),
    ('ensayo-triaxial', 'Ensayo Triaxial', None,
     'Ambiguo: 6 variantes en el LIMS (UU/CU/CD, diámetros 2.8" y 4"): '
     'EE002, EE003, EE005, EE006, EE008, EE009. Vincular manualmente.'),
    ('rotura-de-probetas', 'Rotura de Probetas', None,
     'Ambiguo: dos registros casi duplicados — id 4 (EC-004, "...(*)") y '
     'id 32 (EC001, sin asterisco). Vincular manualmente tras confirmar '
     'cuál es el vigente.'),
    ('diseno-de-mezclas', 'Diseño de Mezclas', None,
     'Ambiguo: 4 candidatos — id 1 (ES001), id 15 (CN007, TEÓRICO), '
     'id 16 (CN008, TEÓRICO con/sin aditivos), id 17 (CN009, COMPROBADO). '
     'Vincular manualmente el que corresponda.'),
    ('densidad-de-campo', 'Densidad de Campo', 35,
     'Servicio único: Densidad mediante el cono y la arena (EDC002).'),
    ('ensayos-de-asfalto', 'Ensayos de Asfalto', None,
     'Sin match: ningún Servicio del LIMS menciona "asfalto". Crear el '
     'registro interno en servicios.Servicio antes de vincular.'),
]


class Command(BaseCommand):
    help = 'Crea/actualiza los ServicioPublicado placeholder de los 7 ensayos de F5.'

    def handle(self, *args, **options):
        categoria_placeholder = CategoriaServicio.objects.order_by('id').first()
        if categoria_placeholder is None:
            self.stderr.write(self.style.ERROR(
                'No hay ninguna CategoriaServicio en la base de datos. '
                'Crea al menos una antes de correr este comando.'
            ))
            return
        self.stdout.write(self.style.WARNING(
            f'Todos los registros se crean con categoria="{categoria_placeholder.nombre}" '
            '(la primera disponible) como placeholder — reasigna la categoría real de '
            'cada ensayo desde el admin antes de publicar.'
        ))
        self.stdout.write('')

        avisos = []

        with transaction.atomic():
            for slug, titulo, servicio_id, nota in ENSAYOS:
                servicio = None
                if servicio_id is not None:
                    servicio = Servicio.objects.filter(pk=servicio_id).first()
                    if servicio is None:
                        avisos.append(f'{slug}: se esperaba Servicio id={servicio_id}, no existe. {nota}')

                publicado, creado = ServicioPublicado.objects.update_or_create(
                    slug=slug,
                    defaults={
                        'titulo_publico': titulo,
                        'categoria': categoria_placeholder,
                        'resumen': PLACEHOLDER_RESUMEN,
                        'contenido': PLACEHOLDER_CONTENIDO,
                        'activo': False,  # no se indexa hasta que se redacte y se revise
                        'servicio': servicio,
                    },
                )

                accion = 'creado' if creado else 'actualizado'
                vinculo = f'-> Servicio #{servicio.pk} ({servicio.codigo_facturacion})' if servicio else '-> SIN VINCULAR'
                self.stdout.write(f'{slug}: {accion} {vinculo}')

                if servicio is None and servicio_id is None:
                    avisos.append(f'{slug}: {nota}')

        if avisos:
            self.stdout.write('')
            self.stdout.write(self.style.WARNING('Pendientes de revisión manual:'))
            for aviso in avisos:
                self.stdout.write(self.style.WARNING(f'  - {aviso}'))

        self.stdout.write('')
        self.stdout.write(self.style.SUCCESS(
            'Listo. Los 7 registros quedan activo=False (no se publican) hasta que se '
            'redacte el contenido real y se confirme la categoría/vínculo en el admin.'
        ))
