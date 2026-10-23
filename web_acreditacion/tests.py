"""Pruebas de las certificaciones (specs/WEB v4, T18-T20; v6, T22; cabeceras de v3, T15) y de los ensayos acreditados (v6, T22)."""
import importlib
import io
import json
import os
import re
import shutil
import tempfile
from datetime import date, timedelta

from django.core.cache import cache
from django.db import connection
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import RequestFactory, TestCase, override_settings
from django.test.utils import CaptureQueriesContext
from django.urls import clear_url_caches, resolve, reverse
from django.utils import timezone
from PIL import Image

from servicios.models import CategoriaServicio, Metodo, Norma, Servicio
from web_catalogo.models import LineaServicio, ServicioPublicado

from .models import Acreditacion, Certificacion, validar_archivo
from .views import _orden_alfabetico, servir_certificado_dev

PDF_MINIMO = b'%PDF-1.4\n1 0 obj<<>>endobj\ntrailer<<>>\n%%EOF\n'


def _png_minimo():
    buffer = io.BytesIO()
    Image.new('RGB', (2, 1), 'white').save(buffer, 'PNG')
    return buffer.getvalue()


PNG_MINIMO = _png_minimo()


def pdf(nombre='certificado.pdf', contenido=PDF_MINIMO):
    return SimpleUploadedFile(nombre, contenido, content_type='application/pdf')


def png(nombre='certificado.png', contenido=PNG_MINIMO):
    return SimpleUploadedFile(nombre, contenido, content_type='image/png')


class MediaTemporalMixin:
    """MEDIA_ROOT en un directorio temporal para no ensuciar mediafiles/."""

    @classmethod
    def setUpClass(cls):
        cls._media = tempfile.mkdtemp()
        override_media = override_settings(MEDIA_ROOT=cls._media)
        override_media.enable()
        # Como class cleanup y antes de super(): el override_settings de clase
        # también se deshace con addClassCleanup y restaura los settings que vio
        # al activarse; en orden LIFO se deshace primero el suyo y luego este.
        cls.addClassCleanup(shutil.rmtree, cls._media, ignore_errors=True)
        cls.addClassCleanup(override_media.disable)
        super().setUpClass()

    # El footer cachea las líneas del catálogo (web_catalogo.context_processors);
    # sin limpiar, otras pruebas heredan objetos leídos con este MEDIA_ROOT.
    def setUp(self):
        super().setUp()
        cache.clear()

    def tearDown(self):
        cache.clear()
        super().tearDown()

    def crear_certificacion(self, **campos):
        datos = {
            'titulo': 'Certificación ISO 9001:2015',
            'descripcion': 'Sistema de Gestión de la Calidad certificado por AENOR.',
            'tipo': Certificacion.TIPO_ISO,
            'institucion': 'AENOR CONFIA S.A.U.',
            'vigencia_hasta': timezone.localdate() + timedelta(days=365),
            'archivo': pdf(),
            'orden': 10,
        }
        datos.update(campos)
        return Certificacion.objects.create(**datos)


