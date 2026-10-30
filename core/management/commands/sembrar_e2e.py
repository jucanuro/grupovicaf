"""Datos fijos para las pruebas E2E de Playwright (carpeta e2e/).

Idempotente: se puede correr las veces que haga falta sobre la misma base y
deja siempre el mismo estado. Todo lo que crea lleva el marcador E2E:

    Usuarios          e2e.coordinador, e2e.tecnico.a, e2e.tecnico.b
    Roles             'E2E Coordinador', 'E2E Técnico'
    Cliente           RUC 20999999991 · 'Constructora E2E SAC'
    Cotización        COT-E2E-0001
    Solicitud         SOL-E2E-0001 (asignada solo a e2e.tecnico.a)
    Informe           slug de validación fijo (SLUG_INFORME)
    Catálogo web      línea 'e2e-mecanica-de-suelos' + ensayo 'e2e-proctor-modificado'

Las pruebas leen los mismos valores desde e2e/datos.js: si cambia uno aquí,
cambia allí.

Uso:
    python manage.py sembrar_e2e
"""
import os
import uuid
from datetime import date
from decimal import Decimal

from django.conf import settings
from django.contrib.auth.models import User
from django.core.files.base import ContentFile
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from clientes.models import Cliente
from proyectos.models import (
    DetalleSolicitudEnsayo,
    InformeFinal,
    MuestraDetalle,
    RecepcionMuestra,
    SolicitudEnsayo,
    TipoMuestra,
)
from servicios.models import CategoriaServicio, Cotizacion, CotizacionDetalle, CotizacionGrupo, Servicio
from trabajadores.models import AccionPermiso, ModuloSistema, PermisoModulo, RolTrabajador, TrabajadorProfile
from web_catalogo.models import LineaServicio, ServicioPublicado

# No es un secreto: solo existe en bases de desarrollo/CI (ver salvaguarda DEBUG).
PASSWORD_POR_DEFECTO = 'vicaf-e2e-2026'
SLUG_INFORME = uuid.UUID('e2e00000-0000-4000-8000-000000000001')

PERMISOS_COORDINADOR = ('cotizaciones.ver', 'ensayos.ver', 'ensayos.ver_todos')
PERMISOS_TECNICO = ('ensayos.ver', 'calendario.ver')


