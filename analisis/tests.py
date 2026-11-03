"""Pruebas de Análisis (VCF-LIMS, HU-LIMS-06 a 10)."""
import json
from datetime import date
from decimal import Decimal
from unittest import mock

from django.core.files.base import ContentFile
from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext
from django.urls import reverse

from clientes.models import Cliente
from servicios.models import Cotizacion, CotizacionDetalle, CotizacionGrupo, Servicio, Voucher
from trabajadores.models import PermisoModulo
from trabajadores.testing import crear_trabajador, rol_con_permisos

from . import conjuntos as modulo_conjuntos
from .conjuntos import CONJUNTOS
from .models import VistaAnalisis

FEB = (date(2001, 2, 1), date(2001, 2, 28))

# Lo que nunca puede llegar al navegador (reglas 2 y 3 del CLAUDE.md).
PROHIBIDOS = ('ruc', 'codigo_confidencial', 'firma', 'logo', 'voucher_codigo', 'imagen', 'correo',
              'celular', 'telefono', 'direccion', 'persona_contacto', 'slug')


def _cotizacion(numero, cliente, estado, cantidad, precio, pagado=None, plantilla=False, fecha=date(2001, 2, 10)):
    servicio, _ = Servicio.objects.get_or_create(
        codigo_facturacion='T-001', defaults={'nombre': 'Proctor de prueba', 'precio_base': Decimal('10')},
    )
    cot = Cotizacion.objects.create(
        numero_oferta=None if plantilla else numero, cliente=cliente, estado=estado, fecha_generacion=fecha,
        asunto_servicio='Prueba', persona_contacto='X', correo_contacto='x@x.invalid',
        telefono_contacto='1', tasa_igv=Decimal('0.18'), es_plantilla=plantilla,
    )
    grupo = CotizacionGrupo.objects.create(cotizacion=cot, nombre_grupo='Suelos')
    CotizacionDetalle.objects.create(
        grupo=grupo, servicio=servicio, cantidad=cantidad, precio_unitario=precio, descripcion_especifica='x',
    )
    if pagado is not None:
        Voucher.objects.create(cotizacion=cot, codigo=f'SECRETO-{numero}', monto_pagado=pagado,
                               imagen=ContentFile(b'%PDF', name='v.pdf'))
    return cot


