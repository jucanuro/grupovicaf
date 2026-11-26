"""Pasa los informes del editor al diseño oficial (VCF-LAB-FOR-064 + FOR-039, HU-LIMS-46).

Los informes emitidos guardan su HTML congelado; este comando lo vuelve a armar con la
estructura y el diseño actuales (carátula, notas, firma con QR y una hoja por ensayo),
con los mismos datos aprobados de la base, y vuelve a generar el PDF. También ordena los
borradores aún no emitidos. No toca los que tienen bloques convertidos en texto editable
(se reportan) ni los informes subidos a mano como PDF (sin borrador del editor).

    python manage.py regenerar_informes_diseno            # simulación: solo reporta
    python manage.py regenerar_informes_diseno --aplicar  # aplica
    python manage.py regenerar_informes_diseno --aplicar --codigo INF-2026-0003
"""
from django.core.files.base import ContentFile
from django.core.management.base import BaseCommand
from django.db import transaction

from proyectos.informe_editor import (
    MODO_PDF, bloques_editados, documento_inicial, generar_pdf_borrador, html_informe,
)
from proyectos.models import BorradorInforme, InformeFinal


class Command(BaseCommand):
    help = "Vuelve a armar los informes del editor con el diseño oficial y regenera su PDF."

    def add_arguments(self, parser):
        parser.add_argument('--aplicar', action='store_true', help="Aplica los cambios (sin esto solo reporta).")
        parser.add_argument('--codigo', help="Solo el informe con este código.")

    def handle(self, *args, **opciones):
        aplicar = opciones['aplicar']
        borradores = BorradorInforme.objects.select_related('solicitud')
        if opciones.get('codigo'):
            borradores = borradores.filter(solicitud__informe_final__codigo_informe=opciones['codigo'])
        hechos = omitidos = 0
        for borrador in borradores:
            solicitud = borrador.solicitud
            informe = InformeFinal.objects.filter(solicitud=solicitud).first()
            nombre = informe.codigo_informe if informe else f"borrador de {solicitud.codigo_solicitud}"
            if bloques_editados(borrador.contenido):
                self.stdout.write(self.style.WARNING(f"Omitido {nombre}: tiene bloques convertidos en texto editable."))
                omitidos += 1
                continue
            emitido = borrador.estado == BorradorInforme.ESTADO_EMITIDO and informe is not None
            self.stdout.write(f"{'Aplicando' if aplicar else 'Se aplicaría'}: {nombre}{' (emitido, se regenera el PDF)' if emitido else ''}")
            if not aplicar:
                continue
            with transaction.atomic():
                borrador.contenido = documento_inicial(solicitud)
                campos = ['contenido', 'actualizado_en']
                if emitido:
                    borrador.html_emitido = html_informe(borrador, MODO_PDF, informe=informe, firmante=informe.responsable_firma)
                    campos.append('html_emitido')
                borrador.save(update_fields=campos)
            if emitido:
                pdf = generar_pdf_borrador(borrador.html_emitido)
                anterior = informe.archivo_pdf.name if informe.archivo_pdf else None
                informe.archivo_pdf.save(f"{informe.codigo_informe}.pdf", ContentFile(pdf), save=False)
                informe.pdf_estado = InformeFinal.PDF_LISTO
                informe.pdf_error = ''
                informe.save(update_fields=['archivo_pdf', 'pdf_estado', 'pdf_error'])
                if anterior and anterior != informe.archivo_pdf.name:
                    informe.archivo_pdf.storage.delete(anterior)
            hechos += 1
        manuales = InformeFinal.objects.filter(solicitud__borrador_informe__isnull=True).count()
        self.stdout.write(self.style.SUCCESS(
            f"{'Listo' if aplicar else 'Simulación'}: {hechos} informe(s)/borrador(es), {omitidos} omitido(s). "
            f"{manuales} informe(s) subido(s) a mano sin borrador del editor no se tocan."))
