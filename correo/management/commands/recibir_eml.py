"""Mete correos .eml reales a las bandejas (p. ej. exportados de cPanel u Outlook).

    python manage.py recibir_eml correo1.eml correo2.eml
    python manage.py recibir_eml carpeta/*.eml --para informes@grupovicaf.com

Usa el mismo camino que la recepción real (RecepcionEML): sanitiza el HTML,
arma los hilos y no duplica un correo que ya entró.
"""
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from correo.recepcion import CorreoRechazado, recepcion


class Command(BaseCommand):
    help = 'Recibe uno o varios archivos .eml en las cuentas VICAF destinatarias.'

    def add_arguments(self, parser):
        parser.add_argument('archivos', nargs='+', help='rutas de archivos .eml')
        parser.add_argument('--para', action='append', default=[],
                            help='cuenta VICAF destinataria si el .eml no la nombra (repetible)')

    def handle(self, *args, **opciones):
        total = 0
        for ruta in opciones['archivos']:
            archivo = Path(ruta)
            if not archivo.is_file():
                raise CommandError(f'No existe el archivo {ruta}')
            try:
                creados = recepcion().recibir(archivo.read_bytes(), destinatarios=opciones['para'])
            except CorreoRechazado as error:
                self.stderr.write(f'{archivo.name}: {error}')
                continue
            total += len(creados)
            if creados:
                cuentas = ', '.join(m.cuenta.direccion for m in creados)
                self.stdout.write(f'{archivo.name}: recibido en {cuentas}')
            else:
                self.stdout.write(f'{archivo.name}: ya estaba recibido')
        self.stdout.write(self.style.SUCCESS(f'Correos nuevos: {total}'))