class CertificacionModelTests(MediaTemporalMixin, TestCase):
    def test_codigo_corto_sale_del_titulo(self):
        # REQ-WEB-71: código del panel de color, sin campo nuevo.
        casos = {
            'Acreditación INACAL LE-230': 'LE-230',
            'Certificación ISO 9001:2015': 'ISO 9001:2015',
            'Certificado ISO/IEC 17025:2017': 'ISO/IEC 17025:2017',
            'ISO 45001': 'ISO 45001',
            'Reconocimiento municipal': '',
        }
        for titulo, codigo in casos.items():
            self.assertEqual(Certificacion(titulo=titulo).codigo_corto, codigo, titulo)

    def test_migracion_pasa_inacal_e_iso9001_al_modelo_unico(self):
        # REQ-WEB-41: la 0005 convierte la semilla ISO 9001 de v3 y crea INACAL.
        inacal = Certificacion.objects.get(tipo=Certificacion.TIPO_ACREDITACION)
        self.assertEqual(inacal.titulo, 'Acreditación INACAL LE-230')
        self.assertEqual(inacal.institucion, 'Instituto Nacional de Calidad (INACAL)')
        self.assertIn('LE-230', inacal.descripcion)
        self.assertEqual(inacal.vigencia_hasta, date(2027, 5, 27))
        self.assertEqual(inacal.archivo.name, 'certificaciones/inacal-le-230.webp')
        self.assertFalse(inacal.es_pdf)
        self.assertEqual(inacal.orden, 0)

        iso = Certificacion.objects.get(tipo=Certificacion.TIPO_ISO)
        self.assertEqual(iso.titulo, 'Certificación ISO 9001:2015')
        self.assertEqual(iso.institucion, 'AENOR CONFIA S.A.U.')
        self.assertEqual(
            iso.descripcion,
            'Sistema de Gestión de la Calidad certificado por AENOR CONFIA. Certificado N.º ER-0146/2026.',
        )
        self.assertEqual(iso.vigencia_hasta, date(2029, 4, 1))
        self.assertEqual(iso.orden, 1)
        # La semilla de v3 no traía PDF: no se publica hasta que se suba.
        self.assertFalse(iso.archivo)
        self.assertFalse(iso.publicada)

    def test_publicadas_aplica_rn15(self):
        # REQ-WEB-42: activa + con archivo + vigencia vacía o sin pasar; el último día cuenta.
        Certificacion.objects.all().delete()
        hoy = timezone.localdate()
        vigente = self.crear_certificacion(titulo='A')
        sin_vigencia = self.crear_certificacion(titulo='B', vigencia_hasta=None)
        ultimo_dia = self.crear_certificacion(titulo='C', vigencia_hasta=hoy)
        vencida = self.crear_certificacion(titulo='D', vigencia_hasta=hoy - timedelta(days=1))
        inactiva = self.crear_certificacion(titulo='E', activo=False)
        sin_archivo = self.crear_certificacion(titulo='F', archivo='')

        self.assertEqual(set(Certificacion.objects.publicadas()), {vigente, sin_vigencia, ultimo_dia})
        for certificacion in (vigente, sin_vigencia, ultimo_dia):
            self.assertTrue(certificacion.publicada, certificacion.titulo)
        for certificacion in (vencida, inactiva, sin_archivo):
            self.assertFalse(certificacion.publicada, certificacion.titulo)

    def test_publicadas_con_fecha_explicita(self):
        cert = self.crear_certificacion(vigencia_hasta=date(2029, 4, 1))
        self.assertIn(cert, Certificacion.objects.publicadas(hoy=date(2029, 4, 1)))
        self.assertNotIn(cert, Certificacion.objects.publicadas(hoy=date(2029, 4, 2)))

    def test_es_pdf_por_extension(self):
        self.assertTrue(self.crear_certificacion().es_pdf)
        self.assertFalse(self.crear_certificacion(archivo=png()).es_pdf)
        self.assertFalse(Certificacion(archivo='').es_pdf)

    def test_validar_archivo_acepta_pdf_e_imagen_reales(self):
        # REQ-WEB-40: firma %PDF-, imagen que Pillow abre y máximo 10 MB.
        validar_archivo(pdf())
        validar_archivo(png())
        for archivo in (
            pdf('falso.pdf', b'<html>no soy un pdf</html>'),
            png('falso.png', b'%PDF-1.4 no soy una imagen'),
            png('falso.webp', b'nada'),
        ):
            with self.subTest(archivo=archivo.name), self.assertRaises(ValidationError):
                validar_archivo(archivo)
        grande = pdf()
        grande.size = 10 * 1024 * 1024 + 1
        with self.assertRaises(ValidationError):
            validar_archivo(grande)

    def test_full_clean_exige_campos_y_extension_permitida(self):
        cert = Certificacion(archivo=png('certificado.gif'))
        with self.assertRaises(ValidationError) as error:
            cert.full_clean()
        for campo in ('titulo', 'descripcion', 'institucion', 'archivo'):
            self.assertIn(campo, error.exception.message_dict)
        self.assertNotIn('vigencia_hasta', error.exception.message_dict)  # opcional

        cert = Certificacion(
            titulo='Otro', descripcion='Corta.', tipo='otro', institucion='X', archivo=png(),
        )
        cert.full_clean()

    def test_tipos_del_admin(self):
        self.assertEqual(
            [etiqueta for _, etiqueta in Certificacion.TIPOS],
            ['Acreditación', 'Certificación ISO', 'Otro'],
        )


