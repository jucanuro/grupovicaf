"""Datos de EJEMPLO del módulo de correo (solo DEBUG=True).

Crea tres cuentas (informes@, laboratorio@, quejas.reportes@), sus carpetas,
hilos con respuestas, adjuntos, una imagen incrustada (cid:), un boletín con
imágenes remotas y un <script> (para ver el sanitizado), spam, un borrador,
un envío fallido en la Bandeja de salida, firmas, asignaciones y bitácora.

Da acceso a los usuarios indicados con --usuario (o, si no se indica, a los
que tienen el permiso correo.ver y a los superusuarios).

Es idempotente: borra las cuentas de ejemplo y las vuelve a crear.

    python manage.py seed_correo_demo
    python manage.py seed_correo_demo --usuario e2e.coordinador --usuario admin
"""
import io
from datetime import timedelta

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from correo.mensajeria import (
    asegurar_carpetas, carpeta, contacto_para, crear_mensaje, nuevo_message_id, registrar_evento,
)
from correo.models import AccesoCuenta, Asignacion, Carpeta, Contacto, CuentaCorreo, EventoMensaje, Firma, Mensaje

CUENTAS = [
    ('informes', 'informes@grupovicaf.com', 'Informes y cotizaciones'),
    ('laboratorio', 'laboratorio@grupovicaf.com', 'Laboratorio'),
    ('quejas', 'quejas.reportes@grupovicaf.com', 'Quejas y reportes'),
]
CLIENTE = ('ana@e2e.invalid', 'Ana Quispe', 'Constructora E2E SAC')


def _pdf(titulo, lineas):
    from reportlab.lib.pagesizes import A4
    from reportlab.pdfgen import canvas
    buffer = io.BytesIO()
    hoja = canvas.Canvas(buffer, pagesize=A4)
    hoja.setFont('Helvetica-Bold', 14)
    hoja.drawString(72, 780, titulo)
    hoja.setFont('Helvetica', 11)
    for i, linea in enumerate(lineas):
        hoja.drawString(72, 750 - 18 * i, linea)
    hoja.showPage()
    hoja.save()
    return buffer.getvalue()


def _logo():
    with open(settings.BASE_DIR / 'static' / 'img' / 'LogoF.png', 'rb') as archivo:
        return archivo.read()


def _p(*parrafos):
    return ''.join(f'<p>{p}</p>' for p in parrafos)


