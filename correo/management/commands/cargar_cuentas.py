"""Crea cuentas de correo y sus accesos desde un CSV (separador «;»).

    python manage.py cargar_cuentas cuentas.csv --actor jucanuro --simular
    python manage.py cargar_cuentas cuentas.csv --actor jucanuro

Columnas: direccion;nombre;accesos   (accesos = usuario:rol,usuario:rol)
Pasa por las mismas funciones de /administrar/ (valida el dominio, deja la
bitácora). Es idempotente: una cuenta que ya existe no se duplica y solo se
completan los accesos que falten. `--actor` es el administrador del correo
(queda con el rol «administra» en cada cuenta nueva, salvo --sin-actor-en-cuentas).
"""
import csv
from pathlib import Path

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand, CommandError

from correo import administracion as adm
from correo.models import AccesoCuenta, CuentaCorreo


class Command(BaseCommand):
    help = 'Crea cuentas y accesos de correo desde un CSV.'

    def add_arguments(self, parser):
        parser.add_argument('csv')
        parser.add_argument('--actor', required=True, help='usuario del LIMS que figura en la bitácora')
        parser.add_argument('--simular', action='store_true')
        parser.add_argument('--sin-actor-en-cuentas', action='store_true',
                            help='no darle al actor el rol «administra» en cada cuenta nueva')

    def handle(self, *args, **o):
        User = get_user_model()
        actor = User.objects.filter(username=o['actor']).first()
        if actor is None or not adm.es_admin_correo(actor):
            raise CommandError('El actor no existe o no es administrador del correo.')
        ruta = Path(o['csv'])
        if not ruta.is_file():
            raise CommandError(f'No existe {ruta}')
        problemas = 0
        with ruta.open(encoding='utf-8-sig', newline='') as f:
            filas = list(csv.DictReader(f, delimiter=';'))
        for fila in filas:
            direccion = (fila.get('direccion') or '').strip().lower()
            if not direccion:
                continue
            accesos, errores = [], []
            for par in (fila.get('accesos') or '').split(','):
                par = par.strip()
                if not par:
                    continue
                usuario, _, rol = par.partition(':')
                u = User.objects.filter(username=usuario.strip()).first()
                if u is None:
                    errores.append(f'usuario inexistente «{usuario}»')
                elif rol.strip() not in AccesoCuenta.NIVEL:
                    errores.append(f'rol no válido «{rol}» para {usuario}')
                else:
                    accesos.append((u, rol.strip()))
            existe = CuentaCorreo.objects.filter(direccion=direccion).first()
            if o['simular']:
                estado = 'ya existe' if existe else 'se crearía'
                self.stdout.write(f'{direccion}: {estado}; accesos: {", ".join(f"{u.username}:{r}" for u, r in accesos) or "-"}'
                                  + (f'  ¡{"; ".join(errores)}!' if errores else ''))
                problemas += len(errores)
                continue
            try:
                cuenta = existe or adm.crear_cuenta(
                    actor, direccion=direccion, nombre=fila.get('nombre') or '',
                    darme_acceso=not o['sin_actor_en_cuentas'])
                for u, rol in accesos:
                    adm.dar_acceso(actor, cuenta, u, rol)
            except ValidationError as error:
                errores.append('; '.join(error.messages))
            problemas += len(errores)
            self.stdout.write(f'{direccion}: {"error " + "; ".join(errores) if errores else "listo"}')
        self.stdout.write(self.style.WARNING(f'Con problemas: {problemas}') if problemas else self.style.SUCCESS('Sin problemas'))