@override_settings(ROOT_URLCONF='grupovicaf.urls_web')
class AcreditacionPaginaTests(MediaTemporalMixin, TestCase):
    def get_html(self):
        respuesta = self.client.get(reverse('web_acreditacion:acreditacion'))
        self.assertEqual(respuesta.status_code, 200)
        return respuesta.content.decode()

    def test_grilla_debajo_del_hero_con_cards(self):
        # REQ-WEB-43 y 44
        cert = self.crear_certificacion(titulo='Certificación ISO 9001:2015')
        Acreditacion.objects.create(numero_acreditacion='LE-230', alcance='Ensayos de suelos.')
        html = self.get_html()
        self.assertEqual(html.count('<h1'), 1)
        hero_fin = html.index('</h1>')
        grilla = html.index('id="certificaciones"')
        self.assertLess(hero_fin, grilla)
        self.assertLess(grilla, html.index('Alcance de acreditación'))
        # REQ-WEB-72: 1 card por fila por debajo de 1280 px y 2 desde ahí, centradas, máx. 1200 px.
        self.assertIn('<ul class="reveal-group mx-auto flex max-w-[1200px] flex-wrap justify-center gap-6" role="list">', html)
        self.assertIn('reveal flex w-full max-w-2xl xl:w-[calc((100%-1.5rem)/2)] xl:max-w-none', html)
        # REQ-WEB-71: card horizontal (vertical en móvil) con panel de color por tipo.
        self.assertIn('group relative flex h-full w-full flex-col overflow-hidden rounded-card', html)
        self.assertIn('sm:min-h-[300px] sm:flex-row', html)
        self.assertIn('from-blue-950 via-blue-800 to-amber-600', html)  # ISO
        self.assertIn('from-blue-950 via-blue-800 to-vicaf-primary', html)  # Acreditación
        self.assertIn('motion-safe:hover:-translate-y-1', html)
        self.assertIn('has-[:focus-visible]:ring-[3px]', html)
        for texto in (
            'Acreditaciones y certificaciones', 'Certificación ISO 9001:2015',
            'Sistema de Gestión de la Calidad certificado por AENOR.',
            'Otorgada por <span class="font-semibold text-slate-700">AENOR CONFIA S.A.U.</span>',
            '>Certificación ISO</span>', 'Acreditación INACAL LE-230', '>Acreditación</span>',
            '>ISO 9001:2015</span>', '>LE-230</span>',
        ):
            self.assertIn(texto, html)
        # Una card = un enlace real al archivo, en pestaña nueva sin JS (REQ-WEB-46).
        self.assertIn(
            f'href="{cert.archivo.url}" target="_blank" rel="noopener" data-cert-open '
            f'data-cert-tipo="pdf" data-cert-titulo="Certificación ISO 9001:2015"', html,
        )
        self.assertIn('data-cert-tipo="imagen" data-cert-titulo="Acreditación INACAL LE-230"', html)
        self.assertIn('after:absolute after:inset-0', html)
        # Pastilla "Ver documento" y vigencia con check (sin fecha: "Vigente").
        self.assertEqual(html.count('Ver documento\n'), 2)
        vence = cert.vigencia_hasta
        self.assertIn(
            f'<span>Vigente hasta <time datetime="{vence:%Y-%m-%d}">{vence:%d/%m/%Y}</time></span>', html,
        )
        self.assertIn('<span>Vigente hasta <time datetime="2027-05-27">27/05/2027</time></span>', html)
        Certificacion.objects.filter(pk=cert.pk).update(vigencia_hasta=None)
        self.assertIn('<span>Vigente</span>', self.get_html())
        self.assertIn('Sin logo, la card muestra un sello genérico', Certificacion._meta.get_field('logo').help_text)
        # Sin el certificado grande al lado: ninguna imagen de certificado en la página.
        self.assertNotIn('GRUPO-VICAF-CERTIFICADO', html)
        self.assertNotIn('<img src="/media/certificaciones/', html)

    def test_card_con_logo_de_la_institucion(self):
        # REQ-WEB-62: el logo arriba, con alt, medidas y carga diferida (regla 17).
        cert = self.crear_certificacion(logo=png('aenor.png'))
        self.assertEqual((cert.logo_ancho, cert.logo_alto), (2, 1))
        html = self.get_html()
        self.assertIn(
            f'<img src="{cert.logo.url}" alt="Logo de AENOR CONFIA S.A.U."\n'
            f'             width="2" height="1"\n             loading="lazy" decoding="async"', html,
        )
        self.assertIn('motion-safe:group-hover:scale-105', html)
        # La card sin logo (INACAL de la migración) muestra el sello genérico.
        self.assertEqual(html.count('data-sello-generico'), 1)

    def test_validar_logo(self):
        # REQ-WEB-62: solo imagen, 2 MB como máximo.
        grande = png('grande.png', PNG_MINIMO + b'0' * (2 * 1024 * 1024))
        with self.assertRaisesMessage(ValidationError, 'El logo no puede pesar más de 2 MB.'):
            Certificacion._meta.get_field('logo').run_validators(grande)
        with self.assertRaises(ValidationError):
            Certificacion._meta.get_field('logo').run_validators(pdf('logo.pdf'))

    def test_textos_solo_cajamarca(self):
        # REQ-WEB-52 (D-VCF-002): H1, meta y textos sin "norte del Perú".
        html = self.get_html()
        self.assertNotIn('norte del per', html.lower())
        self.assertIn('Laboratorio acreditado INACAL en Cajamarca\n        </h1>', html)
        self.assertIn('<title>Laboratorio acreditado INACAL en Cajamarca', html)

    def test_orden_del_admin(self):
        self.crear_certificacion(titulo='Primero del admin', orden=0, tipo='otro')
        html = self.get_html()
        self.assertLess(html.index('Primero del admin'), html.index('Acreditación INACAL LE-230'))

    def test_modal_unico_accesible_y_js_solo_con_certificaciones(self):
        # REQ-WEB-47 y 48
        html = self.get_html()
        self.assertEqual(html.count('id="modal-certificacion"'), 1)
        self.assertIn('role="dialog" aria-modal="true" aria-labelledby="modal-certificacion-titulo"', html)
        self.assertIn('data-cert-contenido', html)
        self.assertIn('data-cert-descargar href="#" download', html)
        # REQ-WEB-64: PDF que no se puede embeber (móvil) -> aviso con "Abrir documento".
        self.assertIn('<div data-cert-alterno class="hidden', html)
        self.assertIn('data-cert-abrir href="#" target="_blank" rel="noopener"', html)
        self.assertIn('Descargar', html)
        self.assertEqual(html.count('data-cert-cerrar'), 2)  # × y "Cerrar"
        self.assertIn('web/js/certificaciones.js', html)
        # Nada se carga con la página (regla 17): el img/iframe lo crea el JS.
        self.assertNotIn('<iframe', html)
        # Los modales de v3 ya no existen.
        for viejo in ('modal-certificado-inacal', 'modal-certificado-pdf', 'certificado-pdf.js', 'modal-certificado.js'):
            self.assertNotIn(viejo, html)

    def test_acceso_inacal_del_hero_abre_la_acreditacion(self):
        # REQ-WEB-50
        html = self.get_html()
        hero = html[:html.index('id="certificaciones"')]
        self.assertIn('data-cert-titulo="Acreditación INACAL LE-230"', hero)

        Certificacion.objects.filter(tipo=Certificacion.TIPO_ACREDITACION).update(activo=False)
        hero = self.get_html().split('</h1>')[1].split('</section>')[0]
        self.assertIn('href="#certificaciones"', hero)
        self.assertNotIn('data-cert-open', hero)

    def test_vencidas_inactivas_o_sin_archivo_no_se_muestran(self):
        # REQ-WEB-42: ni card, ni modal, ni JS.
        Certificacion.objects.all().delete()
        hoy = timezone.localdate()
        self.crear_certificacion(titulo='VENCIDA', vigencia_hasta=hoy - timedelta(days=1))
        self.crear_certificacion(titulo='INACTIVA', activo=False)
        self.crear_certificacion(titulo='SINARCHIVO', archivo='')
        html = self.get_html()
        for texto in ('VENCIDA', 'INACTIVA', 'SINARCHIVO', 'id="certificaciones"', 'modal-certificacion',
                      'certificaciones.js', 'data-cert-open'):
            self.assertNotIn(texto, html)
        # La sección de alcance (modelo Acreditacion) sigue ahí.
        self.assertIn('href="#certificaciones"', html)


