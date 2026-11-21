"""HU-LIMS-11 a 14: datos de la probeta, equipos, sesión, medidas, cálculos y fotos
del ensayo de compresión."""
import shutil
import tempfile
from datetime import date, timedelta
from decimal import Decimal
from io import BytesIO
from pathlib import Path

from django.conf import settings
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import SimpleTestCase, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone
from PIL import Image

from clientes.models import Cliente
from proyectos.calculos_compresion import DatosInsuficientes, calcular, factor_correccion
from proyectos.models import (
    DetalleSolicitudEnsayo,
    ResultadoEnsayo,
    Equipo,
    FotoEnsayo,
    SesionEnsayo,
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


@override_settings(ENSAYOS_FOTOS_DIR=FOTOS_TMP, ROOT_URLCONF='grupovicaf.urls_lab')
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

        self.recepcion = recepcion

        def linea(servicio_cot, norma, tecnico):
            muestra = MuestraDetalle.objects.create(
                recepcion=recepcion, tipo_muestra=tipo, descripcion='Probeta', masa_aprox=Decimal('3.9'),
                fc_diseno=Decimal('420'), fecha_fabricacion=date.today() - timedelta(days=29),
                edad_ensayo_dias=28,
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

    def abrir_sesion(self, fecha=None, **extra):
        datos = {
            'fecha': (fecha or date.today() - timedelta(days=1)).isoformat(),
            'temperatura_inicial': '22.5', 'humedad_inicial': '51',
        }
        for campo, tipo in SesionEnsayo.EQUIPOS + SesionEnsayo.ACCESORIOS:
            datos[campo] = Equipo.objects.filter(tipo=tipo).first().pk
        datos['neopreno_usos'] = '59-60'
        for clave, _, _, esperado in SesionEnsayo.COMPROBACION:
            datos['comp_' + clave] = '1' if esperado else '0'
        datos.update(extra)
        return self.client.post(reverse('proyectos:abrir_sesion_ensayo'), datos)

    def subir_las_cinco(self, detalle):
        for tipo in FotoEnsayo.TIPOS_COMPRESION:
            ancho, alto = FotoEnsayo.PROPORCIONES[tipo]
            self.assertEqual(self.subir(detalle, tipo, jpeg(ancho * 100, alto * 100)).status_code, 200)


class ListaYAccesoTests(CompresionBase):

    def test_tecnico_ve_solo_sus_ensayos_y_sin_cliente(self):
        self.client.force_login(self.user_tec)
        r = self.client.get(reverse('proyectos:mis_ensayos_compresion'))
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, 'Resultados de ensayo')
        self.assertContains(r, self.mia.muestra.codigo_laboratorio)
        self.assertContains(r, self.proctor.muestra.codigo_laboratorio)
        self.assertNotContains(r, self.ajena.muestra.codigo_laboratorio)
        self.assertNotContains(r, 'Constructora Secreta')

    def test_supervisor_ve_todos(self):
        self.client.force_login(self.user_sup)
        r = self.client.get(reverse('proyectos:mis_ensayos_compresion'))
        self.assertContains(r, self.mia.muestra.codigo_laboratorio)
        self.assertContains(r, self.ajena.muestra.codigo_laboratorio)
        self.assertContains(r, self.proctor.muestra.codigo_laboratorio)

    def test_linea_ajena_da_404(self):
        self.client.force_login(self.user_tec)
        self.assertEqual(self.client.get(self.url_registro(self.ajena)).status_code, 404)
        self.assertEqual(self.subir(self.ajena, 'carga', jpeg(180, 70)).status_code, 404)

    def test_cada_linea_usa_su_plantilla(self):
        self.client.force_login(self.user_tec)
        r = self.client.get(self.url_registro(self.mia))
        self.assertContains(r, 'name="tipo_fractura"')
        r = self.client.get(self.url_registro(self.proctor))
        self.assertContains(r, 'data-datos-generales')
        self.assertNotContains(r, 'name="tipo_fractura"')
        # Una foto de compresión no vale para la plantilla general.
        self.assertEqual(self.subir(self.proctor, 'carga', jpeg(180, 70)).status_code, 404)

    def test_las_rutas_viejas_de_compresion_redirigen(self):
        self.client.force_login(self.user_tec)
        r = self.client.get('/proyectos/compresion/')
        self.assertEqual(r.status_code, 301)
        self.assertEqual(r['Location'], reverse('proyectos:mis_ensayos_compresion'))

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

    # Probeta 1 del informe real VCF-INF-2026-4582.
    MEDIDAS_P1 = {
        'masa_g': '3914', 'd1': '102.12', 'd2': '101.82',
        'l1': '205.32', 'l2': '205.26', 'l3': '205.48', 'carga_kn': '497.32', 'tipo_fractura': '3',
        'verif_perpendicularidad': '1', 'verif_planitud': '1',
    }

    def setUp(self):
        super().setUp()
        self.client.force_login(self.user_tec)
        self.abrir_sesion()
        self.client.logout()

    def terminar(self, fecha=None, **medidas):
        fecha = fecha or (date.today() - timedelta(days=1)).isoformat()
        datos = {'accion': 'terminar', 'fecha_ensayo': fecha, 'observaciones': '', **self.MEDIDAS_P1}
        datos.update(medidas)
        return self.client.post(self.url_registro(self.mia), datos)

    def test_no_termina_sin_las_cinco_fotos(self):
        self.client.force_login(self.user_tec)
        self.subir(self.mia, 'carga', jpeg(1800, 700))
        r = self.terminar()
        self.assertRedirects(r, self.url_registro(self.mia), fetch_redirect_response=False)
        ensayo = ResultadoEnsayo.objects.get(detalle=self.mia)
        self.assertEqual(ensayo.estado, ResultadoEnsayo.ESTADO_BORRADOR)
        self.assertEqual(len(ensayo.tipos_faltantes()), 4)

    def test_no_termina_sin_fecha_de_ensayo(self):
        self.client.force_login(self.user_tec)
        self.subir_las_cinco(self.mia)
        self.client.post(self.url_registro(self.mia), {'accion': 'terminar', 'fecha_ensayo': ''})
        self.assertFalse(ResultadoEnsayo.objects.get(detalle=self.mia).terminado)

    def test_rechaza_fecha_futura(self):
        self.client.force_login(self.user_tec)
        self.subir_las_cinco(self.mia)
        self.terminar(fecha=(date.today() + timedelta(days=1)).isoformat())
        self.assertFalse(ResultadoEnsayo.objects.get(detalle=self.mia).terminado)

    def test_con_fecha_y_cinco_fotos_termina_y_registra_al_tecnico(self):
        self.client.force_login(self.user_tec)
        self.subir_las_cinco(self.mia)
        r = self.terminar()
        self.assertRedirects(r, reverse('proyectos:mis_ensayos_compresion'), fetch_redirect_response=False)
        ensayo = ResultadoEnsayo.objects.get(detalle=self.mia)
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
        self.assertFalse(ResultadoEnsayo.objects.get(detalle=self.mia).terminado)

    def test_pantalla_de_registro_muestra_los_cinco_recuadros(self):
        self.client.force_login(self.user_tec)
        r = self.client.get(self.url_registro(self.mia))
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, 'data-slot=', count=5)
        self.assertContains(r, 'aspect-ratio: 18 / 7')
        self.assertNotContains(r, 'Constructora Secreta')


