"""HU-LIMS-14: registro del ensayo de compresión y sus cinco fotos obligatorias."""
import shutil
import tempfile
from datetime import date, timedelta
from decimal import Decimal
from io import BytesIO
from pathlib import Path

from django.conf import settings
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone
from PIL import Image

from clientes.models import Cliente
from proyectos.models import (
    DetalleSolicitudEnsayo,
    EnsayoCompresion,
    FotoEnsayo,
    MuestraDetalle,
    RecepcionMuestra,
    SolicitudEnsayo,
    TipoMuestra,
)
from servicios.models import Cotizacion, CotizacionDetalle, CotizacionGrupo, Servicio
from trabajadores.testing import crear_trabajador, rol_con_permisos

FOTOS_TMP = tempfile.mkdtemp(prefix='ensayos_test_')


def jpeg(ancho, alto, orientacion=None):
    buf = BytesIO()
    img = Image.new('RGB', (ancho, alto), (120, 130, 140))
    if orientacion:
        exif = Image.Exif()
        exif[0x0112] = orientacion
        img.save(buf, format='JPEG', exif=exif)
    else:
        img.save(buf, format='JPEG')
    return SimpleUploadedFile('foto.jpg', buf.getvalue(), content_type='image/jpeg')


@override_settings(ENSAYOS_FOTOS_DIR=FOTOS_TMP)
class CompresionBase(TestCase):

    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        shutil.rmtree(FOTOS_TMP, ignore_errors=True)

    def setUp(self):
        rol_tecnico = rol_con_permisos('Técnico de Laboratorio', 'ensayos.ver', 'ensayos.registrar')
        rol_super = rol_con_permisos(
            'Supervisor', 'ensayos.ver', 'ensayos.ver_todos', 'ensayos.registrar',
        )
        rol_comercial = rol_con_permisos('Comercial', 'cotizaciones.ver')
        self.user_tec, self.tecnico = crear_trabajador('tecnico1', rol_tecnico, 'Ana Ruiz')
        self.user_otro, self.otro = crear_trabajador('tecnico2', rol_tecnico, 'Luis Díaz')
        self.user_sup, _ = crear_trabajador('supervisor', rol_super)
        self.user_com, _ = crear_trabajador('comercial', rol_comercial)

        cliente = Cliente.objects.create(
            ruc='20123456789', razon_social='Constructora Secreta SAC',
            persona_contacto='Ana', celular_contacto='987654321', correo_contacto='a@b.pe',
        )
        cot = Cotizacion.objects.create(
            cliente=cliente, numero_oferta='OF-2026-0001', asunto_servicio='Probetas',
            persona_contacto='Ana', correo_contacto='a@b.pe', telefono_contacto='987654321',
            tasa_igv=Decimal('0.18'),
        )
        grupo = CotizacionGrupo.objects.create(cotizacion=cot, nombre_grupo='Concreto')
        srv_c39 = Servicio.objects.create(codigo_facturacion='EC001', nombre='Compresión de probetas')
        srv_proctor = Servicio.objects.create(codigo_facturacion='ES010', nombre='Proctor')
        det_c39 = CotizacionDetalle.objects.create(
            grupo=grupo, servicio=srv_c39, descripcion_especifica='Compresión', precio_unitario=Decimal('25'),
        )
        det_proctor = CotizacionDetalle.objects.create(
            grupo=grupo, servicio=srv_proctor, descripcion_especifica='Proctor', precio_unitario=Decimal('150'),
        )
        tipo = TipoMuestra.objects.create(nombre='Probeta de concreto', sigla='C')
        recepcion = RecepcionMuestra.objects.create(
            cotizacion=cot, procedencia='Cajamarca', responsable_cliente='Ana',
            telefono='987654321', responsable_recepcion=self.user_sup,
            fecha_recepcion=timezone.now() - timedelta(days=30),
        )
        solicitud = SolicitudEnsayo.objects.create(
            codigo_solicitud='SOL-2026-0001', recepcion=recepcion, cotizacion=cot,
            fecha_entrega_programada=date.today(), elaborado_por=self.tecnico,
        )

        def linea(servicio_cot, norma, tecnico):
            muestra = MuestraDetalle.objects.create(
                recepcion=recepcion, tipo_muestra=tipo, descripcion='Probeta', masa_aprox=Decimal('3.9'),
            )
            return DetalleSolicitudEnsayo.objects.create(
                solicitud=solicitud, muestra=muestra, servicio_cotizado=servicio_cot,
                descripcion_ensayo='Ensayo', norma=norma, tecnico_asignado=tecnico,
                fecha_entrega_programada=date.today(),
            )

        self.mia = linea(det_c39, 'ASTM C39/C39M-26', self.tecnico)
        self.ajena = linea(det_c39, 'ASTM C39/C39M-26', self.otro)
        self.proctor = linea(det_proctor, 'ASTM D1557', self.tecnico)

    def url_registro(self, detalle):
        return reverse('proyectos:registrar_compresion', args=[detalle.pk])

    def subir(self, detalle, tipo, archivo):
        return self.client.post(
            reverse('proyectos:subir_foto_compresion', args=[detalle.pk, tipo]), {'foto': archivo},
        )

    def subir_las_cinco(self, detalle):
        for tipo, _ in FotoEnsayo.TIPOS:
            ancho, alto = FotoEnsayo.PROPORCIONES[tipo]
            self.assertEqual(self.subir(detalle, tipo, jpeg(ancho * 100, alto * 100)).status_code, 200)