class CabecerasPdfTests(MediaTemporalMixin, TestCase):
    def test_pdf_de_certificaciones_embebible_solo_desde_el_mismo_origen(self):
        # REQ-WEB-37: SAMEORIGIN para /media/certificaciones/ en dev.
        os.makedirs(os.path.join(self._media, 'certificaciones'))
        with open(os.path.join(self._media, 'certificaciones', 'cert.pdf'), 'wb') as archivo:
            archivo.write(PDF_MINIMO)
        respuesta = servir_certificado_dev(RequestFactory().get('/media/certificaciones/cert.pdf'), 'cert.pdf')
        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(respuesta['X-Frame-Options'], 'SAMEORIGIN')
        self.assertEqual(respuesta['Content-Type'], 'application/pdf')

    def test_urls_web_enruta_certificaciones_antes_del_static_generico(self):
        import grupovicaf.urls_web as urls_web
        try:
            with override_settings(DEBUG=True):
                importlib.reload(urls_web)
                clear_url_caches()
                coincidencia = resolve('/media/certificaciones/cert.pdf', urlconf=urls_web)
                self.assertEqual(coincidencia.func, servir_certificado_dev)
                self.assertNotEqual(resolve('/media/acreditacion/x.png', urlconf=urls_web).func, servir_certificado_dev)
        finally:
            importlib.reload(urls_web)
            clear_url_caches()

    def test_el_resto_de_la_web_sigue_en_deny(self):
        with override_settings(ROOT_URLCONF='grupovicaf.urls_web'):
            respuesta = self.client.get(reverse('web_acreditacion:acreditacion'))
        self.assertEqual(respuesta['X-Frame-Options'], 'DENY')