class TerminarConMedidasTests(TerminarTests):

    def test_guarda_los_resultados_del_informe_real_y_la_sesion(self):
        self.client.force_login(self.user_tec)
        self.subir_las_cinco(self.mia)
        self.terminar()
        e = ResultadoEnsayo.objects.get(detalle=self.mia)
        self.assertTrue(e.terminado)
        self.assertEqual(e.diametro_prom, Decimal('102.00'))
        self.assertEqual(e.longitud_prom, Decimal('205.35'))
        self.assertEqual(e.area, Decimal('8171.30'))
        self.assertEqual(e.relacion_ld, Decimal('2.01'))
        self.assertEqual(e.factor, Decimal('1.00'))
        self.assertEqual(e.resistencia_mpa, Decimal('60.9'))
        self.assertEqual(e.resistencia_kgcm2, Decimal('621.0'))
        self.assertEqual(e.porcentaje, 148)
        self.assertEqual(e.densidad, 2330)
        self.assertEqual(e.edad_dias, 28)
        self.assertEqual(e.tipo_fractura, 3)
        self.assertEqual(e.sesion, SesionEnsayo.abierta_de(self.tecnico))

    def test_acepta_coma_decimal(self):
        self.client.force_login(self.user_tec)
        self.subir_las_cinco(self.mia)
        self.terminar(d1='102,12', d2='101,82')
        self.assertEqual(ResultadoEnsayo.objects.get(detalle=self.mia).d1, Decimal('102.12'))

    def test_medida_fuera_de_rango_no_se_guarda(self):
        self.client.force_login(self.user_tec)
        self.subir_las_cinco(self.mia)
        r = self.terminar(d1='1021.2')
        self.assertRedirects(r, self.url_registro(self.mia), fetch_redirect_response=False)
        e = ResultadoEnsayo.objects.get(detalle=self.mia)
        self.assertFalse(e.terminado)
        self.assertIsNone(e.d1)

    def test_no_termina_sin_medidas_ni_fractura(self):
        self.client.force_login(self.user_tec)
        self.subir_las_cinco(self.mia)
        self.terminar(carga_kn='', tipo_fractura='')
        e = ResultadoEnsayo.objects.get(detalle=self.mia)
        self.assertFalse(e.terminado)
        faltan = ' '.join(e.faltantes_para_terminar())
        self.assertIn('Carga máxima', faltan)
        self.assertIn('fractura', faltan)

    def test_no_termina_sin_datos_for004_de_la_probeta(self):
        MuestraDetalle.objects.filter(pk=self.mia.muestra_id).update(fc_diseno=None)
        self.client.force_login(self.user_tec)
        self.subir_las_cinco(self.mia)
        self.terminar()
        self.assertFalse(ResultadoEnsayo.objects.get(detalle=self.mia).terminado)

    def test_no_termina_sin_sesion_abierta(self):
        SesionEnsayo.objects.update(cerrada_en=timezone.now(), temperatura_final=22, humedad_final=50)
        self.client.force_login(self.user_tec)
        self.subir_las_cinco(self.mia)
        self.terminar()
        self.assertFalse(ResultadoEnsayo.objects.get(detalle=self.mia).terminado)

    def test_no_termina_si_la_fecha_no_es_la_de_la_sesion(self):
        self.client.force_login(self.user_tec)
        self.subir_las_cinco(self.mia)
        self.terminar(fecha=(date.today() - timedelta(days=2)).isoformat())
        self.assertFalse(ResultadoEnsayo.objects.get(detalle=self.mia).terminado)

    def test_pantalla_muestra_datos_de_probeta_y_calculo(self):
        self.client.force_login(self.user_tec)
        self.client.post(self.url_registro(self.mia), {'accion': 'guardar', **self.MEDIDAS_P1})
        r = self.client.get(self.url_registro(self.mia))
        self.assertContains(r, 'data-medida=', count=7)
        self.assertContains(r, '621,0')  # es-PE: coma decimal, como el informe
        self.assertContains(r, 'compresion_calculos.js')
        self.assertContains(r, 'centrado_foto.js')
        self.assertNotContains(r, 'Constructora Secreta')


