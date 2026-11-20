"""Revisa que cada usuario del CSV de cuentas pueda entrar y usar su correo.

    python manage.py verificar_accesos deploy/correo/cuentas_iniciales.csv

Solo lee; no cambia nada. Por usuario comprueba: existe, está activo, tiene
perfil de trabajador, su rol tiene «correo.ver» y tiene las cuentas con el
rol esperado. Termina con error si algo falla (útil como chequeo previo).
"""
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError

from correo.models import AccesoCuenta
from trabajadores.models import TrabajadorProfile
from trabajadores.permissions import trabajador_tiene_permiso

from ._accesos_csv import esperado_por_usuario


class Command(BaseCommand):
    help = 'Verifica usuarios, permiso de correo y accesos a cuentas según el CSV.'

    def add_arguments(self, parser):
        parser.add_argument('csv')

    def handle(self, *args, **o):
        User = get_user_model()
        fallos = 0
        for usuario, cuentas in esperado_por_usuario(o['csv']).items():
            problemas = []
            u = User.objects.filter(username=usuario).first()
            if u is None:
                self.stdout.write(self.style.ERROR(f'✘ {usuario}: no existe en el LIMS'))
                fallos += 1
                continue
            if not u.is_active:
                problemas.append('inactivo')
            perfil = TrabajadorProfile.objects.filter(user=u).select_related('rol').first()
            if perfil is None:
                problemas.append('sin perfil de trabajador')
            elif not trabajador_tiene_permiso(u, 'correo.ver'):
                problemas.append(f'su rol «{perfil.rol.nombre}» no tiene «Correo ver»')
            if not u.email:
                problemas.append('sin correo en su ficha (no podrá entrar con el correo)')
            tiene = {a.cuenta.direccion: a.rol for a in AccesoCuenta.objects.filter(usuario=u).select_related('cuenta')}
            for direccion, rol in cuentas:
                if tiene.get(direccion) is None:
                    problemas.append(f'falta acceso a {direccion}')
                elif tiene[direccion] != rol:
                    problemas.append(f'{direccion}: tiene «{tiene[direccion]}», se esperaba «{rol}»')
            if problemas:
                fallos += 1
                self.stdout.write(self.style.ERROR(f'✘ {usuario}: ' + '; '.join(problemas)))
            else:
                extra = ' · debe cambiar su clave' if perfil and perfil.debe_cambiar_clave else ''
                self.stdout.write(self.style.SUCCESS(f'✔ {usuario}: {len(cuentas)} cuenta(s){extra}'))
        if fallos:
            raise CommandError(f'{fallos} usuario(s) con problemas.')
        self.stdout.write(self.style.SUCCESS('Todos los accesos están completos.'))