@override_settings(ROOT_URLCONF='grupovicaf.urls_web', SITE_URL='https://www.grupovicaf.com')
class JsonLdTests(MediaTemporalMixin, TestCase):
    def local_business(self, nombre_url='web_contacto:contacto'):
        html = self.client.get(reverse(nombre_url)).content.decode()
        bloques = re.findall(r'<script type="application/ld\+json">(.*?)</script>', html, re.S)
        for bloque in bloques:
            datos = json.loads(bloque)  # todo bloque debe seguir siendo JSON válido
            if isinstance(datos, dict) and datos.get('@type') == 'LocalBusiness':
                return datos
        self.fail('No hay JSON-LD LocalBusiness')

    def test_has_certification_en_todas_las_paginas(self):
        # REQ-WEB-51: ISO y Otro; INACAL sigue en hasCredential y no se repite.
        Certificacion.objects.all().delete()
        self.crear_certificacion(titulo='Acreditación INACAL', tipo='acreditacion')
        cert = self.crear_certificacion(
            vigencia_hasta=date(2099, 4, 1), institucion='AENOR </script> & CONFIA',
        )
        otro = self.crear_certificacion(titulo='Reconocimiento', tipo='otro', vigencia_hasta=None, archivo=png())
        for pagina in ('web_contacto:contacto', 'web_acreditacion:acreditacion'):
            with self.subTest(pagina=pagina):
                negocio = self.local_business(pagina)
                self.assertIn('hasCredential', negocio)  # INACAL intacto
                self.assertEqual(negocio['hasCertification'], [
                    {
                        '@type': 'Certification',
                        'name': 'Certificación ISO 9001:2015',
                        'description': 'Sistema de Gestión de la Calidad certificado por AENOR.',
                        'issuedBy': {'@type': 'Organization', 'name': 'AENOR </script> & CONFIA'},
                        'certificationStatus': 'https://schema.org/CertificationActive',
                        'url': f'https://www.grupovicaf.com{cert.archivo.url}',
                        'expires': '2099-04-01',
                    },
                    {
                        '@type': 'Certification',
                        'name': 'Reconocimiento',
                        'description': 'Sistema de Gestión de la Calidad certificado por AENOR.',
                        'issuedBy': {'@type': 'Organization', 'name': 'AENOR CONFIA S.A.U.'},
                        'certificationStatus': 'https://schema.org/CertificationActive',
                        'url': f'https://www.grupovicaf.com{otro.archivo.url}',
                    },
                ])

    def test_sin_certificaciones_publicadas_no_hay_has_certification(self):
        # REQ-WEB-42: la semilla ISO sin PDF, una vencida e INACAL (hasCredential) no se declaran.
        self.crear_certificacion(vigencia_hasta=timezone.localdate() - timedelta(days=1))
        self.assertNotIn('hasCertification', self.local_business())


