"""Importa el contenido publicado en vicafpro (fixtures dumpdata en
_ref/fixtures/) hacia el nuevo esquema web_inicio / web_nosotros.

Idempotente: se puede correr varias veces sin duplicar filas. Usa
update_or_create sobre una clave natural por modelo (no hay pk compartido
entre el esquema viejo y el nuevo).
"""
import json
import shutil
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand
from django.utils.text import slugify

from web_inicio.models import CarruselInicio
from web_nosotros.models import DocumentoNosotros, Nosotros, TipoDocumentoNosotros


class Contador:
    def __init__(self):
        self.creados = 0
        self.actualizados = 0
        self.omitidos = []

    def registrar_omision(self, motivo):
        self.omitidos.append(motivo)

    def resumen(self, etiqueta):
        lineas = [f'{etiqueta}: {self.creados} creado(s), {self.actualizados} actualizado(s)']
        if self.omitidos:
            lineas.append(f'  omitidos ({len(self.omitidos)}):')
            lineas += [f'    - {motivo}' for motivo in self.omitidos]
        return '\n'.join(lineas)


class Command(BaseCommand):
    help = 'Importa carrusel de inicio y contenido de Nosotros desde _ref/fixtures/ y _ref/media_vicafpro/.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--fixtures-dir', default=str(settings.BASE_DIR / '_ref' / 'fixtures'),
            help='Carpeta con los JSON exportados de vicafpro (default: _ref/fixtures/).',
        )
        parser.add_argument(
            '--media-dir', default=str(settings.BASE_DIR / '_ref' / 'media_vicafpro'),
            help='Carpeta con los archivos media de vicafpro (default: _ref/media_vicafpro/).',
        )

    def handle(self, *args, **options):
        fixtures_dir = Path(options['fixtures_dir'])
        media_dir = Path(options['media_dir'])

        self.stdout.write(f'Fixtures: {fixtures_dir}')
        self.stdout.write(f'Media origen: {media_dir}')
        self.stdout.write('')

        contador_carrusel = self._importar_inicio(fixtures_dir / 'inicio.json', media_dir)
        self.stdout.write(contador_carrusel.resumen('CarruselInicio'))
        self.stdout.write('')

        contadores_nosotros = self._importar_nosotros(fixtures_dir / 'nosotros.json', media_dir)
        for etiqueta, contador in contadores_nosotros.items():
            self.stdout.write(contador.resumen(etiqueta))
        self.stdout.write('')

        self.stdout.write(self.style.WARNING(
            'Acreditacion: no existe fixture equivalente en vicafpro (modelo nuevo); nada que importar.'
        ))
        self.stdout.write(self.style.SUCCESS('Importación finalizada.'))

    # -- helpers de carga -------------------------------------------------

    def _cargar_fixture(self, ruta):
        if not ruta.exists():
            self.stdout.write(self.style.WARNING(f'{ruta.name} no existe, se omite.'))
            return []
        with open(ruta, encoding='utf-8') as f:
            data = json.load(f)
        if not data:
            self.stdout.write(f'{ruta.name} está vacío, nada que importar.')
        return data

    def _copiar_media(self, media_dir, ruta_relativa, contador, descripcion):
        """Copia media_dir/ruta_relativa a MEDIA_ROOT/ruta_relativa si existe. Devuelve la ruta relativa o None."""
        if not ruta_relativa:
            return None
        origen = media_dir / ruta_relativa
        if not origen.exists():
            contador.registrar_omision(f'{descripcion}: archivo no encontrado en {origen}')
            return None
        destino = Path(settings.MEDIA_ROOT) / ruta_relativa
        destino.parent.mkdir(parents=True, exist_ok=True)
        if not destino.exists():
            shutil.copyfile(origen, destino)
        return ruta_relativa

    # -- inicio.json --------------------------------------------------

    def _importar_inicio(self, ruta, media_dir):
        contador = Contador()
        for entrada in self._cargar_fixture(ruta):
            if entrada.get('model') != 'inicio.carruselinicio':
                contador.registrar_omision(f'modelo desconocido {entrada.get("model")!r}')
                continue
            fields = entrada.get('fields', {})
            titulo = (fields.get('titulo') or '').strip()
            if not titulo:
                contador.registrar_omision(f'pk={entrada.get("pk")}: sin título')
                continue

            imagen = self._copiar_media(media_dir, fields.get('imagen'), contador, f'carrusel "{titulo}"')
            if not imagen:
                contador.registrar_omision(f'carrusel "{titulo}": sin imagen, se omite (campo obligatorio)')
                continue

            _, creado = CarruselInicio.objects.update_or_create(
                titulo=titulo,
                defaults={
                    'descripcion': fields.get('descripcion') or '',
                    'imagen': imagen or '',
                    'alt_text': fields.get('alt_text') or titulo,
                    'enlace': fields.get('enlace') or '',
                    'orden': entrada.get('pk') or 0,
                },
            )
            contador.creados += int(creado)
            contador.actualizados += int(not creado)
        return contador

    # -- nosotros.json --------------------------------------------------

    def _importar_nosotros(self, ruta, media_dir):
        contador_nosotros = Contador()
        contador_tipos = Contador()
        contador_documentos = Contador()

        entradas = self._cargar_fixture(ruta)

        modelos_reconocidos = {'nosotros.nosotros', 'nosotros.tipodocumentonosotros', 'nosotros.documentonosotros'}
        entradas_nosotros = [e for e in entradas if e.get('model') == 'nosotros.nosotros']
        entradas_tipos = [e for e in entradas if e.get('model') == 'nosotros.tipodocumentonosotros']
        entradas_documentos = [e for e in entradas if e.get('model') == 'nosotros.documentonosotros']
        for entrada in entradas:
            if entrada.get('model') not in modelos_reconocidos:
                contador_nosotros.registrar_omision(f'modelo desconocido {entrada.get("model")!r}')

        for entrada in entradas_nosotros:
            fields = entrada.get('fields', {})
            titulo = (fields.get('titulo') or '').strip()
            if not titulo:
                contador_nosotros.registrar_omision(f'pk={entrada.get("pk")}: sin título')
                continue

            imagen = self._copiar_media(media_dir, fields.get('imagen'), contador_nosotros, f'Nosotros "{titulo}"')
            contenido = fields.get('contenido') or ''

            _, creado = Nosotros.objects.update_or_create(
                titulo=titulo,
                defaults={
                    'contenido': contenido,
                    'imagen': imagen or '',
                    'imagen_alt': titulo if imagen else '',
                    'slug': self._slug_para(Nosotros, {'titulo': titulo}, titulo),
                    'meta_description': self._resumen_meta(contenido),
                },
            )
            contador_nosotros.creados += int(creado)
            contador_nosotros.actualizados += int(not creado)

        tipos_por_pk = {}
        for entrada in entradas_tipos:
            fields = entrada.get('fields', {})
            nombre = (fields.get('nombre') or '').strip()
            if not nombre:
                contador_tipos.registrar_omision(f'pk={entrada.get("pk")}: sin nombre')
                continue

            descripcion = fields.get('descripcion') or ''
            obj, creado = TipoDocumentoNosotros.objects.update_or_create(
                nombre=nombre,
                defaults={
                    'descripcion': descripcion,
                    'orden': fields.get('orden') or 0,
                    'activo': fields.get('activo', True),
                    'slug': self._slug_para(TipoDocumentoNosotros, {'nombre': nombre}, fields.get('slug') or nombre),
                    'meta_description': self._resumen_meta(descripcion or nombre),
                },
            )
            contador_tipos.creados += int(creado)
            contador_tipos.actualizados += int(not creado)
            tipos_por_pk[entrada.get('pk')] = obj

        for entrada in entradas_documentos:
            fields = entrada.get('fields', {})
            titulo = (fields.get('titulo') or '').strip()
            if not titulo:
                contador_documentos.registrar_omision(f'pk={entrada.get("pk")}: sin título')
                continue

            tipo_pk = fields.get('tipo')
            tipo = tipos_por_pk.get(tipo_pk)
            if tipo is None:
                contador_documentos.registrar_omision(f'documento "{titulo}": tipo pk={tipo_pk} no encontrado')
                continue

            archivo = self._copiar_media(media_dir, fields.get('archivo'), contador_documentos, f'documento "{titulo}"')
            if not archivo:
                contador_documentos.registrar_omision(f'documento "{titulo}": sin archivo, se omite (campo obligatorio)')
                continue
            imagen = self._copiar_media(media_dir, fields.get('imagen'), contador_documentos, f'documento "{titulo}" (imagen)')

            _, creado = DocumentoNosotros.objects.update_or_create(
                tipo=tipo, titulo=titulo,
                defaults={
                    'descripcion': fields.get('descripcion') or '',
                    'imagen': imagen or '',
                    'archivo': archivo,
                    'orden': fields.get('orden') or 0,
                    'activo': fields.get('activo', True),
                    'destacado': fields.get('destacado', False),
                    'fecha_publicacion': fields.get('fecha_publicacion') or None,
                },
            )
            contador_documentos.creados += int(creado)
            contador_documentos.actualizados += int(not creado)

        return {
            'Nosotros': contador_nosotros,
            'TipoDocumentoNosotros': contador_tipos,
            'DocumentoNosotros': contador_documentos,
        }

    # -- utilidades SEO --------------------------------------------------

    def _slug_disponible(self, modelo, texto):
        base = slugify(texto)[:50] or 'sin-titulo'
        slug = base
        i = 2
        while modelo.objects.filter(slug=slug).exists():
            sufijo = f'-{i}'
            slug = f'{base[:50 - len(sufijo)]}{sufijo}'
            i += 1
        return slug

    def _slug_para(self, modelo, titulo_lookup, texto):
        """Reutiliza el slug ya asignado si el registro existe (evita
        regenerar uno nuevo -y romper idempotencia- en cada corrida)."""
        existente = modelo.objects.filter(**titulo_lookup).only('slug').first()
        if existente:
            return existente.slug
        return self._slug_disponible(modelo, texto)

    def _resumen_meta(self, texto):
        texto = ' '.join((texto or '').split())
        if len(texto) <= 160:
            return texto
        return texto[:157].rsplit(' ', 1)[0] + '...'