class Command(BaseCommand):
    help = 'Crea cuentas y correos de EJEMPLO para el módulo de correo (solo DEBUG=True).'

    def add_arguments(self, parser):
        parser.add_argument('--usuario', action='append', default=[], help='username con acceso (repetible)')

    def handle(self, *args, **opciones):
        if not settings.DEBUG:
            raise CommandError('seed_correo_demo es solo para desarrollo y CI (DEBUG=True).')
        User = get_user_model()
        if opciones['usuario']:
            usuarios = list(User.objects.filter(username__in=opciones['usuario']))
            faltan = set(opciones['usuario']) - {u.username for u in usuarios}
            if faltan:
                raise CommandError(f'No existen: {", ".join(sorted(faltan))}')
        else:
            usuarios = list(User.objects.filter(
                Q(is_superuser=True) | Q(trabajadorprofile__rol__permisos__codigo='correo.ver'),
                is_active=True,
            ).distinct())
        if not usuarios:
            raise CommandError('Ningún usuario recibe acceso: use --usuario o asigne correo.ver a un rol.')

        with transaction.atomic():
            self._limpiar()
            cuentas = self._cuentas(usuarios)
            self._correos(cuentas, usuarios[0])
            self._firmas(cuentas, usuarios)
        nombres = ', '.join(u.username for u in usuarios)
        self.stdout.write(self.style.SUCCESS(f'Correo de ejemplo listo. Acceso para: {nombres}'))

    # ------------------------------------------------------------------

    def _limpiar(self):
        slugs = [c[0] for c in CUENTAS]
        Mensaje.objects.filter(cuenta__slug__in=slugs).delete()
        CuentaCorreo.objects.filter(slug__in=slugs).delete()

    def _cuentas(self, usuarios):
        cuentas = {}
        for slug, direccion, nombre in CUENTAS:
            cuenta = CuentaCorreo.objects.create(slug=slug, direccion=direccion, nombre=nombre)
            asegurar_carpetas(cuenta)
            cuentas[slug] = cuenta
            for i, usuario in enumerate(usuarios):
                # El primero gestiona todo; quejas@ queda en solo lectura para el resto.
                rol = AccesoCuenta.GESTIONA if (i == 0 or slug != 'quejas') else AccesoCuenta.LECTURA
                if usuario.is_superuser:
                    rol = AccesoCuenta.ADMINISTRA
                AccesoCuenta.objects.create(usuario=usuario, cuenta=cuenta, rol=rol)
        Carpeta.objects.create(cuenta=cuentas['informes'], tipo=Carpeta.PERSONAL, nombre='Proveedores', orden=200)
        return cuentas

    def _correos(self, cuentas, yo):
        ahora = timezone.now()
        hace = lambda **kw: ahora - timedelta(**kw)  # noqa: E731
        informes, lab, quejas = cuentas['informes'], cuentas['laboratorio'], cuentas['quejas']
        cli_correo, cli_nombre, _ = CLIENTE
        cliente = {'nombre': cli_nombre, 'correo': cli_correo}
        yo_nombre = getattr(getattr(yo, 'trabajadorprofile', None), 'nombre_completo', '') or yo.username
        contacto_para(cli_correo, cli_nombre)
        Contacto.objects.filter(correo=cli_correo, empresa='').update(empresa=CLIENTE[2])

        # 1) Cotización de compresión: pregunta, respuesta nuestra y nueva consulta (no leída)
        m1 = crear_mensaje(
            informes, 'entrada', de=cli_correo, de_nombre=cli_nombre,
            para=[{'nombre': 'Informes VICAF', 'correo': informes.direccion}],
            asunto='Solicitud de cotización: ensayo de compresión de probetas',
            html=_p('Buenos días,', 'Necesitamos cotizar el ensayo de <b>resistencia a la compresión</b> de '
                    '24 probetas de concreto (f\'c 210) para la obra del colegio en Baños del Inca.',
                    'Adjunto el plano de ubicación y el cronograma de vaciados.', 'Saludos,<br>Ana Quispe<br>Constructora E2E SAC'),
            fecha=hace(days=2, hours=3), leido=True,
            adjuntos=[('plano-ubicacion.pdf', 'application/pdf',
                       _pdf('Plano de ubicación', ['Obra: Colegio Baños del Inca', 'Probetas: 24']), '', False),
                      ('cronograma-vaciados.pdf', 'application/pdf',
                       _pdf('Cronograma de vaciados', ['Semana 1: zapatas', 'Semana 2: columnas']), '', False)],
        )
        registrar_evento(m1.hilo, EventoMensaje.ABRIO, yo, m1)
        m2 = crear_mensaje(
            informes, 'enviados', de=informes.direccion, de_nombre='Informes VICAF', para=[cliente],
            asunto='RE: Solicitud de cotización: ensayo de compresión de probetas',
            html=_p('Estimada Ana:', 'Gracias por escribirnos. El ensayo según NTP 339.034 tiene un costo de '
                    'S/ 25.00 por probeta. Le enviamos la oferta formal en el transcurso del día.',
                    'Atentamente,<br>' + yo_nombre),
            fecha=hace(days=2), leido=True, in_reply_to=m1.message_id, references=m1.message_id,
            estado=Mensaje.ENVIADO, creado_por=yo, hilo=m1.hilo,
        )
        registrar_evento(m1.hilo, EventoMensaje.RESPONDIO, yo, m2)
        m3 = crear_mensaje(
            informes, 'entrada', de=cli_correo, de_nombre=cli_nombre,
            para=[{'nombre': 'Informes VICAF', 'correo': informes.direccion}],
            cc=[{'nombre': 'Residente de obra', 'correo': 'residente@e2e.invalid'}],
            asunto='RE: Solicitud de cotización: ensayo de compresión de probetas',
            html=_p('Gracias. ¿Podrían incluir también el recojo de probetas en obra? Son 3 viajes.',
                    'Quedo atenta.'),
            fecha=hace(hours=5), in_reply_to=m2.message_id, references=f'{m1.message_id} {m2.message_id}',
        )
        Asignacion.objects.create(hilo=m1.hilo, asignado_a=yo, asignado_por=yo)
        registrar_evento(m1.hilo, EventoMensaje.ASIGNO, yo, m3, a=yo.username)

        # 2) Recepción de muestras, con foto incrustada (cid)
        cid = 'foto-muestras@vicaf'
        m4 = crear_mensaje(
            informes, 'entrada', de='jperez@consorciovial.example', de_nombre='Ing. Jorge Pérez',
            para=[{'nombre': '', 'correo': informes.direccion}],
            asunto='Recepción de muestras de suelo – Vía de Evitamiento',
            html=_p('Buenas tardes, mañana a las 9:00 llevamos 6 sacos de muestra para Proctor y CBR.',
                    'Le comparto una foto de cómo vienen rotuladas:')
            + f'<p><img src="cid:{cid}" alt="Rotulado de muestras" width="240"></p>'
            + _p('Saludos.'),
            fecha=hace(days=1, hours=2), leido=True,
            adjuntos=[('rotulado.png', 'image/png', _logo(), cid, True)],
        )
        registrar_evento(m4.hilo, EventoMensaje.ABRIO, yo, m4)

        # 3) Pago con detracción (no leído, con PDF)
        crear_mensaje(
            informes, 'entrada', de='pagos@mineranorte.example', de_nombre='Tesorería Minera Norte',
            para=[{'nombre': '', 'correo': informes.direccion}],
            asunto='Comprobante de pago y detracción – COT-2026-0412',
            texto='Adjuntamos la constancia de depósito y la detracción del 12%.\n\nTesorería',
            fecha=hace(hours=1),
            adjuntos=[('constancia-deposito.pdf', 'application/pdf',
                       _pdf('Constancia de depósito', ['Monto: S/ 1 180.00', 'Detracción: S/ 141.60']), '', False)],
        )

        # 4) Boletín con imágenes remotas y un script (se sanitiza)
        crear_mensaje(
            informes, 'entrada', de='boletin@normas-tecnicas.example', de_nombre='Boletín de Normas',
            para=[{'nombre': '', 'correo': informes.direccion}],
            asunto='Boletín técnico: actualizaciones NTP para concreto',
            html='<h2 style="color:#1D4ED8">Novedades NTP</h2>'
                 '<p><img src="https://normas-tecnicas.example/pixel.gif" width="1" height="1">'
                 '<img src="https://normas-tecnicas.example/banner.png" alt="Banner" width="480"></p>'
                 '<p onclick="alert(1)">Se actualizó la NTP 339.034 sobre compresión de probetas.</p>'
                 '<script>alert("no debe ejecutarse")</script>'
                 '<p><a href="javascript:alert(2)">Enlace peligroso</a> · '
                 '<a href="https://normas-tecnicas.example/ntp">Ver norma</a></p>',
            fecha=hace(days=3), leido=True,
        )

        # 5) Spam
        crear_mensaje(
            informes, 'spam', de='promo@premios.example', de_nombre='Premios',
            para=[{'nombre': '', 'correo': informes.direccion}],
            asunto='¡Ganaste un premio! Reclámalo hoy', texto='Haz clic aquí para reclamar tu premio.',
            fecha=hace(days=4),
        )

        # 6) Archivado antiguo y carpeta personal
        crear_mensaje(
            informes, 'archivados', de=cli_correo, de_nombre=cli_nombre,
            para=[{'nombre': '', 'correo': informes.direccion}],
            asunto='Informe de ensayo de granulometría recibido', texto='Recibimos el informe, gracias.',
            fecha=hace(days=40), leido=True,
        )
        proveedores = Carpeta.objects.get(cuenta=informes, nombre='Proveedores')
        crear_mensaje(
            informes, 'personal', carpeta_obj=proveedores, de='ventas@equiposlab.example',
            de_nombre='Equipos Lab', para=[{'nombre': '', 'correo': informes.direccion}],
            asunto='Cotización de moldes para probetas', texto='Le enviamos la lista de precios 2026.',
            fecha=hace(days=6), leido=True,
        )

        # 7) Borrador y un envío fallido en la Bandeja de salida
        crear_mensaje(
            informes, 'borradores', de=informes.direccion, de_nombre='Informes VICAF', para=[cliente],
            asunto='Oferta de ensayos de compresión', html=_p('Estimada Ana: adjuntamos la oferta…'),
            fecha=hace(minutes=30), leido=True, estado=Mensaje.BORRADOR, creado_por=yo,
        )
        fallido = crear_mensaje(
            informes, 'salida', de=informes.direccion, de_nombre='Informes VICAF',
            para=[{'nombre': 'Obra norte', 'correo': 'residente@falla.invalid'}],
            asunto='Programación de recojo de probetas', html=_p('Confirmamos el recojo para el jueves.'),
            fecha=hace(minutes=50), leido=True, estado=Mensaje.FALLIDO, creado_por=yo,
        )
        Mensaje.objects.filter(pk=fallido.pk).update(intentos=1, ultimo_error='Rebote simulado: el dominio no existe.')

        # 8) Laboratorio: el mismo cliente escribe a otra cuenta (historial por contacto)
        crear_mensaje(
            lab, 'entrada', de=cli_correo, de_nombre=cli_nombre,
            para=[{'nombre': '', 'correo': lab.direccion}],
            asunto='Consulta por resultados de Proctor – SOL-2026-118',
            texto='¿Ya tienen el resultado del Proctor modificado? Lo necesitamos para el viernes.',
            fecha=hace(hours=8),
        )
        crear_mensaje(
            lab, 'entrada', de='metrologia@calibra.example', de_nombre='Calibra SAC',
            para=[{'nombre': '', 'correo': lab.direccion}],
            asunto='Certificado de calibración de prensa hidráulica',
            texto='Adjuntamos el certificado vigente hasta noviembre de 2027.',
            fecha=hace(days=5), leido=True,
            adjuntos=[('certificado-calibracion.pdf', 'application/pdf',
                       _pdf('Certificado de calibración', ['Equipo: prensa 2000 kN', 'Vigencia: 2027-11']), '', False)],
        )

        # 9) Quejas
        crear_mensaje(
            quejas, 'entrada', de='gerencia@obrasur.example', de_nombre='Gerencia Obras Sur',
            para=[{'nombre': '', 'correo': quejas.direccion}],
            asunto='Reclamo por demora en informe de ensayo',
            texto='El informe comprometido para el lunes aún no llega. Solicitamos una fecha de entrega.',
            fecha=hace(hours=20),
        )

    def _firmas(self, cuentas, usuarios):
        informes = cuentas['informes']
        compartida = Firma.objects.create(
            nombre='Ventas VICAF', cuenta=informes, para_nuevos=True, para_respuestas=True,
            html='<p>—<br><b>Área de Informes y Cotizaciones</b><br>GRUPO VICAF SAC · Cajamarca<br>'
                 'Tel. +51 964 326 364</p>',
        )
        CuentaCorreo.objects.filter(pk=informes.pk).update(firma_predeterminada=compartida)
        for usuario in usuarios:
            Firma.objects.filter(usuario=usuario, nombre__in=['Completa', 'Breve']).delete()
            nombre = getattr(getattr(usuario, 'trabajadorprofile', None), 'nombre_completo', '') or usuario.username
            Firma.objects.create(
                nombre='Completa', usuario=usuario, para_nuevos=True,
                html=f'<p>Saludos cordiales,<br><b>{nombre}</b><br>GRUPO VICAF SAC<br>'
                     'Laboratorio de ensayo de materiales · Cajamarca</p>',
            )
            Firma.objects.create(nombre='Breve', usuario=usuario, para_respuestas=True,
                                 html=f'<p>Saludos,<br>{nombre}</p>')
