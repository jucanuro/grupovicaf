"""Solo desarrollo: trae ya lo que llegó a Mailpit (beat lo hace cada 15 s)."""
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from correo.mailpit import traer


class Command(BaseCommand):
    help = 'Trae a las bandejas los correos de Mailpit dirigidos a cuentas VICAF (solo desarrollo).'

    def add_arguments(self, parser):
        parser.add_argument('--url', default='', help='URL de Mailpit (por defecto CORREO_MAILPIT_URL)')

    def handle(self, *args, **opciones):
        url = (opciones['url'] or settings.CORREO_MAILPIT_URL).rstrip('/')
        if not url:
            raise CommandError('Configure CORREO_MAILPIT_URL o pase --url http://localhost:8025')
        self.stdout.write(self.style.SUCCESS(f'Correos nuevos: {traer(url)}'))
