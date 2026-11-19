"""Genera contraseñas temporales para los usuarios del CSV de cuentas.

    python manage.py generar_accesos deploy/correo/cuentas_iniciales.csv --salida /root/claves.csv          (vista previa)
    python manage.py generar_accesos deploy/correo/cuentas_iniciales.csv --salida /root/claves.csv --aplicar

- Por defecto NO cambia nada: solo lista a quién se la generaría. Con --aplicar
  guarda cada contraseña cifrada y marca «debe cambiarla» en el primer ingreso.
- Las contraseñas en claro van SOLO al archivo --salida (permisos 600, no se
  sobrescribe uno existente). No se imprimen ni se registran en logs.
- Se salta a quien ya ingresó alguna vez (last_login), salvo --incluir-con-sesion;
  --excluir usuarios que no deben tocarse (p. ej. el administrador).
- Entrega cada clave por un canal privado y borra el archivo después.
"""
import csv
import os
import secrets
from pathlib import Path

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from trabajadores.models import TrabajadorProfile

from ._accesos_csv import esperado_por_usuario

# Sin caracteres ambiguos (0/O, 1/l/I).
ALFABETO = 'abcdefghjkmnpqrstuvwxyzABCDEFGHJKLMNPQRSTUVWXYZ23456789'


def nueva_clave():
    """Tres bloques de 4 caracteres: Ab3k-Xm9p-Qr7t (12 símbolos, ~68 bits)."""
    return '-'.join(''.join(secrets.choice(ALFABETO) for _ in range(4)) for _ in range(3))


class Command(BaseCommand):
    help = 'Genera contraseñas temporales (cambio obligatorio al primer ingreso).'

    def add_arguments(self, parser):
        parser.add_argument('csv')
        parser.add_argument('--salida', required=True, help='archivo CSV donde se escriben las claves')
        parser.add_argument('--aplicar', action='store_true', help='aplicar de verdad (sin esto solo es vista previa)')
        parser.add_argument('--excluir', default='', help='usuarios separados por coma que no se tocan')
        parser.add_argument('--incluir-con-sesion', action='store_true',
                            help='también a quien ya inició sesión alguna vez')

    def handle(self, *args, **o):
        User = get_user_model()
        excluidos = {x.strip() for x in o['excluir'].split(',') if x.strip()}
        destino = Path(o['salida'])
        if o['aplicar'] and destino.exists():
            raise CommandError(f'{destino} ya existe: no se sobrescribe. Bórralo o usa otro nombre.')

        candidatos = []
        for usuario in esperado_por_usuario(o['csv']):
            if usuario in excluidos:
                self.stdout.write(f'- {usuario}: excluido')
                continue
            u = User.objects.filter(username=usuario, is_active=True).first()
            if u is None:
                self.stdout.write(self.style.WARNING(f'! {usuario}: no existe o está inactivo, se omite'))
                continue
            if u.last_login and not o['incluir_con_sesion']:
                self.stdout.write(f'- {usuario}: ya inició sesión antes, se omite (usa --incluir-con-sesion)')
                continue
            candidatos.append(u)

        if not o['aplicar']:
            for u in candidatos:
                self.stdout.write(f'· {u.username}: se le generaría una clave temporal')
            self.stdout.write(self.style.WARNING(f'Vista previa: {len(candidatos)} usuario(s). Nada cambió; agrega --aplicar.'))
            return

        filas = []
        with transaction.atomic():
            for u in candidatos:
                clave = nueva_clave()
                u.set_password(clave)
                u.save(update_fields=['password'])
                TrabajadorProfile.objects.filter(user=u).update(debe_cambiar_clave=True)
                filas.append((u.username, u.email, clave))
        descriptor = os.open(destino, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(descriptor, 'w', encoding='utf-8', newline='') as f:
            escritor = csv.writer(f, delimiter=';')
            escritor.writerow(['usuario', 'correo', 'clave_temporal'])
            escritor.writerows(filas)
        self.stdout.write(self.style.SUCCESS(
            f'{len(filas)} clave(s) generadas en {destino} (permisos 600). Entrégalas en privado y borra el archivo.'))
