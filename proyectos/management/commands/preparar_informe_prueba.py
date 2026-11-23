"""Deja una solicitud con todos sus resultados aprobados para probar el editor
del informe en local (solo DEBUG=True).

    python manage.py preparar_informe_prueba                 # la solicitud más reciente sin informe
    python manage.py preparar_informe_prueba --solicitud 12
"""
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.urls import reverse
from django.utils import timezone

from proyectos.models import InformeFinal, ResultadoEnsayo, SolicitudEnsayo

RESUMEN_PRUEBA = "Resultado de prueba generado con preparar_informe_prueba (dato ficticio)."


class Command(BaseCommand):
    help = "Aprueba todos los resultados de una solicitud para probar el editor del informe (solo DEBUG=True)."

    def add_arguments(self, parser):
        parser.add_argument('--solicitud', type=int, help="ID de la solicitud (por defecto, la más reciente sin informe).")

    def handle(self, *args, **opciones):
        # Marca resultados como aprobados: nunca en producción.
        if not settings.DEBUG:
            raise CommandError("preparar_informe_prueba es solo para desarrollo (DEBUG=True).")

        if opciones.get('solicitud'):
            solicitud = SolicitudEnsayo.objects.filter(pk=opciones['solicitud']).first()
            if solicitud is None:
                raise CommandError(f"No existe la solicitud {opciones['solicitud']}.")
        else:
            con_informe = InformeFinal.objects.values_list('solicitud_id', flat=True)
            solicitud = (
                SolicitudEnsayo.objects.filter(detalles__isnull=False).exclude(pk__in=con_informe)
                .order_by('-pk').distinct().first()
            )
            if solicitud is None:
                raise CommandError("No hay ninguna solicitud con ensayos y sin informe.")
        if InformeFinal.objects.filter(solicitud=solicitud).exists():
            raise CommandError(f"{solicitud.codigo_solicitud} ya tiene informe; elige otra con --solicitud.")

        ahora = timezone.now()
        hoy = timezone.localdate()
        creados = 0
        with transaction.atomic():
            for d in solicitud.detalles.select_related('tecnico_asignado'):
                e, nuevo = ResultadoEnsayo.objects.get_or_create(
                    detalle=d, defaults={'plantilla': ResultadoEnsayo.plantilla_para(d)},
                )
                creados += nuevo
                if not e.fecha_ensayo:
                    e.fecha_ensayo = hoy
                if not e.es_compresion and not e.resumen.strip():
                    e.resumen = RESUMEN_PRUEBA
                e.estado = ResultadoEnsayo.ESTADO_APROBADO
                e.tecnico = e.tecnico or d.tecnico_asignado
                e.terminado_en = e.terminado_en or ahora
                e.aprobado_en = ahora
                e.observacion_revision = ''
                e.save()
            solicitud.sincronizar_estado()

        total = solicitud.detalles.count()
        self.stdout.write(self.style.SUCCESS(
            f"{solicitud.codigo_solicitud}: {total} resultado(s) aprobado(s) ({creados} nuevo(s))."
        ))
        self.stdout.write(f"Abre: {reverse('proyectos:editor_informe', args=[solicitud.pk])}")
        self.stdout.write(
            "Para firmar y emitir usa un usuario con ficha de trabajador que no sea el técnico de esas líneas."
        )