class SesionTests(CompresionBase):

    def test_equipos_del_informe_vienen_cargados(self):
        codigos = set(Equipo.objects.values_list('codigo', flat=True))
        self.assertTrue({'VCF-EQ-PRC-001', 'VCF-EQ-BAL-011', 'VCF-EQ-VER-001',
                         'VCF-EQ-TMG-006', 'VCF-EQ-CUÑ-001', 'VCF-EQ-ESC-001'} <= codigos)

    def test_abrir_y_cerrar_sesion(self):
        self.client.force_login(self.user_tec)
        r = self.abrir_sesion()
        self.assertRedirects(r, reverse('proyectos:mis_ensayos_compresion'), fetch_redirect_response=False)
        sesion = SesionEnsayo.abierta_de(self.tecnico)
        self.assertIsNotNone(sesion)
        self.assertContains(self.client.get(reverse('proyectos:mis_ensayos_compresion')), 'Sesión abierta')

        # Una segunda no se abre.
        self.abrir_sesion()
        self.assertEqual(SesionEnsayo.objects.filter(tecnico=self.tecnico).count(), 1)

        # Cerrar exige T/HR final.
        self.client.post(reverse('proyectos:cerrar_sesion_ensayo'), {'temperatura_final': '', 'humedad_final': ''})
        self.assertIsNotNone(SesionEnsayo.abierta_de(self.tecnico))
        self.client.post(reverse('proyectos:cerrar_sesion_ensayo'), {'temperatura_final': '23', 'humedad_final': '49'})
        self.assertIsNone(SesionEnsayo.abierta_de(self.tecnico))

    def test_equipo_vencido_no_se_puede_elegir(self):
        prensa = Equipo.objects.get(codigo='VCF-EQ-PRC-001')
        prensa.vence_calibracion = date.today() - timedelta(days=1)
        prensa.save()
        self.client.force_login(self.user_tec)
        r = self.client.get(reverse('proyectos:abrir_sesion_ensayo'))
        self.assertNotContains(r, 'VCF-EQ-PRC-001')
        self.assertContains(r, 'No hay equipo vigente de: Prensa')
        r = self.abrir_sesion(prensa=prensa.pk)
        self.assertEqual(r.status_code, 200)
        self.assertIsNone(SesionEnsayo.abierta_de(self.tecnico))

    def test_rechaza_humedad_imposible(self):
        self.client.force_login(self.user_tec)
        self.abrir_sesion(humedad_inicial='150')
        self.assertIsNone(SesionEnsayo.abierta_de(self.tecnico))


