"""Cambia el nombre de usuario de un trabajador (conserva todo lo demás).

    python manage.py renombrar_usuario raquelro raquelo
"""
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = 'Renombra un usuario del LIMS; sus accesos, cuentas y datos siguen vinculados.'

    def add_arguments(self, parser):
        parser.add_argument('actual')
        parser.add_argument('nuevo')

    def handle(self, *args, **o):
        User = get_user_model()
        u = User.objects.filter(username=o['actual']).first()
        if u is None:
            raise CommandError(f'No existe el usuario «{o["actual"]}».')
        nuevo = o['nuevo'].strip()
        if not nuevo or User.objects.filter(username__iexact=nuevo).exclude(pk=u.pk).exists():
            raise CommandError(f'«{nuevo}» está vacío o ya lo usa otro usuario.')
        u.username = nuevo
        u.save(update_fields=['username'])
        self.stdout.write(self.style.SUCCESS(f'Usuario renombrado: {o["actual"]} → {nuevo}'))
