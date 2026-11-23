"""Regenera static/css/tema_oscuro_utilidades.css (modo oscuro del LIMS).

    python manage.py generar_tema_oscuro              # escribe el archivo
    python manage.py generar_tema_oscuro --comprobar  # falla si está desactualizado

Ver core/tema_oscuro.py.
"""
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from core.tema_oscuro import SALIDA, generar_css


class Command(BaseCommand):
    help = 'Genera la hoja de utilidades del modo oscuro del LIMS a partir de las plantillas.'

    def add_arguments(self, parser):
        parser.add_argument('--comprobar', action='store_true',
                            help='No escribe; termina con error si el archivo no está al día.')

    def handle(self, *args, **opciones):
        destino = Path(settings.BASE_DIR) / SALIDA
        css = generar_css()
        if opciones['comprobar']:
            actual = destino.read_text(encoding='utf-8') if destino.exists() else ''
            if actual != css:
                raise CommandError(f'{SALIDA} está desactualizado: corre `python manage.py generar_tema_oscuro`.')
            self.stdout.write(self.style.SUCCESS(f'{SALIDA} al día.'))
            return
        destino.write_text(css, encoding='utf-8')
        self.stdout.write(self.style.SUCCESS(f'{SALIDA}: {css.count(chr(10))} líneas.'))
