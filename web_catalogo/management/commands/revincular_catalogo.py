"""Revincula el catálogo web contra los Servicio reales de ESTA base de datos.

Se corre en producción, después de `loaddata web_dump.json` (y de
`cargar_servicios_publicados`, que debe ir antes de ese loaddata — ver
CLAUDE.md). El volcado que sube desde dev deja vacíos:

- ``ServicioPublicado.servicio``
- ``LineaServicio.ensayos`` (M2M)
- ``Acreditacion.servicios_acreditados`` (M2M)

porque esos campos apuntan a IDs de ``servicios.Servicio`` de la base de
origen, que no coinciden con los de producción (99 Servicio en dev, 14 en
AWS). Este comando busca, en el catálogo real de esta base, el Servicio
correspondiente a cada snapshot guardado en ``web_dump_relink.json``
(nombre + código de facturación), y propone el vínculo.

Emparejamiento, en orden de confianza:
1. alta — coincide el código de facturación exacto (único en Servicio).
2. alta — coincide el nombre normalizado (sin tildes/mayúsculas/puntuación)
   con un único Servicio.
3. media — nombre normalizado "parecido" (difflib) a un único Servicio.
4. ambiguo — varios candidatos igual de válidos: se reporta, no se adivina.
5. sin match — ningún candidato: se reporta, no se adivina.

MODO DRY-RUN POR DEFECTO: sin ``--apply`` solo imprime el reporte. Con
``--apply`` escribe los vínculos de confianza alta y media; los ambiguos y
sin match nunca se escriben solos y quedan para revisión manual en el admin.
"""
import difflib
import json
import unicodedata

from django.core.management.base import BaseCommand, CommandError

from servicios.models import Servicio
from web_acreditacion.models import Acreditacion
from web_catalogo.models import LineaServicio, ServicioPublicado

UMBRAL_PARECIDO = 0.82


def normalizar(texto):
    texto = unicodedata.normalize('NFKD', texto or '').encode('ascii', 'ignore').decode('ascii')
    return ' '.join(texto.lower().split())


def buscar_candidato(snapshot, por_codigo, por_nombre_norm, nombres_norm):
    """Devuelve (servicio_o_None, etiqueta_confianza, alternativas_si_ambiguo)."""
    codigo = snapshot.get('codigo_facturacion')
    if codigo and codigo in por_codigo:
        return por_codigo[codigo], 'alta (código de facturación)', []

    nombre_norm = snapshot.get('nombre_normalizado') or normalizar(snapshot.get('nombre', ''))
    exactos = por_nombre_norm.get(nombre_norm, [])
    if len(exactos) == 1:
        return exactos[0], 'alta (nombre exacto)', []
    if len(exactos) > 1:
        return None, 'ambiguo (varios Servicio con el mismo nombre)', exactos

    parecidos = difflib.get_close_matches(nombre_norm, nombres_norm, n=3, cutoff=UMBRAL_PARECIDO)
    candidatos = [s for n in parecidos for s in por_nombre_norm[n]]
    if len(candidatos) == 1:
        return candidatos[0], 'media (nombre similar)', []
    if candidatos:
        return None, 'ambiguo (varios nombres similares)', candidatos
    return None, 'sin match', []


def bucket(confianza):
    for prefijo in ('alta', 'media', 'ambiguo'):
        if confianza.startswith(prefijo):
            return prefijo
    return 'sin_match'