class Command(BaseCommand):
    help = 'Crea o deja al día los datos fijos de las pruebas E2E (solo DEBUG=True).'

    def handle(self, *args, **options):
        # En prod DEBUG=False: estos usuarios con contraseña conocida nunca
        # deben existir allí.
        if not settings.DEBUG:
            raise CommandError('sembrar_e2e es solo para desarrollo y CI (DEBUG=True).')

        password = os.environ.get('E2E_PASSWORD') or PASSWORD_POR_DEFECTO
        with transaction.atomic():
            coordinador, tecnico_a = self._trabajadores(password)
            self._catalogo_web()
            self._solicitud_con_informe(coordinador, tecnico_a)

        self.stdout.write(self.style.SUCCESS('Datos E2E listos.'))

    # ------------------------------------------------------------------

    def _rol(self, nombre, codigos):
        rol, _ = RolTrabajador.objects.get_or_create(nombre=nombre)
        permisos = []
        for codigo in codigos:
            modulo_codigo, accion_codigo = codigo.split('.')
            modulo, _ = ModuloSistema.objects.get_or_create(
                codigo=modulo_codigo, defaults={'nombre': modulo_codigo.title()},
            )
            accion, _ = AccionPermiso.objects.get_or_create(
                codigo=accion_codigo, defaults={'nombre': accion_codigo.title()},
            )
            permiso, _ = PermisoModulo.objects.get_or_create(modulo_sistema=modulo, accion=accion)
            permisos.append(permiso)
        rol.permisos.set(permisos)
        return rol

    def _trabajador(self, username, rol, nombre_completo, password, titulo=''):
        user, _ = User.objects.get_or_create(username=username)
        user.is_active = True
        user.set_password(password)
        user.save()
        perfil, _ = TrabajadorProfile.objects.update_or_create(
            user=user,
            defaults={'rol': rol, 'nombre_completo': nombre_completo, 'titulo_profesional': titulo or None},
        )
        return perfil

    def _trabajadores(self, password):
        rol_coordinador = self._rol('E2E Coordinador', PERMISOS_COORDINADOR)
        rol_tecnico = self._rol('E2E Técnico', PERMISOS_TECNICO)
        coordinador = self._trabajador('e2e.coordinador', rol_coordinador, 'Coordinadora E2E', password, 'Ing')
        tecnico_a = self._trabajador('e2e.tecnico.a', rol_tecnico, 'Técnico E2E A', password)
        self._trabajador('e2e.tecnico.b', rol_tecnico, 'Técnico E2E B', password)
        return coordinador, tecnico_a

    def _catalogo_web(self):
        categoria, _ = CategoriaServicio.objects.get_or_create(nombre='E2E Mecánica de Suelos')
        servicio, _ = Servicio.objects.update_or_create(
            codigo_facturacion='E2E-001',
            defaults={'nombre': 'Ensayo de Compactación Proctor Modificado (E2E)', 'precio_base': Decimal('150.00')},
        )
        linea, _ = LineaServicio.objects.update_or_create(
            slug='e2e-mecanica-de-suelos',
            defaults={
                'nombre': 'Mecánica de Suelos E2E',
                'titulo_h1': 'Mecánica de Suelos E2E',
                'resumen': 'Línea de prueba para las pruebas E2E.',
                'contenido': 'Contenido de prueba.',
                'meta_title': 'Mecánica de Suelos E2E',
                'meta_description': 'Línea de prueba para las pruebas E2E.',
                'noindex': True,
                'activo': True,
                'orden': 0,
            },
        )
        ServicioPublicado.objects.update_or_create(
            slug='e2e-proctor-modificado',
            defaults={
                'servicio': servicio,
                'categoria': categoria,
                'linea': linea,
                'titulo_publico': 'Proctor Modificado E2E',
                'resumen': 'Ensayo de prueba para las pruebas E2E.',
                'contenido': 'Contenido de prueba.',
                'meta_title': 'Proctor Modificado E2E',
                'meta_description': 'Ensayo de prueba para las pruebas E2E.',
                'noindex': True,
                'activo': True,
            },
        )

    def _solicitud_con_informe(self, coordinador, tecnico_a):
        cliente, _ = Cliente.objects.update_or_create(
            ruc='20999999991',
            defaults={
                'razon_social': 'Constructora E2E SAC',
                'persona_contacto': 'Ana E2E',
                'celular_contacto': '999999991',
                'correo_contacto': 'ana@e2e.invalid',
            },
        )
        cotizacion, _ = Cotizacion.objects.get_or_create(
            numero_oferta='COT-E2E-0001',
            defaults={
                'cliente': cliente,
                'asunto_servicio': 'Ensayos de suelos E2E',
                'persona_contacto': 'Ana E2E',
                'correo_contacto': 'ana@e2e.invalid',
                'telefono_contacto': '999999991',
                'tasa_igv': Decimal('0.18'),
            },
        )
        grupo, _ = CotizacionGrupo.objects.get_or_create(cotizacion=cotizacion, nombre_grupo='Suelos')
        detalle_cot, _ = CotizacionDetalle.objects.get_or_create(
            grupo=grupo,
            servicio=Servicio.objects.get(codigo_facturacion='E2E-001'),
            defaults={'descripcion_especifica': 'Proctor Modificado', 'precio_unitario': Decimal('150.00')},
        )

        tipo_muestra, _ = TipoMuestra.objects.get_or_create(nombre='Suelo E2E', defaults={'sigla': 'SE2E'})
        recepcion, _ = RecepcionMuestra.objects.get_or_create(
            cotizacion=cotizacion,
            defaults={
                'procedencia': 'Cajamarca',
                'responsable_cliente': 'Ana E2E',
                'telefono': '999999991',
                'responsable_recepcion': coordinador.user,
            },
        )
        muestra, _ = MuestraDetalle.objects.get_or_create(
            recepcion=recepcion,
            descripcion='Muestra E2E Km 1',
            defaults={'tipo_muestra': tipo_muestra, 'masa_aprox': Decimal('5.00')},
        )

        solicitud, _ = SolicitudEnsayo.objects.get_or_create(
            codigo_solicitud='SOL-E2E-0001',
            defaults={
                'recepcion': recepcion,
                'cotizacion': cotizacion,
                'fecha_entrega_programada': date(2026, 12, 1),
                'elaborado_por': coordinador,
            },
        )
        DetalleSolicitudEnsayo.objects.update_or_create(
            solicitud=solicitud,
            muestra=muestra,
            defaults={
                'servicio_cotizado': detalle_cot,
                'descripcion_ensayo': 'Proctor Modificado',
                'norma': 'ASTM D1557',
                'tecnico_asignado': tecnico_a,
                'fecha_entrega_programada': date(2026, 12, 1),
            },
        )

        if not InformeFinal.objects.filter(solicitud=solicitud).exists():
            InformeFinal.objects.create(
                solicitud=solicitud,
                slug_validacion=SLUG_INFORME,
                archivo_pdf=ContentFile(b'%PDF-1.4 informe E2E', name='informe-e2e.pdf'),
                responsable_firma=coordinador,
            )