class ListaYAccesoTests(CompresionBase):

    def test_tecnico_ve_solo_sus_probetas_de_compresion_y_sin_cliente(self):
        self.client.force_login(self.user_tec)
        r = self.client.get(reverse('proyectos:mis_ensayos_compresion'))
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, self.mia.muestra.codigo_laboratorio)
        self.assertNotContains(r, self.ajena.muestra.codigo_laboratorio)
        self.assertNotContains(r, self.proctor.muestra.codigo_laboratorio)
        self.assertNotContains(r, 'Constructora Secreta')

    def test_supervisor_ve_todas_las_de_compresion(self):
        self.client.force_login(self.user_sup)
        r = self.client.get(reverse('proyectos:mis_ensayos_compresion'))
        self.assertContains(r, self.mia.muestra.codigo_laboratorio)
        self.assertContains(r, self.ajena.muestra.codigo_laboratorio)
        self.assertNotContains(r, self.proctor.muestra.codigo_laboratorio)

    def test_probeta_ajena_o_que_no_es_compresion_da_404(self):
        self.client.force_login(self.user_tec)
        self.assertEqual(self.client.get(self.url_registro(self.ajena)).status_code, 404)
        self.assertEqual(self.client.get(self.url_registro(self.proctor)).status_code, 404)
        self.assertEqual(self.subir(self.ajena, 'carga', jpeg(180, 70)).status_code, 404)

    def test_sin_permiso_registrar_da_403(self):
        self.client.force_login(self.user_com)
        self.assertEqual(self.client.get(reverse('proyectos:mis_ensayos_compresion')).status_code, 403)
        self.assertEqual(self.subir(self.mia, 'carga', jpeg(180, 70)).status_code, 403)


class FotoTests(CompresionBase):

    def test_recorta_a_la_proporcion_y_limita_el_tamano(self):
        self.client.force_login(self.user_tec)
        r = self.subir(self.mia, 'antes', jpeg(3000, 3000))
        self.assertEqual(r.status_code, 200)
        foto = FotoEnsayo.objects.get(ensayo__detalle=self.mia, tipo='antes')
        self.assertAlmostEqual(foto.ancho / foto.alto, 4 / 7, delta=0.01)
        self.assertLessEqual(max(foto.ancho, foto.alto), FotoEnsayo.LADO_MAXIMO)

    def test_corrige_la_orientacion_del_celular(self):
        self.client.force_login(self.user_tec)
        # 700x400 con EXIF "girar 90°" = 400x700 real, ya en proporción 4:7.
        self.subir(self.mia, 'despues', jpeg(700, 400, orientacion=6))
        foto = FotoEnsayo.objects.get(ensayo__detalle=self.mia, tipo='despues')
        self.assertEqual((foto.ancho, foto.alto), (400, 700))

    def test_la_foto_se_guarda_fuera_de_media(self):
        self.client.force_login(self.user_tec)
        self.subir(self.mia, 'carga', jpeg(1800, 700))
        foto = FotoEnsayo.objects.get(ensayo__detalle=self.mia, tipo='carga')
        ruta = Path(foto.imagen.path).resolve()
        self.assertTrue(str(ruta).startswith(str(Path(FOTOS_TMP).resolve())))
        self.assertFalse(str(ruta).startswith(str(Path(settings.MEDIA_ROOT).resolve())))

    def test_reemplazar_una_foto_borra_la_anterior(self):
        self.client.force_login(self.user_tec)
        self.subir(self.mia, 'carga', jpeg(1800, 700))
        primera = Path(FotoEnsayo.objects.get(ensayo__detalle=self.mia, tipo='carga').imagen.path)
        self.subir(self.mia, 'carga', jpeg(900, 350))
        self.assertEqual(FotoEnsayo.objects.filter(ensayo__detalle=self.mia, tipo='carga').count(), 1)
        self.assertFalse(primera.exists())

    def test_archivo_que_no_es_imagen_da_400(self):
        self.client.force_login(self.user_tec)
        r = self.subir(self.mia, 'carga', SimpleUploadedFile('x.jpg', b'no soy una foto'))
        self.assertEqual(r.status_code, 400)
        self.assertFalse(FotoEnsayo.objects.exists())

    def test_tipo_desconocido_da_404(self):
        self.client.force_login(self.user_tec)
        self.assertEqual(self.subir(self.mia, 'selfie', jpeg(100, 100)).status_code, 404)

    def test_la_foto_solo_la_ve_quien_puede_ver_la_probeta(self):
        self.client.force_login(self.user_tec)
        self.subir(self.mia, 'carga', jpeg(1800, 700))
        foto = FotoEnsayo.objects.get()
        url = reverse('proyectos:foto_compresion', args=[foto.pk])
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r['Content-Type'], 'image/jpeg')
        self.client.force_login(self.user_otro)
        self.assertEqual(self.client.get(url).status_code, 404)
        self.client.logout()
        self.assertEqual(self.client.get(url).status_code, 302)