class DatosProbetaTests(CompresionBase):

    def setUp(self):
        super().setUp()
        rol = rol_con_permisos('Recepción', 'muestras.ver', 'muestras.editar')
        self.user_rec, _ = crear_trabajador('recepcion', rol)
        self.url = reverse('proyectos:datos_probetas', args=[self.recepcion.pk])

    def test_solo_con_muestras_editar(self):
        self.client.force_login(self.user_tec)
        self.assertEqual(self.client.get(self.url).status_code, 403)

    def test_guarda_datos_for004_y_ubicacion(self):
        self.client.force_login(self.user_rec)
        r = self.client.get(self.url)
        self.assertEqual(r.status_code, 200)
        m = self.mia.muestra
        datos = {'ubicacion_proyecto': 'Jr. Ejemplo 123, Cajamarca'}
        for muestra in MuestraDetalle.objects.filter(recepcion=self.recepcion):
            p = f'm{muestra.pk}-'
            datos.update({
                p + 'codigo_cliente': 'P-01', p + 'elemento_estructural': 'Zapata Z-1',
                p + 'fc_diseno': '280', p + 'fecha_fabricacion': (date.today() - timedelta(days=7)).isoformat(),
                p + 'edad_ensayo_dias': '7', p + 'material': 'Concreto', p + 'tipo_probeta': 'Cilíndrica',
            })
        r = self.client.post(self.url, datos)
        self.assertRedirects(r, self.url, fetch_redirect_response=False)
        m.refresh_from_db()
        self.assertEqual(m.codigo_cliente, 'P-01')
        self.assertEqual(m.fc_diseno, Decimal('280'))
        self.assertEqual(m.fecha_ensayo_solicitada, date.today())
        self.recepcion.refresh_from_db()
        self.assertEqual(self.recepcion.ubicacion_informe, 'Jr. Ejemplo 123, Cajamarca')

    def test_rechaza_fabricacion_futura(self):
        self.client.force_login(self.user_rec)
        m = self.mia.muestra
        r = self.client.post(self.url, {f'm{m.pk}-fecha_fabricacion': (date.today() + timedelta(days=1)).isoformat()})
        self.assertEqual(r.status_code, 200)
        m.refresh_from_db()
        self.assertNotEqual(m.fecha_fabricacion, date.today() + timedelta(days=1))

    def test_avisa_si_un_item_de_compresion_agrupa_varias_probetas(self):
        MuestraDetalle.objects.filter(pk=self.mia.muestra_id).update(cantidad=3)
        self.client.force_login(self.user_rec)
        self.assertContains(self.client.get(self.url), 'cantidad mayor que 1')