class EnsayosAcreditadosTests(TestCase):
    """Ensayos acreditados en lista por línea (specs/WEB v6, T22; en v5 eran cards, T21)."""

    @classmethod
    def setUpTestData(cls):
        cls.categoria = CategoriaServicio.objects.create(nombre='Suelos T21')
        cls.norma = Norma.objects.create(codigo='NTP 339.145', nombre='Suelos. Método de ensayo CBR')
        cls.metodo = Metodo.objects.create(codigo='M-T21', nombre='Compactación en molde')

        def servicio(codigo, nombre, **campos):
            return Servicio.objects.create(
                codigo_facturacion=codigo, nombre=nombre, precio_base='987.65', esta_acreditado=True, **campos,
            )

        def linea(slug, nombre, orden, activo=True):
            return LineaServicio.objects.create(
                slug=slug, nombre=nombre, titulo_h1=nombre, resumen='r', contenido='c', orden=orden, activo=activo,
            )

        cls.cbr = servicio('ZZT21-001', 'Relación de soporte de California', norma=cls.norma, metodo=cls.metodo)
        cls.humedad = servicio('ZZT21-002', 'Contenido de humedad')
        cls.ficha = servicio('ZZT21-003', 'Granulometría por tamizado')
        cls.suelto = servicio('ZZT21-004', 'Ensayo sin línea')
        cls.no_acreditado = servicio('ZZT21-005', 'Ensayo fuera del alcance')

        cls.suelos = linea('suelos-t21', 'Suelos T21', orden=901)
        cls.concreto = linea('concreto-t21', 'Concreto T21', orden=900)
        cls.inactiva = linea('inactiva-t21', 'Inactiva T21', orden=0, activo=False)
        cls.suelos.ensayos.add(cls.cbr, cls.humedad)
        # El CBR también está en una línea anterior en el orden: va solo ahí (REQ-WEB-54).
        cls.concreto.ensayos.add(cls.cbr)
        cls.inactiva.ensayos.add(cls.suelto)
        # Sin M2M: lo agrupa la línea de su ficha publicada.
        ServicioPublicado.objects.create(
            servicio=cls.ficha, categoria=cls.categoria, linea=cls.suelos, slug='granulometria-t21',
            titulo_publico='Análisis granulométrico', resumen='Resumen público de granulometría.',
            contenido='c', activo=True,
        )

        cls.inacal = Acreditacion.objects.create(
            organismo='INACAL', numero_acreditacion='LE-230', alcance='Ensayos de suelos y concreto.', orden=0,
        )
        cls.inacal.servicios_acreditados.add(cls.cbr, cls.humedad, cls.ficha, cls.suelto)
        otra = Acreditacion.objects.create(organismo='OTRO', numero_acreditacion='X-1', alcance='Otro alcance.', orden=1)
        otra.servicios_acreditados.add(cls.cbr)
        inactiva = Acreditacion.objects.create(
            organismo='VIEJA', numero_acreditacion='V-0', alcance='Vencida.', activo=False,
        )
        inactiva.servicios_acreditados.add(cls.no_acreditado)

    def setUp(self):
        cache.clear()

    def get(self):
        respuesta = self.client.get(reverse('web_acreditacion:acreditacion'))
        self.assertEqual(respuesta.status_code, 200)
        return respuesta, respuesta.content.decode()

    def test_lista_agrupada_por_linea_y_no_cards(self):
        # REQ-WEB-66 y 67
        respuesta, html = self.get()
        self.assertEqual(html.count('<h1'), 1)
        self.assertIn('id="ensayos-acreditados-titulo" class="h2-section mt-4">Ensayos acreditados</h2>', html)
        claves = [g['clave'] for g in respuesta.context['grupos_ensayos']]
        self.assertLess(claves.index('concreto-t21'), claves.index('suelos-t21'))
        self.assertEqual(claves[-1], 'otros')
        grupos = {g['clave']: [e['nombre'] for e in g['ensayos']] for g in respuesta.context['grupos_ensayos']}
        self.assertEqual(grupos['concreto-t21'], ['Relación de soporte de California'])
        # Orden alfabético sin tildes: "Análisis" va antes que "Contenido".
        self.assertEqual(grupos['suelos-t21'], ['Análisis granulométrico', 'Contenido de humedad'])
        # La línea inactiva no agrupa: su ensayo cae en "Otros".
        self.assertIn('Ensayo sin línea', grupos['otros'])
        self.assertNotIn('inactiva-t21', grupos)
        self.assertEqual(respuesta.context['total_ensayos'], 4)
        self.assertIn('Otros ensayos acreditados', html)
        # Ni la acreditación inactiva ni duplicados del ensayo de dos acreditaciones.
        self.assertNotIn('Ensayo fuera del alcance', html)
        self.assertEqual(html.count('data-ensayo-buscar="Relación de soporte'), 1)
        # Lista, no cards ni modal (v5).
        for viejo in ('data-ensayo-open', 'modal-ensayo', 'ensayos-acreditados-datos', 'data-ensayos-linea', '<h4'):
            self.assertNotIn(viejo, html)

    def test_orden_alfabetico_sin_tildes(self):
        self.assertEqual(
            sorted(['Zeta', 'Ábaco', 'abrasión', 'Éter'], key=_orden_alfabetico),
            ['Ábaco', 'abrasión', 'Éter', 'Zeta'],
        )

    def test_grupos_plegables_abiertos_con_contador_y_columnas(self):
        # REQ-WEB-66
        _, html = self.get()
        self.assertEqual(html.count('<details data-ensayos-grupo='), 3)
        self.assertIn('<details data-ensayos-grupo="suelos-t21" open', html)
        self.assertIn('<summary', html)
        self.assertIn('<h3 id="ensayos-suelos-t21"', html)
        self.assertIn('text-blue-800">2 ensayos</span>', html)
        self.assertIn('text-blue-800">1 ensayo</span>', html)
        self.assertIn('columns-1 gap-x-10', html)
        self.assertIn('md:columns-2 lg:columns-3', html)
        self.assertIn('break-inside-avoid', html)
        self.assertIn('text-emerald-600', html)  # check verde

    def test_ensayo_con_ficha_enlaza_y_sin_ficha_es_texto(self):
        # REQ-WEB-70 y RN-14
        _, html = self.get()
        self.assertIn('<a href="/servicios/granulometria-t21/" class="font-medium', html)
        self.assertIn('>Análisis granulométrico</a>', html)
        self.assertIn('>NTP 339.145</span>', html)
        self.assertNotIn('>Contenido de humedad</a>', html)
        # Ficha cuyo slug lo resuelve antes una línea activa: sin enlace (RN-14).
        ServicioPublicado.objects.filter(servicio=self.ficha).update(slug='suelos-t21')
        _, html = self.get()
        self.assertNotIn('href="/servicios/suelos-t21/" class="font-medium', html)
        self.assertIn('Granulometría por tamizado', html)

    def test_buscador_oculto_sin_js(self):
        # REQ-WEB-68 y 70
        _, html = self.get()
        self.assertIn('<div data-ensayos-controles hidden>', html)
        self.assertIn('<label for="buscar-ensayo"', html)
        self.assertIn('id="buscar-ensayo" type="search" data-ensayos-buscar', html)
        self.assertIn('aria-live="polite"', html)
        self.assertIn('Se muestran los 4 ensayos acreditados.', html)
        self.assertIn('<div data-ensayos-vacio hidden', html)
        self.assertIn('No encontramos ensayos acreditados con ese criterio.', html)
        self.assertIn('Limpiar búsqueda', html)
        self.assertIn('web/js/ensayos-acreditados.js', html)
        # Texto que usa el buscador: nombre, norma, método y línea.
        self.assertIn(
            'data-ensayo-buscar="Relación de soporte de California NTP 339.145 Compactación en molde Concreto T21"', html,
        )

    def test_lista_blanca(self):
        # REQ-WEB-69
        _, html = self.get()
        for prohibido in ('987.65', '987,65', 'ZZT21-', 'precio', 'esta_acreditado', 'codigo_facturacion'):
            self.assertNotIn(prohibido, html)

    def test_sin_ensayos_no_hay_buscador_ni_js(self):
        for acreditacion in Acreditacion.objects.all():
            acreditacion.servicios_acreditados.clear()
        _, html = self.get()
        self.assertIn('Ensayos acreditados', html)  # el alcance sigue
        self.assertIn('Ensayos de suelos y concreto.', html)
        for texto in ('data-ensayos-controles', 'data-ensayos-grupo', 'ensayos-acreditados.js'):
            self.assertNotIn(texto, html)

    def test_consultas_acotadas(self):
        # Sin N+1: la cantidad de consultas no crece con los ensayos.
        antes = self._consultas()
        extra = Servicio.objects.create(codigo_facturacion='ZZT21-006', nombre='Otro más')
        self.inacal.servicios_acreditados.add(extra)
        self.suelos.ensayos.add(extra)
        self.assertEqual(self._consultas(), antes)

    def _consultas(self):
        cache.clear()
        with CaptureQueriesContext(connection) as capturadas:
            self.get()
        return len(capturadas)
