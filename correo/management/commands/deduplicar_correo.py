"""Quita los correos recibidos que quedaron duplicados (mismo Message-ID en la misma cuenta).

Por defecto solo muestra qué haría; con --aplicar borra las copias y deja la más antigua.
"""
from django.core.management.base import BaseCommand
from django.db import transaction
from django.db.models import Count

from correo.models import Adjunto, Hilo, Mensaje


class Command(BaseCommand):
    help = 'Borra copias duplicadas de correos recibidos (misma cuenta y mismo Message-ID).'

    def add_arguments(self, parser):
        parser.add_argument('--aplicar', action='store_true', help='Borrar de verdad (sin esto solo informa).')

    def handle(self, *args, **opciones):
        grupos = (Mensaje.objects.filter(estado_envio=Mensaje.RECIBIDO).exclude(message_id='')
                  .values('cuenta', 'message_id').annotate(n=Count('id')).filter(n__gt=1))
        sobran = 0
        for g in grupos:
            copias = list(Mensaje.objects.filter(cuenta=g['cuenta'], message_id=g['message_id'],
                                                 estado_envio=Mensaje.RECIBIDO).order_by('id'))
            conservar, extras = copias[0], copias[1:]
            self.stdout.write(f'{conservar.cuenta.direccion} · {conservar.asunto[:60]!r}: '
                              f'{len(copias)} copias, se conserva #{conservar.pk} y sobran {len(extras)}')
            sobran += len(extras)
            if not opciones['aplicar']:
                continue
            for extra in extras:
                with transaction.atomic():
                    hilo_id = extra.hilo_id
                    for adjunto in Adjunto.objects.filter(mensaje=extra):
                        adjunto.archivo.delete(save=False)
                    if extra.eml:
                        extra.eml.delete(save=False)
                    extra.delete()
                    if not Mensaje.objects.filter(hilo_id=hilo_id).exists():
                        Hilo.objects.filter(pk=hilo_id).delete()
        estilo = self.style.SUCCESS if opciones['aplicar'] else self.style.WARNING
        self.stdout.write(estilo(f'Copias {"borradas" if opciones["aplicar"] else "por borrar"}: {sobran}'
                                 + ('' if opciones['aplicar'] else ' (corre con --aplicar para borrarlas)')))