class TerminarTests(CompresionBase):

    def terminar(self, fecha=None):
        fecha = fecha or (date.today() - timedelta(days=1)).isoformat()
        return self.client.post(self.url_registro(self.mia), {
            'accion': 'terminar', 'fecha_ensayo': fecha, 'observaciones': '',
        })

    def test_no_termina_sin_las_cinco_fotos(self):
        self.client.force_login(self.user_tec)
        self.subir(self.mia, 'carga', jpeg(1800, 700))
        r = self.terminar()
        self.assertRedirects(r, self.url_registro(self.mia), fetch_redirect_response=False)
        ensayo = EnsayoCompresion.objects.get(detalle=self.mia)
        self.assertEqual(ensayo.estado, EnsayoCompresion.ESTADO_BORRADOR)
        self.assertEqual(len(ensayo.tipos_faltantes()), 4)

    def test_no_termina_sin_fecha_de_ensayo(self):
        self.client.force_login(self.user_tec)
        self.subir_las_cinco(self.mia)
        self.client.post(self.url_registro(self.mia), {'accion': 'terminar', 'fecha_ensayo': ''})
        self.assertFalse(EnsayoCompresion.objects.get(detalle=self.mia).terminado)

    def test_rechaza_fecha_futura(self):
        self.client.force_login(self.user_tec)
        self.subir_las_cinco(self.mia)
        self.terminar(fecha=(date.today() + timedelta(days=1)).isoformat())
        self.assertFalse(EnsayoCompresion.objects.get(detalle=self.mia).terminado)

    def test_con_fecha_y_cinco_fotos_termina_y_registra_al_tecnico(self):
        self.client.force_login(self.user_tec)
        self.subir_las_cinco(self.mia)
        r = self.terminar()
        self.assertRedirects(r, reverse('proyectos:mis_ensayos_compresion'), fetch_redirect_response=False)
        ensayo = EnsayoCompresion.objects.get(detalle=self.mia)
        self.assertTrue(ensayo.terminado)
        self.assertEqual(ensayo.tecnico, self.tecnico)
        self.assertIsNotNone(ensayo.terminado_en)

    def test_terminado_queda_bloqueado_y_solo_el_supervisor_lo_reabre(self):
        self.client.force_login(self.user_tec)
        self.subir_las_cinco(self.mia)
        self.terminar()
        self.assertEqual(self.subir(self.mia, 'carga', jpeg(1800, 700)).status_code, 409)
        r = self.client.post(self.url_registro(self.mia), {'accion': 'reabrir'})
        self.assertEqual(r.status_code, 403)

        self.client.force_login(self.user_sup)
        self.client.post(self.url_registro(self.mia), {'accion': 'reabrir'})
        self.assertFalse(EnsayoCompresion.objects.get(detalle=self.mia).terminado)

    def test_pantalla_de_registro_muestra_los_cinco_recuadros(self):
        self.client.force_login(self.user_tec)
        r = self.client.get(self.url_registro(self.mia))
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, 'data-slot=', count=5)
        self.assertContains(r, 'aspect-ratio: 18 / 7')
        self.assertNotContains(r, 'Constructora Secreta')