class Command(BaseCommand):
    help = (
        'Revincula ServicioPublicado.servicio y los M2M de LineaServicio/Acreditacion '
        'contra el catálogo real de esta base, por código de facturación o nombre '
        'normalizado. Dry-run por defecto.'
    )

    def add_arguments(self, parser):
        parser.add_argument('relink_file', help='Ruta a web_dump_relink.json (de exportar_datos_web).')
        parser.add_argument(
            '--apply', action='store_true',
            help='Escribe los vínculos de confianza alta/media. Sin esto solo se reporta.',
        )

    def handle(self, *args, **opciones):
        try:
            with open(opciones['relink_file'], encoding='utf-8') as f:
                relink = json.load(f)
        except FileNotFoundError as exc:
            raise CommandError(f'No existe {opciones["relink_file"]!r}.') from exc

        servicios = list(Servicio.objects.all())
        por_codigo = {s.codigo_facturacion: s for s in servicios}
        por_nombre_norm = {}
        for s in servicios:
            por_nombre_norm.setdefault(normalizar(s.nombre), []).append(s)
        nombres_norm = list(por_nombre_norm.keys())

        aplicar = opciones['apply']
        resumen = {'alta': 0, 'media': 0, 'ambiguo': 0, 'sin_match': 0}

        self.stdout.write(
            self.style.SUCCESS('MODO --apply: se escriben los vínculos de confianza alta/media.')
            if aplicar else
            self.style.WARNING('DRY-RUN: no se escribe nada. Vuelve a correr con --apply para confirmar.')
        )

        def evaluar_y_reportar(etiqueta, snapshot):
            candidato, confianza, alternativas = buscar_candidato(snapshot, por_codigo, por_nombre_norm, nombres_norm)
            resumen[bucket(confianza)] += 1
            linea = f'  [{confianza}] {etiqueta} -> "{snapshot.get("nombre")}"'
            if candidato:
                linea += f' => Servicio #{candidato.pk} "{candidato.nombre}" ({candidato.codigo_facturacion})'
            elif alternativas:
                opciones_txt = ', '.join(f'#{a.pk} "{a.nombre}"' for a in alternativas[:5])
                linea += f' => candidatos: {opciones_txt}'
            self.stdout.write(linea)
            return candidato, confianza

        self.stdout.write('\n== ServicioPublicado.servicio ==')
        for entrada in relink.get('servicios_publicados', []):
            snapshot = entrada.get('servicio_snapshot')
            if snapshot is None:
                continue
            try:
                publicado = ServicioPublicado.objects.get(pk=entrada['pk'])
            except ServicioPublicado.DoesNotExist:
                self.stdout.write(self.style.ERROR(
                    f"  pk={entrada['pk']}: no existe en esta base "
                    "(¿corriste cargar_servicios_publicados antes del loaddata?)."
                ))
                continue
            if publicado.servicio_id is not None:
                continue
            candidato, confianza = evaluar_y_reportar(publicado.titulo_publico, snapshot)
            if aplicar and candidato and bucket(confianza) in ('alta', 'media'):
                publicado.servicio = candidato
                publicado.save(update_fields=['servicio'])

        self.stdout.write('\n== LineaServicio.ensayos ==')
        for slug, snapshots in relink.get('linea_ensayos', {}).items():
            try:
                linea = LineaServicio.objects.get(slug=slug)
            except LineaServicio.DoesNotExist:
                self.stdout.write(self.style.ERROR(f'  {slug}: LineaServicio no existe en esta base.'))
                continue
            for snapshot in snapshots:
                candidato, confianza = evaluar_y_reportar(f'línea "{slug}"', snapshot)
                if aplicar and candidato and bucket(confianza) in ('alta', 'media'):
                    linea.ensayos.add(candidato)

        self.stdout.write('\n== Acreditacion.servicios_acreditados ==')
        for numero, snapshots in relink.get('acreditacion_servicios', {}).items():
            acreditaciones = list(Acreditacion.objects.filter(numero_acreditacion=numero))
            if not acreditaciones:
                self.stdout.write(self.style.ERROR(f'  {numero}: Acreditacion no existe en esta base.'))
                continue
            if len(acreditaciones) > 1:
                self.stdout.write(self.style.ERROR(
                    f'  {numero}: hay {len(acreditaciones)} Acreditacion con ese número; se omite (ambiguo).'
                ))
                continue
            acreditacion = acreditaciones[0]
            for snapshot in snapshots:
                candidato, confianza = evaluar_y_reportar(f'acreditación "{numero}"', snapshot)
                if aplicar and candidato and bucket(confianza) in ('alta', 'media'):
                    acreditacion.servicios_acreditados.add(candidato)

        self.stdout.write('\n== Resumen ==')
        for etiqueta, cantidad in resumen.items():
            self.stdout.write(f'  {etiqueta}: {cantidad}')
        if resumen['ambiguo'] or resumen['sin_match']:
            self.stdout.write(self.style.WARNING(
                'Hay casos ambiguos o sin match: revisar y vincular a mano desde el admin.'
            ))
        if not aplicar:
            self.stdout.write(self.style.WARNING('Dry-run: no se escribió nada.'))
