"""Pasa a «No deseado» los correos recibidos en chino, japonés o coreano que ya están en la bandeja de entrada.

Por defecto solo informa; con --aplicar los mueve. No toca a clientes activos ni remitentes de confianza.
"""
import re

from django.core.management.base import BaseCommand

from correo.models import Carpeta, Mensaje
from correo.recepcion import _de_confianza, _fraccion_cjk


class Command(BaseCommand):
    help = 'Mueve a No deseado los correos en chino/japonés/coreano de la bandeja de entrada.'

    def add_arguments(self, parser):
        parser.add_argument('--aplicar', action='store_true', help='Mover de verdad (sin esto solo informa).')

    def handle(self, *args, **opciones):
        total = 0
        entrada = Mensaje.objects.filter(estado_envio=Mensaje.RECIBIDO, carpeta__tipo=Carpeta.ENTRADA)
        for m in entrada.select_related('cuenta', 'hilo').iterator():
            visible = re.sub(r'<[^>]+>', ' ', m.cuerpo_texto or m.cuerpo_html or '')[:4000]
            if _fraccion_cjk(f'{m.asunto} {m.de_nombre}') <= 0.3 and _fraccion_cjk(visible) <= 0.3:
                continue
            if _de_confianza({'correo': m.de.lower(), 'nombre': m.de_nombre}):
                continue
            total += 1
            self.stdout.write(f'{m.cuenta.direccion} · {m.de} · {m.asunto[:50]!r}')
            if opciones['aplicar']:
                spam = Carpeta.objects.filter(cuenta=m.cuenta, tipo=Carpeta.SPAM).first()
                if spam:
                    m.carpeta = spam
                    m.save(update_fields=['carpeta'])
        estilo = self.style.SUCCESS if opciones['aplicar'] else self.style.WARNING
        self.stdout.write(estilo(f'Correos {"movidos" if opciones["aplicar"] else "por mover"}: {total}'
                                 + ('' if opciones['aplicar'] else ' (corre con --aplicar para moverlos)')))