class EquiposTests(CompresionBase):

    def test_lista_y_edicion_segun_permiso(self):
        self.client.force_login(self.user_tec)
        self.assertEqual(self.client.get(reverse('proyectos:lista_equipos')).status_code, 403)

        rol = rol_con_permisos('Jefe de laboratorio', 'equipos.ver', 'equipos.editar')
        user, _ = crear_trabajador('jefe', rol)
        self.client.force_login(user)
        r = self.client.get(reverse('proyectos:lista_equipos'))
        self.assertContains(r, 'VCF-EQ-PRC-001')
        prensa = Equipo.objects.get(codigo='VCF-EQ-PRC-001')
        r = self.client.post(reverse('proyectos:editar_equipo', args=[prensa.pk]), {
            'codigo': prensa.codigo, 'nombre': prensa.nombre, 'tipo': prensa.tipo,
            'fecha_calibracion': '2026-01-10', 'vence_calibracion': '2025-01-10', 'activo': 'on',
        })
        self.assertEqual(r.status_code, 200)  # vencimiento antes de la calibración
        r = self.client.post(reverse('proyectos:editar_equipo', args=[prensa.pk]), {
            'codigo': prensa.codigo, 'nombre': prensa.nombre, 'tipo': prensa.tipo,
            'fecha_calibracion': '2025-01-10', 'vence_calibracion': '2026-01-10', 'activo': 'on',
            'certificado': 'LF-123',
        })
        self.assertRedirects(r, reverse('proyectos:lista_equipos'), fetch_redirect_response=False)
        self.assertContains(self.client.get(reverse('proyectos:lista_equipos')), 'Vencido')


class CalculosTests(SimpleTestCase):
    """Las tres probetas del informe real VCF-INF-2026-4582, valor por valor."""

    def test_tres_probetas_del_informe_real(self):
        casos = [
            (('102.12', '101.82', '205.32', '205.26', '205.48', '497.32', 3914),
             ('102.00', '205.35', '8171.30', '2.01', '60.9', '621.0', '148', '2330')),
            (('102.46', '102.38', '204.26', '204.32', '204.74', '457.42', 3897),
             ('102.50', '204.44', '8251.61', '1.99', '55.4', '564.9', '135', '2310')),
            (('102.12', '102.24', '202.76', '202.48', '202.76', '422.94', 3872),
             ('102.25', '202.67', '8211.41', '1.98', '51.5', '525.2', '125', '2330')),
        ]
        for entrada, esperado in casos:
            *medidas, masa = entrada
            r = calcular(*medidas, masa_g=masa, fc_kgcm2=420)
            obtenido = tuple(str(v) for v in (
                r.diametro_prom, r.longitud_prom, r.area, r.relacion_ld,
                r.resistencia_mpa, r.resistencia_kgcm2, r.porcentaje, r.densidad,
            ))
            self.assertEqual(obtenido, esperado)

    def test_factor_de_correccion_astm_c39(self):
        self.assertEqual(factor_correccion(Decimal('1.80')), Decimal('1.00'))
        self.assertEqual(factor_correccion(Decimal('1.75')), Decimal('0.98'))
        self.assertEqual(factor_correccion(Decimal('1.50')), Decimal('0.96'))
        self.assertEqual(factor_correccion(Decimal('1.10')), Decimal('0.89'))
        self.assertEqual(factor_correccion(Decimal('1.00')), Decimal('0.87'))
        with self.assertRaises(DatosInsuficientes):
            factor_correccion(Decimal('0.99'))

    def test_faltan_datos(self):
        with self.assertRaises(DatosInsuficientes):
            calcular('102', None, '200', '200', '200', '400')