class BaseAnalisis(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.cliente = Cliente.objects.create(ruc='20111111111', razon_social='Constructora Uno SAC')
        cls.otro = Cliente.objects.create(ruc='20222222222', razon_social='Minera Dos SAC')
        _cotizacion('C-1', cls.cliente, 'Aceptada', 2, Decimal('500'), pagado=Decimal('590'))
        _cotizacion('C-2', cls.cliente, 'Aceptada', 1, Decimal('500'), pagado=Decimal('590'))
        _cotizacion('C-3', cls.otro, 'Pendiente', 1, Decimal('200'))
        _cotizacion('PL', cls.cliente, 'Pendiente', 10, Decimal('999'), plantilla=True)
        _cotizacion('C-OLD', cls.cliente, 'Rechazada', 1, Decimal('100'), fecha=date(2000, 5, 1))

        rol_total = rol_con_permisos('Gerencia', 'reportes.ver', 'cotizaciones.ver', 'clientes.ver')
        cls.gerente, _ = crear_trabajador('gerente', rol_total)
        rol_analista = rol_con_permisos('Analista', 'reportes.ver', 'clientes.ver')
        cls.analista, _ = crear_trabajador('analista', rol_analista)
        rol_comercial = rol_con_permisos('Comercial', 'cotizaciones.ver', 'clientes.ver')
        cls.comercial, _ = crear_trabajador('comercial', rol_comercial)

    def datos(self, user, clave, desde='', hasta='', estado=200):
        self.client.force_login(user)
        resp = self.client.get(reverse('analisis:datos', args=[clave]), {'desde': desde, 'hasta': hasta})
        self.assertEqual(resp.status_code, estado, resp.content)
        return resp.json()

    def filas_como_dict(self, datos):
        return [dict(zip(datos['encabezado'], f)) for f in datos['filas']]


class CotizacionesTests(BaseAnalisis):
    def test_montos_cobrado_y_saldo_referencial(self):
        filas = {f['N.º oferta']: f for f in self.filas_como_dict(
            self.datos(self.gerente, 'cotizaciones', '2001-02-01', '2001-02-28'))}
        self.assertEqual(set(filas), {'C-1', 'C-2', 'C-3'})
        self.assertEqual(filas['C-1']['Total (con IGV)'], 1180.0)
        self.assertEqual(filas['C-1']['Cobrado (voucher)'], 590.0)
        self.assertEqual(filas['C-1']['Saldo referencial'], 590.0)
        self.assertEqual(filas['C-2']['Saldo referencial'], 0.0)
        # RN-R02: una pendiente no es deuda.
        self.assertEqual(filas['C-3']['Saldo referencial'], 0.0)
        self.assertEqual(filas['C-3']['Con voucher'], 'No')
        self.assertEqual(filas['C-1']['Mes'], '2001-02')

    def test_excluye_plantillas_y_respeta_el_rango(self):  # CA-06.7, RN-R01
        numeros = [f['N.º oferta'] for f in self.filas_como_dict(self.datos(self.gerente, 'cotizaciones'))]
        self.assertIn('C-OLD', numeros)
        self.assertNotIn('S/N', numeros)
        self.assertEqual(len(numeros), 4)
        solo_feb = self.datos(self.gerente, 'cotizaciones', *[d.isoformat() for d in FEB])
        self.assertEqual(len(solo_feb['filas']), 3)

    def test_items_sin_igv(self):
        filas = self.filas_como_dict(self.datos(self.gerente, 'items', '2001-02-01', '2001-02-28'))
        self.assertEqual(len(filas), 3)
        c1 = next(f for f in filas if f['N.º oferta'] == 'C-1')
        self.assertEqual(c1['Total ítem (sin IGV)'], 1000.0)
        self.assertEqual(c1['Cantidad'], 2)
        self.assertEqual(c1['Ensayo'], 'Proctor de prueba')

    def test_rango_invertido_y_fecha_invalida(self):  # CA-06.6
        self.assertIn('posterior', self.datos(self.gerente, 'cotizaciones', '2001-03-01', '2001-02-01', 400)['error'])
        self.datos(self.gerente, 'cotizaciones', '01/02/2001', '', 400)

    def test_tope_de_filas(self):  # CA-10.4
        with mock.patch.object(modulo_conjuntos, 'LIMITE_FILAS', 2):
            error = self.datos(self.gerente, 'cotizaciones', estado=400)['error']
        self.assertIn('Acota', error)

    def test_consultas_fijas(self):  # CA-10.3: sin una consulta por fila
        self.client.force_login(self.gerente)
        url = reverse('analisis:datos', args=['cotizaciones'])
        with CaptureQueriesContext(connection) as pocas:
            self.client.get(url)
        for i in range(10):
            _cotizacion(f'X-{i}', self.otro, 'Aceptada', 1, Decimal('10'), pagado=Decimal('5'))
        with CaptureQueriesContext(connection) as muchas:
            self.client.get(url)
        self.assertEqual(len(pocas), len(muchas))


class ListaBlancaTests(BaseAnalisis):
    def test_solo_campos_de_la_lista_blanca(self):  # CA-10.2
        for clave, conjunto in CONJUNTOS.items():
            with self.subTest(conjunto=clave):
                datos = self.datos(self.gerente, clave)
                esperado = [c.etiqueta for c in conjunto.campos]
                self.assertEqual(datos['encabezado'], esperado)
                self.assertEqual(set(datos), {'encabezado', 'numericos', 'filas', 'conjunto'})
                for fila in datos['filas']:
                    self.assertEqual(len(fila), len(esperado))
                texto = json.dumps(datos).lower()
                self.assertNotIn('20111111111', texto)  # RUC
                self.assertNotIn('secreto-', texto)     # código del voucher
                for etiqueta in esperado:
                    for prohibido in PROHIBIDOS:
                        self.assertNotIn(prohibido, etiqueta.lower())

    def test_montos_de_clientes_exigen_cotizaciones_ver(self):  # DP-LIMS-12 B
        sin_montos = self.datos(self.analista, 'clientes')['encabezado']
        self.assertNotIn('Monto cotizado (con IGV)', sin_montos)
        self.assertIn('N.º cotizaciones', sin_montos)
        con_montos = self.filas_como_dict(self.datos(self.gerente, 'clientes'))
        uno = next(f for f in con_montos if f['Razón social'] == 'Constructora Uno SAC')
        # Históricos y sin plantillas: C-1 + C-2 + C-OLD.
        self.assertEqual(uno['N.º cotizaciones'], 3)
        self.assertEqual(uno['N.º aceptadas'], 2)
        self.assertEqual(uno['Monto aceptado (con IGV)'], 1770.0)


class PermisosTests(BaseAnalisis):
    def test_sin_reportes_ver_no_entra(self):  # CA-10.1
        self.client.force_login(self.comercial)
        self.assertEqual(self.client.get(reverse('analisis:analisis')).status_code, 403)
        self.assertEqual(self.client.get(reverse('analisis:datos', args=['cotizaciones'])).status_code, 403)
        menu = self.client.get(reverse('dashboard')).content.decode()
        self.assertNotIn(reverse('analisis:analisis'), menu)

    def test_conjunto_sin_permiso_del_modulo(self):  # CA-10.1b
        self.datos(self.analista, 'cotizaciones', estado=403)
        self.datos(self.analista, 'items', estado=403)
        self.client.force_login(self.analista)
        pagina = self.client.get(reverse('analisis:analisis'))
        self.assertEqual(pagina.status_code, 200)
        claves = [c['clave'] for c in pagina.context['config']['conjuntos']]
        self.assertEqual(claves, ['clientes'])
        # Las vistas rápidas que usan montos no se ofrecen sin cotizaciones.ver.
        vistas = [v['nombre'] for v in pagina.context['config']['conjuntos'][0]['vistas']]
        self.assertNotIn('Cotizado por cliente', vistas)

    def test_menu_muestra_analisis_con_permiso(self):
        self.client.force_login(self.gerente)
        self.assertIn(reverse('analisis:analisis'), self.client.get(reverse('dashboard')).content.decode())

    def test_conjunto_inexistente(self):
        self.client.force_login(self.gerente)
        self.assertEqual(self.client.get(reverse('analisis:datos', args=['no-existe'])).status_code, 404)

    def test_migracion_crea_el_permiso(self):
        self.assertTrue(PermisoModulo.objects.filter(codigo='reportes.ver').exists())


class VistasGuardadasTests(BaseAnalisis):
    def guardar(self, user, cuerpo, estado=201):
        self.client.force_login(user)
        resp = self.client.post(reverse('analisis:vistas'), json.dumps(cuerpo), content_type='application/json')
        self.assertEqual(resp.status_code, estado, resp.content)
        return resp.json()

    def test_guarda_solo_la_disposicion(self):  # CA-08.2
        config = {'rows': ['Cliente'], 'cols': [], 'vals': ['Total (con IGV)'], 'aggregatorName': 'Suma',
                  'rendererName': 'Tabla', 'exclusions': {'Estado': ['Pendiente']},
                  'filas': [['dato', 1]], 'localeStrings': {'x': 'y'}}
        vista = self.guardar(self.gerente, {'nombre': 'Por cliente', 'conjunto': 'cotizaciones',
                                            'configuracion': config})['vista']
        guardada = VistaAnalisis.objects.get(pk=vista['id']).configuracion
        self.assertNotIn('filas', guardada)
        self.assertNotIn('localeStrings', guardada)
        self.assertEqual(guardada['rows'], ['Cliente'])
        # Mismo nombre reemplaza en lugar de duplicar.
        self.guardar(self.gerente, {'nombre': 'Por cliente', 'conjunto': 'cotizaciones',
                                    'configuracion': {'rows': ['Estado']}})
        self.assertEqual(VistaAnalisis.objects.filter(usuario=self.gerente).count(), 1)

    def test_cada_usuario_ve_y_borra_solo_las_suyas(self):
        vista = self.guardar(self.gerente, {'nombre': 'Mía', 'conjunto': 'clientes', 'configuracion': {}})['vista']
        self.client.force_login(self.analista)
        self.assertEqual(self.client.get(reverse('analisis:vistas')).json()['vistas'], [])
        borrar = reverse('analisis:eliminar_vista', args=[vista['id']])
        self.assertEqual(self.client.post(borrar).status_code, 404)
        self.client.force_login(self.gerente)
        self.assertEqual(self.client.post(borrar).status_code, 200)
        self.assertFalse(VistaAnalisis.objects.exists())

    def test_valida_entrada(self):
        self.guardar(self.gerente, {'nombre': '', 'conjunto': 'clientes', 'configuracion': {}}, 400)
        self.guardar(self.gerente, {'nombre': 'x', 'conjunto': 'clientes', 'configuracion': {'rows': 'Cliente'}}, 400)
        self.guardar(self.analista, {'nombre': 'x', 'conjunto': 'cotizaciones', 'configuracion': {}}, 403)
