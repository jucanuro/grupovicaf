from django.db import models
import uuid
import qrcode
from io import BytesIO
from django.core.files import File
from django.core.files.storage import FileSystemStorage
from django.conf import settings
from django.contrib.auth.models import User
from django.utils.timezone import now
from django.utils import timezone
import io
from django.core.files.base import ContentFile
from pypdf import PdfReader, PdfWriter
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter
from django.db import IntegrityError, transaction
from django.core.validators import MinValueValidator
from clientes.models import Cliente
from trabajadores.models import TrabajadorProfile 
from core.models import siguiente_correlativo
from . import formularios_ensayo
from servicios.models import Cotizacion, CotizacionDetalle, Servicio, CategoriaServicio, Subcategoria
import os
import datetime
import logging

logger = logging.getLogger(__name__)

def documento_file_path(instance, filename):
    """Genera la ruta de subida para documentos finales basados en cliente y proyecto."""
    proyecto_id = instance.proyecto.id if instance.proyecto else 'default'
    cliente_id = instance.proyecto.cliente.id if instance.proyecto and instance.proyecto.cliente else 'default'
    return f'proyectos/documentos/{cliente_id}/{proyecto_id}/{filename}'

class Proyecto(models.Model):
    """Representa un proyecto de trabajo generado tras la aprobación de una cotización."""
    
    ESTADOS_PROYECTO = [
        ('PENDIENTE', 'Pendiente de Inicio'),
        ('EN_CURSO', 'En Curso'),
        ('MUESTRAS_ASIGNADAS', 'Técnicos Asignados'),
        ('MUESTRAS_VALIDADAS', 'Muestras Validadas (Listo para Informe)'),
        ('FINALIZADO', 'Finalizado'),
        ('CANCELADO', 'Cancelado'),
    ]

    cotizacion = models.ForeignKey(
        Cotizacion, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        verbose_name="Cotización de Origen"
    )
    
    nombre_proyecto = models.CharField(max_length=255, verbose_name="Nombre del Proyecto")
    codigo_proyecto = models.CharField(max_length=50, unique=True, verbose_name="Código del Proyecto (Interno)")
    cliente = models.ForeignKey(
        Cliente, 
        on_delete=models.CASCADE, 
        verbose_name="Cliente", 
        related_name='proyectos'
    )
    
    descripcion_proyecto = models.TextField(verbose_name="Descripción", blank=True, null=True)
    monto_cotizacion = models.DecimalField(max_digits=10, decimal_places=2, default=0.00, verbose_name="Monto de la Cotización Aprobada")
    codigo_voucher = models.CharField(max_length=100, verbose_name="Código de Voucher/Operación de Pago", blank=True, null=True)

    fecha_inicio = models.DateField(default=timezone.now, verbose_name="Fecha de Inicio Real")
    fecha_entrega_estimada = models.DateField(blank=True, null=True, verbose_name="Fecha de Entrega Estimada")
    estado = models.CharField(max_length=20, choices=ESTADOS_PROYECTO, default='PENDIENTE', verbose_name="Estado del Proyecto")
    
    numero_muestras = models.PositiveIntegerField(default=0, verbose_name="Número Total de Muestras (Según Cotización)")
    numero_muestras_registradas = models.PositiveIntegerField(default=0, verbose_name="Número de Muestras con Resultados Finales")

    creado_en = models.DateTimeField(auto_now_add=True)
    modificado_en = models.DateTimeField(auto_now=True)
    
    @property
    def muestras_registradas_reales(self):
        return self.muestras.count()

    @property
    def estado_sugerido_por_muestras(self):
        muestras_registradas = self.muestras_registradas_reales
        muestras_totales = self.numero_muestras

        if muestras_registradas == 0:
            return 'PENDIENTE'
        
        if muestras_registradas > 0 and muestras_registradas < muestras_totales:
            return 'EN_CURSO'
        
        if muestras_registradas >= muestras_totales and muestras_totales > 0:
            return 'MUESTRAS_ASIGNADAS'
            
        return 'PENDIENTE' 

    def actualizar_estado_por_muestreo(self):
        
        logger.info("-" * 50)
        logger.info(f"DEBUGGING ESTADO: Proyecto PK={self.pk}, Actual={self.estado}")
        logger.info(f"Muestras Totales (numero_muestras): {self.numero_muestras}")
        logger.info(f"Muestras Contadas (muestras_registradas_reales): {self.muestras_registradas_reales}")
        
        estado_sugerido = self.estado_sugerido_por_muestras
        
        jerarquia = ['PENDIENTE', 'EN_CURSO', 'MUESTRAS_ASIGNADAS', 'MUESTRAS_VALIDADAS', 'FINALIZADO']
        
        if self.estado not in ['FINALIZADO', 'CANCELADO']:
            
            try:
                indice_actual = jerarquia.index(self.estado)
                indice_sugerido = jerarquia.index(estado_sugerido)
                
                if indice_sugerido > indice_actual:
                    Proyecto.objects.filter(pk=self.pk).update(estado=estado_sugerido)
                    self.estado = estado_sugerido 
                    return True

            except ValueError:
                pass
                
        return False
    
    def __str__(self):
        return f"{self.nombre_proyecto} ({self.codigo_proyecto})"

    class Meta:
        verbose_name = "Proyecto"
        verbose_name_plural = "Proyectos"
        ordering = ['-fecha_inicio']
        
class TipoMuestra(models.Model):
    nombre = models.CharField(max_length=100)
    sigla = models.CharField(max_length=5, unique=True) 
   
class UnidadMedida(models.Model):
    nombre = models.CharField(max_length=100, unique=True)
    codigo = models.CharField(max_length=20, unique=True)
    activo = models.BooleanField(default=True)

    class Meta:
        verbose_name = "Unidad de Medida"
        verbose_name_plural = "Unidades de Medida"
        ordering = ['codigo']

    def __str__(self):
        return self.codigo
 
class RecepcionMuestra(models.Model):
    cotizacion = models.ForeignKey(Cotizacion, on_delete=models.CASCADE, related_name='recepciones')
    procedencia = models.CharField(max_length=255)
    responsable_cliente = models.CharField(max_length=255)
    telefono = models.CharField(max_length=20)
    
    fecha_recepcion = models.DateTimeField(default=timezone.now)
    fecha_fabricacion = models.DateField(null=True, blank=True)
    fecha_muestreo = models.DateField(null=True, blank=True)
    fecha_ensayo_programado = models.DateField(null=True, blank=True)
    
    responsable_recepcion = models.ForeignKey(User, on_delete=models.PROTECT)

    # FOR-004 / informe: ubicación de la obra (PM-C03). Si está vacía, se usa
    # la procedencia.
    ubicacion_proyecto = models.CharField(
        max_length=255, blank=True, default='', verbose_name="Ubicación del proyecto",
    )

    @property
    def ubicacion_informe(self):
        return self.ubicacion_proyecto or self.procedencia

class MuestraDetalle(models.Model):
    recepcion = models.ForeignKey(RecepcionMuestra, related_name='muestras', on_delete=models.CASCADE)
    tipo_muestra = models.ForeignKey(TipoMuestra, on_delete=models.PROTECT)

    nro_item = models.IntegerField(default=1)
    descripcion = models.CharField(max_length=255)
    masa_aprox = models.DecimalField(max_digits=10, decimal_places=2)
    cantidad = models.IntegerField(default=1)
    unidad_medida = models.ForeignKey(UnidadMedida, on_delete=models.CASCADE, null=True, blank=True)
    observaciones = models.TextField(null=True, blank=True)

    # Datos de la orden FOR-004 que da el cliente (HU-LIMS-11). Opcionales:
    # las muestras de suelos no los usan.
    codigo_cliente = models.CharField(max_length=100, blank=True, default='', verbose_name="ID del cliente")
    elemento_estructural = models.CharField(max_length=150, blank=True, default='', verbose_name="Elemento estructural")
    fc_diseno = models.DecimalField(
        max_digits=7, decimal_places=2, null=True, blank=True,
        validators=[MinValueValidator(0)], verbose_name="Resistencia de diseño f'c (kg/cm²)",
    )
    fecha_fabricacion = models.DateField(null=True, blank=True, verbose_name="Fecha de fabricación / extracción")
    edad_ensayo_dias = models.PositiveSmallIntegerField(null=True, blank=True, verbose_name="Edad de ensayo solicitada (días)")
    material = models.CharField(max_length=60, blank=True, default='', verbose_name="Material")
    tipo_probeta = models.CharField(max_length=60, blank=True, default='', verbose_name="Tipo de muestra (informe)")

    @property
    def fecha_ensayo_solicitada(self):
        if self.fecha_fabricacion and self.edad_ensayo_dias is not None:
            return self.fecha_fabricacion + datetime.timedelta(days=self.edad_ensayo_dias)
        return None

    codigo_laboratorio = models.CharField(max_length=50, unique=True, blank=True)

    def generar_codigo_laboratorio(self):
        anio = timezone.now().year
        sigla = self.tipo_muestra.sigla.upper()
        prefijo = f"V-M-{anio}-{sigla}-"

        numero = siguiente_correlativo(
            prefijo,
            MuestraDetalle.objects.filter(codigo_laboratorio__startswith=prefijo)
            .values_list('codigo_laboratorio', flat=True),
        )
        return f"{prefijo}{numero:04d}"

    def save(self, *args, **kwargs):
        if self.codigo_laboratorio:
            return super().save(*args, **kwargs)

        for _ in range(10):
            self.codigo_laboratorio = self.generar_codigo_laboratorio()
            try:
                with transaction.atomic():
                    return super().save(*args, **kwargs)
            except IntegrityError:
                self.codigo_laboratorio = None

        raise IntegrityError("No se pudo generar un código_laboratorio único después de varios intentos.")
              
class SolicitudEnsayo(models.Model):
    """
    Cabecera del registro VCF-LAB-FOR-068.
    Representa la orden de trabajo interna para el laboratorio.
    """
    codigo_solicitud = models.CharField(
        max_length=50, unique=True, verbose_name="No. DE SOLICITUD"
    )
    recepcion = models.OneToOneField(
        'RecepcionMuestra', 
        on_delete=models.CASCADE, 
        related_name='solicitud_ensayo',
        verbose_name="Recepción Asociada"
    )
    cotizacion = models.ForeignKey(
        Cotizacion, 
        on_delete=models.PROTECT, 
        related_name='solicitudes_ensayo',
        verbose_name="No. COTIZACIÓN"
    )
    
    ESTADOS = [
        ('pendiente', 'PENDIENTE'),
        ('proceso', 'EN PROCESO'),
        ('finalizado', 'FINALIZADO'),
    ]
    estado = models.CharField(
        max_length=20, 
        choices=ESTADOS, 
        default='pendiente',
        verbose_name="ESTADO OPERATIVO"
    )
    
    fecha_solicitud = models.DateField(default=timezone.now, verbose_name="FECHA DE SOLICITUD")
    
    fecha_entrega_programada = models.DateField(verbose_name="FECHA DE ENTREGA DE REGISTROS (PROGRAMADA)")
    fecha_entrega_real = models.DateField(null=True, blank=True, verbose_name="FECHA REAL DE ENTREGA DE REGISTROS")
    
    elaborado_por = models.ForeignKey(
        TrabajadorProfile, 
        on_delete=models.PROTECT, 
        related_name='solicitudes_elaboradas',
        verbose_name="PERSONA QUE ELABORA LA SOLICITUD"
    )
    
    revisado_por = models.ForeignKey(
        TrabajadorProfile, 
        on_delete=models.SET_NULL, 
        null=True, blank=True, 
        related_name='solicitudes_revisadas',
        verbose_name="FIRMA JEFE DE LABORATORIO"
    )

    class Meta:
        verbose_name = "Solicitud de Ensayo"
        verbose_name_plural = "Solicitudes de Ensayo"
        ordering = ['-fecha_solicitud']

    def __str__(self):
        return f"{self.codigo_solicitud} - {self.cotizacion.cliente.razon_social}"

    def avance_resultados(self):
        """(terminadas, total) de las líneas de la solicitud."""
        estados = list(self.detalles.values_list('resultado__estado', flat=True))
        terminadas = sum(1 for e in estados if e in ResultadoEnsayo.ESTADOS_CERRADOS)
        return terminadas, len(estados)

    def sincronizar_estado(self):
        """El estado sale de los resultados: nadie finaliza sin todas las líneas terminadas.

        - Todas terminadas → finalizado (con fecha real de entrega).
        - Alguna con resultado (o una devuelta) → en proceso.
        """
        terminadas, total = self.avance_resultados()
        if total and terminadas == total:
            nuevo = 'finalizado'
        elif self.detalles.filter(resultado__isnull=False).exists():
            nuevo = 'proceso'
        else:
            return
        cambios = {}
        if self.estado != nuevo:
            cambios['estado'] = nuevo
        if nuevo == 'finalizado' and not self.fecha_entrega_real:
            cambios['fecha_entrega_real'] = timezone.localdate()
        if nuevo == 'proceso' and self.fecha_entrega_real:
            cambios['fecha_entrega_real'] = None
        if cambios:
            SolicitudEnsayo.objects.filter(pk=self.pk).update(**cambios)
            for campo, valor in cambios.items():
                setattr(self, campo, valor)

class DetalleSolicitudEnsayo(models.Model):
    """
    Detalle línea por línea de los ensayos a realizar por cada muestra.
    """
    solicitud = models.ForeignKey(
        SolicitudEnsayo, 
        on_delete=models.CASCADE, 
        related_name='detalles'
    )
    muestra = models.ForeignKey(
        'MuestraDetalle', 
        on_delete=models.PROTECT, 
        verbose_name="Código de Muestra (Lab)"
    )
    
    # Vinculamos al detalle de la cotización para traer Norma y Método automáticamente
    servicio_cotizado = models.ForeignKey(
        CotizacionDetalle, 
        on_delete=models.PROTECT,
        verbose_name="Servicio/Ensayo"
    )
    
    # Estos campos se extraen del servicio_cotizado pero se guardan por si cambian en la oferta
    descripcion_ensayo = models.CharField(max_length=255, verbose_name="Descripción")
    norma = models.CharField(max_length=255, verbose_name="Norma de ensayo")
    metodo = models.CharField(max_length=100, blank=True, null=True, verbose_name="Método")
    
    tecnico_asignado = models.ForeignKey(
        TrabajadorProfile, 
        on_delete=models.SET_NULL, 
        null=True, blank=True, 
        verbose_name="Técnico Asignado"
    )
    
    fecha_entrega_programada = models.DateField(verbose_name="Entrega Programada")
    fecha_entrega_real = models.DateField(null=True, blank=True, verbose_name="Entrega Real")
    
    aceptado_tecnico = models.BooleanField(
        default=False, 
        verbose_name="Aceptación (Firma)",
        help_text="Check para reemplazar la firma manual del técnico"
    )
    
    observaciones = models.TextField(blank=True, null=True, verbose_name="Observaciones")

    class Meta:
        verbose_name = "Detalle de Solicitud"
        verbose_name_plural = "Detalles de Solicitudes"

    def __str__(self):
        return f"{self.muestra.codigo_laboratorio} - {self.descripcion_ensayo}"

class IncidenciaSolicitud(models.Model):
    """
    Registro de incidencias durante el ensayo (Reporte de incidencias).
    Basado en el formato de la imagen de referencia.
    """
    solicitud = models.ForeignKey(
        SolicitudEnsayo, 
        on_delete=models.CASCADE, 
        related_name='incidencias'
    )
    detalle_incidencia = models.TextField(verbose_name="Detalle de la incidencia")
    fecha_ocurrencia = models.DateTimeField(default=timezone.now, verbose_name="Fecha de ocurrencia")
    
    representante_cliente = models.CharField(
        max_length=255, 
        blank=True, null=True, 
        verbose_name="Representante del Cliente"
    )
    representante_laboratorio = models.ForeignKey(
        TrabajadorProfile, 
        on_delete=models.SET_NULL, 
        null=True, 
        verbose_name="Responsable del laboratorio (JL / SL)",
        related_name="incidencias_responsable"
    )

    esta_autorizada = models.BooleanField(
        default=False, 
        verbose_name="Autorizado",
        help_text="Indica si la incidencia ha sido validada/firmada electrónicamente."
    )
    autorizado_por = models.ForeignKey(
        TrabajadorProfile,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="incidencias_autorizadas",
        verbose_name="Firma de Autorización"
    )
    fecha_autorizacion = models.DateTimeField(
        null=True, 
        blank=True, 
        verbose_name="Fecha de Firma"
    )

    class Meta:
        verbose_name = "Incidencia de Solicitud"
        verbose_name_plural = "Incidencias de Solicitudes"
        ordering = ['fecha_ocurrencia']

    def __str__(self):
        estado = "✅" if self.esta_autorizada else "⏳"
        return f"{estado} Incidencia {self.id} - Solicitud {self.solicitud.codigo_solicitud}"

    def autorizar(self, trabajador):
        """
        Método para ejecutar la firma/autorización de la incidencia.
        """
        self.esta_autorizada = True
        self.autorizado_por = trabajador
        self.fecha_autorizacion = timezone.now()
        self.save()
                
class InformeFinal(models.Model):
    ESTADOS_ENVIO = [
        ('pendiente', 'Pendiente de Envío'),
        ('enviado', 'Enviado al Cliente'),
    ]

    solicitud = models.OneToOneField(
        SolicitudEnsayo, 
        on_delete=models.CASCADE, 
        related_name='informe_final'
    )
    codigo_informe = models.CharField(max_length=50, unique=True, editable=False)
    archivo_pdf = models.FileField(upload_to='informes_finales/pdfs/%Y/%m/')
    fecha_emision = models.DateTimeField(default=now)
    
    estado_envio = models.CharField(max_length=20, choices=ESTADOS_ENVIO, default='pendiente')
    fecha_envio = models.DateTimeField(null=True, blank=True)
    
    slug_validacion = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    qr_code = models.ImageField(upload_to='informes_finales/qrs/', blank=True, null=True)
    
    responsable_firma = models.ForeignKey(
        TrabajadorProfile, on_delete=models.PROTECT, related_name='informes_firmados'
    )
    descargas_count = models.PositiveIntegerField(default=0)

    # Informe que arma el propio sistema (compresión, HU-LIMS-16). Vacío en
    # los informes que se suben a mano como PDF.
    PDF_GENERANDO = 'generando'
    PDF_LISTO = 'listo'
    PDF_ERROR = 'error'
    ESTADOS_PDF = [(PDF_GENERANDO, 'Generando'), (PDF_LISTO, 'Listo'), (PDF_ERROR, 'Error al generar')]
    pdf_estado = models.CharField(max_length=12, choices=ESTADOS_PDF, blank=True, default='')
    pdf_error = models.CharField(max_length=255, blank=True, default='')

    class Meta:
        verbose_name = "Informe Final"
        verbose_name_plural = "Informes Finales"

    def save(self, *args, **kwargs):
        if not self.codigo_informe:
            # Antes count() + 1: al borrar un informe el siguiente repetía número.
            prefijo = f"INF-{now().year}-"
            numero = siguiente_correlativo(
                prefijo,
                InformeFinal.objects.filter(codigo_informe__startswith=prefijo)
                .values_list('codigo_informe', flat=True),
            )
            self.codigo_informe = f"{prefijo}{numero:04d}"
        
        if not self.qr_code:
            self.generar_qr_validacion()
            
        super().save(*args, **kwargs)

    def generar_qr_validacion(self):
        from django.conf import settings
        base_url = getattr(settings, 'SITE_URL', 'http://127.0.0.1:8000')
        url_final = f"{base_url}/proyectos/v/{self.slug_validacion}/"
        
        qr = qrcode.QRCode(version=1, box_size=10, border=5)
        qr.add_data(url_final)
        qr.make(fit=True)
        img = qr.make_image(fill_color="black", back_color="white")
        
        buffer = io.BytesIO()
        img.save(buffer, format='PNG')
        self.qr_code.save(f"QR_{self.codigo_informe}.png", ContentFile(buffer.getvalue()), save=False)

    def estampar_qr_en_pdf(self):
        """Pega el QR en la parte inferior derecha de la última página del PDF"""
        if not self.archivo_pdf or not self.qr_code:
            return False

        packet = io.BytesIO()
        can = canvas.Canvas(packet, pagesize=letter)
        can.drawImage(self.qr_code.path, 480, 50, width=70, height=70)
        can.save()
        packet.seek(0)

        new_pdf = PdfReader(packet)
        existing_pdf = PdfReader(self.archivo_pdf.path)
        output = PdfWriter()

        for i, page in enumerate(existing_pdf.pages):
            if i == len(existing_pdf.pages) - 1:
                page.merge_page(new_pdf.pages[0])
            output.add_page(page)

        with open(self.archivo_pdf.path, "wb") as f:
            output.write(f)
        return True

# ---------------------------------------------------------------------------
# Ensayo de compresión de probetas (HU-LIMS-14): registro mínimo por probeta
# y sus cinco fotos obligatorias. Las medidas y el informe llegan en otras HU.
# ---------------------------------------------------------------------------

def es_ensayo_compresion(norma, codigo_servicio=''):
    """El ensayo es la compresión de probetas cilíndricas (ASTM C39 / EC001)."""
    return 'C39' in (norma or '').upper() or (codigo_servicio or '').upper() == 'EC001'


class AlmacenFotosEnsayo(FileSystemStorage):
    """Carpeta privada de las fotos (fuera de MEDIA_ROOT: nginx no la sirve).

    La ubicación se lee de ``settings.ENSAYOS_FOTOS_DIR`` en cada uso, no al
    importar el modelo, para que ``override_settings`` funcione en los tests.
    """

    @property
    def base_location(self):
        return settings.ENSAYOS_FOTOS_DIR

    @property
    def location(self):
        return os.path.abspath(self.base_location)


def _almacen_fotos_ensayo():
    return AlmacenFotosEnsayo()


def ruta_foto_ensayo(instance, filename):
    # Nombre aleatorio: ni el código de la muestra ni el del cliente en la ruta.
    return f"compresion/{timezone.now():%Y/%m}/{uuid.uuid4().hex}.jpg"


def ruta_hoja_ensayo(instance, filename):
    extension = os.path.splitext(filename)[1].lower()[:6]
    return f"hojas/{timezone.now():%Y/%m}/{uuid.uuid4().hex}{extension}"


class Equipo(models.Model):
    """Equipo del laboratorio que se declara en el informe (HU-LIMS-12)."""
    TIPO_PRENSA = 'PRC'
    TIPO_BALANZA = 'BAL'
    TIPO_VERNIER = 'VER'
    TIPO_TERMOHIGROMETRO = 'TMG'
    TIPO_CUNA = 'CUÑ'
    TIPO_ESCUADRA = 'ESC'
    TIPO_ANILLOS = 'ARE'
    TIPO_NEOPRENO = 'NEO'
    TIPO_OTRO = 'OTR'
    TIPOS = [
        (TIPO_PRENSA, 'Prensa'),
        (TIPO_BALANZA, 'Balanza'),
        (TIPO_VERNIER, 'Vernier'),
        (TIPO_TERMOHIGROMETRO, 'Termohigrómetro'),
        (TIPO_CUNA, 'Cuña'),
        (TIPO_ESCUADRA, 'Escuadra'),
        (TIPO_ANILLOS, 'Anillos retenedores'),
        (TIPO_NEOPRENO, 'Neoprenos'),
        (TIPO_OTRO, 'Otro'),
    ]

    codigo = models.CharField(max_length=40, unique=True, verbose_name="Código interno")
    nombre = models.CharField(max_length=120, verbose_name="Nombre")
    tipo = models.CharField(max_length=3, choices=TIPOS, verbose_name="Tipo")
    marca = models.CharField(max_length=80, blank=True, default='')
    modelo = models.CharField(max_length=80, blank=True, default='')
    serie = models.CharField(max_length=80, blank=True, default='', verbose_name="N.º de serie")
    fecha_calibracion = models.DateField(null=True, blank=True, verbose_name="Fecha de calibración")
    vence_calibracion = models.DateField(null=True, blank=True, verbose_name="Vencimiento de la calibración")
    certificado = models.CharField(max_length=80, blank=True, default='', verbose_name="N.º de certificado")
    activo = models.BooleanField(default=True)

    class Meta:
        verbose_name = "Equipo"
        verbose_name_plural = "Equipos"
        ordering = ['tipo', 'codigo']

    def __str__(self):
        return f"{self.codigo} · {self.nombre}"

    def vencido(self, fecha=None):
        """DP-LIMS-18 A: con la calibración vencida no se puede elegir."""
        fecha = fecha or timezone.localdate()
        return bool(self.vence_calibracion and self.vence_calibracion < fecha)

    @classmethod
    def disponibles(cls, tipo, fecha=None):
        fecha = fecha or timezone.localdate()
        return cls.objects.filter(tipo=tipo, activo=True).filter(
            models.Q(vence_calibracion__isnull=True) | models.Q(vence_calibracion__gte=fecha)
        )


class SesionEnsayo(models.Model):
    """Una tanda de ensayos del técnico: condiciones ambientales inicial y
    final y los equipos usados, comunes a todas sus probetas (como en el
    informe real, donde las 3 probetas comparten esos datos)."""
    # Equipos del FOR-039, en el orden del informe.
    EQUIPOS = [
        ('prensa', Equipo.TIPO_PRENSA),
        ('balanza', Equipo.TIPO_BALANZA),
        ('vernier', Equipo.TIPO_VERNIER),
        ('termohigrometro', Equipo.TIPO_TERMOHIGROMETRO),
        ('cuna', Equipo.TIPO_CUNA),
        ('escuadra', Equipo.TIPO_ESCUADRA),
    ]
    # Accesorios del formato de registro (anillos retenedores y neoprenos). Son
    # opcionales en el modelo solo por las sesiones anteriores; el formulario
    # los exige.
    ACCESORIOS = [
        ('anillos', Equipo.TIPO_ANILLOS),
        ('neopreno', Equipo.TIPO_NEOPRENO),
    ]
    # Orden en que el formato de registro lista el equipamiento empleado.
    ORDEN_EQUIPOS = ['prensa', 'vernier', 'balanza', 'termohigrometro', 'anillos', 'cuna', 'escuadra', 'neopreno']
    # Comprobación funcional de equipos del formato de registro:
    # (clave, equipo, pregunta, respuesta esperada).
    COMPROBACION = [
        ('prensa_fugas', 'Prensa', 'Se evidencia fugas de aceite en la máquina.', False),
        ('prensa_papel', 'Prensa', 'El rollo de papel térmico tiene suficiente papel para impresión de carga máxima.', True),
        ('prensa_tornillo', 'Prensa', 'El tornillo sin fin gira libremente.', True),
        ('prensa_indicadores', 'Prensa', 'Los indicadores y botones de control son legibles y están en buen estado.', True),
        ('vernier_tornillo', 'Vernier', 'El tornillo de fijación se encuentra adecuadamente ajustado.', True),
        ('vernier_escalas', 'Vernier', 'Las escalas graduadas son legibles.', True),
        ('anillos_superficie', 'Anillos retenedores', 'Se evidencia una superficie libre de defectos, grietas o irregularidades.', True),
        ('neoprenos_superficie', 'Neoprenos', 'Se evidencia una superficie libre de defectos, grietas o irregularidades.', True),
    ]

    tecnico = models.ForeignKey(TrabajadorProfile, on_delete=models.PROTECT, related_name='sesiones_ensayo')
    fecha = models.DateField(default=timezone.localdate)
    temperatura_inicial = models.DecimalField(max_digits=5, decimal_places=2, verbose_name="Temperatura inicial (°C)")
    humedad_inicial = models.DecimalField(max_digits=5, decimal_places=2, verbose_name="Humedad relativa inicial (%)")
    temperatura_final = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True, verbose_name="Temperatura final (°C)")
    humedad_final = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True, verbose_name="Humedad relativa final (%)")
    prensa = models.ForeignKey(Equipo, on_delete=models.PROTECT, related_name='+')
    balanza = models.ForeignKey(Equipo, on_delete=models.PROTECT, related_name='+')
    vernier = models.ForeignKey(Equipo, on_delete=models.PROTECT, related_name='+')
    termohigrometro = models.ForeignKey(Equipo, on_delete=models.PROTECT, related_name='+')
    cuna = models.ForeignKey(Equipo, on_delete=models.PROTECT, related_name='+')
    escuadra = models.ForeignKey(Equipo, on_delete=models.PROTECT, related_name='+')
    anillos = models.ForeignKey(Equipo, on_delete=models.PROTECT, related_name='+', null=True, blank=True)
    neopreno = models.ForeignKey(Equipo, on_delete=models.PROTECT, related_name='+', null=True, blank=True)
    neopreno_usos = models.CharField(max_length=20, blank=True, default='', verbose_name="N.º de usos de neoprenos")
    comprobacion = models.JSONField(default=dict, blank=True, verbose_name="Comprobación funcional de equipos")
    # Quien la abrió en el sistema cuando no es el técnico (pasa a limpio el formato en papel).
    registrada_por = models.ForeignKey(
        TrabajadorProfile, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='+', verbose_name="Registrada por",
    )
    abierta_en = models.DateTimeField(auto_now_add=True)
    cerrada_en = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = "Sesión de ensayo"
        verbose_name_plural = "Sesiones de ensayo"
        ordering = ['-abierta_en']

    def __str__(self):
        return f"Sesión {self.fecha:%d/%m/%Y} · {self.tecnico}"

    @property
    def abierta(self):
        return self.cerrada_en is None

    def equipos_usados(self):
        """[(etiqueta, código)] en el orden del formato; omite lo que la sesión no tiene."""
        etiquetas = dict(Equipo.TIPOS)
        tipos = dict(self.EQUIPOS + self.ACCESORIOS)
        filas = []
        for campo in self.ORDEN_EQUIPOS:
            equipo = getattr(self, campo)
            if equipo is None:
                continue
            codigo = equipo.codigo
            if campo == 'neopreno' and self.neopreno_usos:
                codigo += f" (usos: {self.neopreno_usos})"
            filas.append((etiquetas[tipos[campo]], codigo))
        return filas

    def comprobacion_items(self):
        """Respuestas de la comprobación funcional; vacía en sesiones anteriores."""
        if not self.comprobacion:
            return []
        filas = []
        for clave, equipo, pregunta, esperado in self.COMPROBACION:
            respuesta = self.comprobacion.get(clave)
            filas.append({
                'equipo': equipo, 'pregunta': pregunta, 'respuesta': respuesta,
                'conforme': respuesta is not None and respuesta == esperado,
            })
        return filas

    @classmethod
    def abierta_de(cls, perfil):
        if perfil is None:
            return None
        return cls.objects.filter(tecnico=perfil, cerrada_en__isnull=True).first()


class PlantillaFormulario(models.Model):
    """Formulario de resultados de uno o varios servicios (HU-LIMS-36).

    Reproduce los campos del formato en papel del ensayo. Los ensayos sin
    plantilla usan el formulario general (resumen y las 6 fotos).
    """
    nombre = models.CharField(max_length=150, verbose_name="Nombre del formulario")
    servicios = models.ManyToManyField(
        'servicios.Servicio', blank=True, related_name='plantillas_formulario',
        verbose_name="Servicios que lo usan",
    )
    campos = models.JSONField(
        default=list, blank=True,
        help_text=("Lista de campos. Cada uno: clave, etiqueta, tipo "
                   "(numero, texto, texto_largo, fecha, si_no, cumple, seleccion), unidad, requerido, grupo, ayuda, opciones."),
    )
    instrucciones = models.TextField(blank=True, default='', verbose_name="Instrucciones para el técnico")
    activo = models.BooleanField(default=True)
    actualizado_en = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Formulario de resultados"
        verbose_name_plural = "Formularios de resultados"
        ordering = ['nombre']

    def __str__(self):
        return self.nombre

    def clean(self):
        from django.core.exceptions import ValidationError
        errores = formularios_ensayo.validar_campos(self.campos)
        if errores:
            raise ValidationError({'campos': errores})

    def como_esquema(self):
        return {
            'nombre': self.nombre, 'campos': formularios_ensayo.normalizar_campos(self.campos),
            'instrucciones': self.instrucciones,
        }

    @classmethod
    def para_detalle(cls, detalle):
        servicio = getattr(detalle.servicio_cotizado, 'servicio', None)
        if servicio is None:
            return None
        return cls.objects.filter(activo=True, servicios=servicio).order_by('pk').first()


class ResultadoEnsayo(models.Model):
    """Resultado de una línea de la solicitud (muestra × ensayo).

    La plantilla dice qué se registra: «compresion» (ASTM C39, medidas,
    cálculo y 5 fotos) o «general» (resumen, hoja de cálculo y 2 fotos) para
    los ensayos que aún no tienen formato propio.
    """
    PLANTILLA_COMPRESION = 'compresion'
    PLANTILLA_GENERAL = 'general'
    PLANTILLAS = [
        (PLANTILLA_COMPRESION, 'Compresión de probetas (ASTM C39)'),
        (PLANTILLA_GENERAL, 'General'),
    ]
    ESTADO_BORRADOR = 'borrador'
    ESTADO_TERMINADO = 'terminado'
    ESTADO_APROBADO = 'aprobado'
    ESTADOS = [
        (ESTADO_BORRADOR, 'En registro'),
        (ESTADO_TERMINADO, 'Terminado'),
        (ESTADO_APROBADO, 'Aprobado'),
    ]
    # Terminado o aprobado: el técnico ya no puede modificarlo.
    ESTADOS_CERRADOS = (ESTADO_TERMINADO, ESTADO_APROBADO)

    detalle = models.OneToOneField(
        DetalleSolicitudEnsayo,
        on_delete=models.CASCADE,
        related_name='resultado',
        verbose_name="Ensayo de la solicitud",
    )
    plantilla = models.CharField(max_length=20, choices=PLANTILLAS, default=PLANTILLA_GENERAL)
    estado = models.CharField(max_length=20, choices=ESTADOS, default=ESTADO_BORRADOR)
    resumen = models.TextField(blank=True, default='', verbose_name="Resumen de resultados")
    # Formulario configurable por servicio (HU-LIMS-36): el esquema se copia de la
    # plantilla al crear el resultado y `datos` guarda lo que escribió el técnico.
    esquema = models.JSONField(default=dict, blank=True, verbose_name="Formulario del ensayo")
    datos = models.JSONField(default=dict, blank=True, verbose_name="Datos del formulario")
    hoja_calculo = models.FileField(
        storage=_almacen_fotos_ensayo, upload_to=ruta_hoja_ensayo, blank=True,
        verbose_name="Hoja de cálculo",
    )
    fecha_ensayo = models.DateField(null=True, blank=True, verbose_name="Fecha de ensayo")
    observaciones = models.TextField(blank=True, default='', verbose_name="Observaciones")
    tecnico = models.ForeignKey(
        TrabajadorProfile,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='resultados_ejecutados',
        verbose_name="Ejecutado por",
    )
    # Quien lo pasó al sistema cuando no es el técnico que ejecutó (formato en papel).
    registrado_por = models.ForeignKey(
        TrabajadorProfile, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='+', verbose_name="Registrado por",
    )
    sesion = models.ForeignKey(
        SesionEnsayo, on_delete=models.PROTECT, null=True, blank=True,
        related_name='ensayos', verbose_name="Sesión de ensayo",
    )

    # Datos medidos (HU-LIMS-13). mm, g y kN como en el FOR-039.
    masa_g = models.DecimalField(max_digits=8, decimal_places=1, null=True, blank=True, verbose_name="Masa (g)")
    d1 = models.DecimalField(max_digits=7, decimal_places=2, null=True, blank=True, verbose_name="D1 (mm)")
    d2 = models.DecimalField(max_digits=7, decimal_places=2, null=True, blank=True, verbose_name="D2 (mm)")
    l1 = models.DecimalField(max_digits=7, decimal_places=2, null=True, blank=True, verbose_name="L1 (mm)")
    l2 = models.DecimalField(max_digits=7, decimal_places=2, null=True, blank=True, verbose_name="L2 (mm)")
    l3 = models.DecimalField(max_digits=7, decimal_places=2, null=True, blank=True, verbose_name="L3 (mm)")
    carga_kn = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True, verbose_name="Carga máxima (kN)")
    tipo_fractura = models.PositiveSmallIntegerField(
        null=True, blank=True, choices=[(n, f'Tipo {n}') for n in range(1, 7)], verbose_name="Tipo de fractura",
    )
    defectos = models.CharField(max_length=255, blank=True, default='', verbose_name="Defectos del espécimen")
    # Formato de registro: tipos de defecto (a-e), verificaciones y evidencia.
    tipos_defecto = models.CharField(max_length=20, blank=True, default='', verbose_name="Tipos de defecto")
    verif_perpendicularidad = models.BooleanField(null=True, blank=True, verbose_name="Perpendicularidad (≤ 0,5°)")
    verif_planitud = models.BooleanField(null=True, blank=True, verbose_name="Planitud (≤ 0,05 mm)")
    video_grabado = models.BooleanField(default=False, verbose_name="Se grabó video del ensayo")

    # Resultados calculados (proyectos.calculos_compresion), guardados al terminar.
    edad_dias = models.PositiveSmallIntegerField(null=True, blank=True)
    diametro_prom = models.DecimalField(max_digits=7, decimal_places=2, null=True, blank=True)
    longitud_prom = models.DecimalField(max_digits=7, decimal_places=2, null=True, blank=True)
    area = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    relacion_ld = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    factor = models.DecimalField(max_digits=4, decimal_places=2, null=True, blank=True)
    resistencia_mpa = models.DecimalField(max_digits=7, decimal_places=1, null=True, blank=True)
    resistencia_kgcm2 = models.DecimalField(max_digits=8, decimal_places=1, null=True, blank=True)
    porcentaje = models.PositiveIntegerField(null=True, blank=True)
    densidad = models.PositiveIntegerField(null=True, blank=True)

    terminado_en = models.DateTimeField(null=True, blank=True)

    # Revisión del supervisor (HU-LIMS-15).
    observacion_revision = models.TextField(blank=True, default='', verbose_name="Observación del revisor")
    aprobado_por = models.ForeignKey(
        TrabajadorProfile, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='resultados_aprobados',
    )
    aprobado_en = models.DateTimeField(null=True, blank=True)

    creado_en = models.DateTimeField(auto_now_add=True)
    actualizado_en = models.DateTimeField(auto_now=True)

    CAMPOS_MEDIDOS = ['masa_g', 'd1', 'd2', 'l1', 'l2', 'l3', 'carga_kn']
    DEFECTO_OTROS = 'e'
    TIPOS_DEFECTO = [
        ('a', 'Espécimen mal moldeado'),
        ('b', 'Espécimen quiñado'),
        ('c', 'Dimensiones atípicas'),
        ('d', 'Caras irregulares'),
        (DEFECTO_OTROS, 'Otros'),
    ]

    class Meta:
        verbose_name = "Resultado de ensayo"
        verbose_name_plural = "Resultados de ensayo"

    def __str__(self):
        return f"Resultado {self.detalle.muestra.codigo_laboratorio}"

    @classmethod
    def plantilla_para(cls, detalle):
        servicio = getattr(detalle.servicio_cotizado, 'servicio', None)
        codigo = getattr(servicio, 'codigo_facturacion', '') or ''
        return cls.PLANTILLA_COMPRESION if es_ensayo_compresion(detalle.norma, codigo) else cls.PLANTILLA_GENERAL

    @property
    def es_compresion(self):
        return self.plantilla == self.PLANTILLA_COMPRESION

    @property
    def filas_formulario(self):
        """[(grupo, etiqueta, texto)] de lo registrado en el formulario del servicio (revisión e informe)."""
        return formularios_ensayo.filas(self.esquema or {}, self.datos or {})

    @classmethod
    def crear_para(cls, detalle, **extra):
        """Crea el resultado de una línea con la plantilla y el formulario de su servicio."""
        plantilla = extra.pop('plantilla', None) or cls.plantilla_para(detalle)
        esquema = {}
        if plantilla == cls.PLANTILLA_GENERAL:
            formulario = PlantillaFormulario.para_detalle(detalle)
            esquema = formulario.como_esquema() if formulario else {}
        return cls.objects.create(detalle=detalle, plantilla=plantilla, esquema=esquema, **extra)

    @property
    def tipos_foto(self):
        return FotoEnsayo.tipos_de(self.plantilla)

    @property
    def terminado(self):
        return self.estado in self.ESTADOS_CERRADOS

    @property
    def aprobado(self):
        return self.estado == self.ESTADO_APROBADO

    @property
    def lista_defectos(self):
        return [c for c in self.tipos_defecto.split(',') if c in dict(self.TIPOS_DEFECTO)]

    @property
    def defectos_texto(self):
        """«Ninguno», los tipos marcados o, en registros anteriores, el texto libre."""
        etiquetas = dict(self.TIPOS_DEFECTO)
        partes = []
        for c in self.lista_defectos:
            if c == self.DEFECTO_OTROS:
                partes.append(f"{etiquetas[c]}: {self.defectos}" if self.defectos else etiquetas[c])
            else:
                partes.append(f"({c}) {etiquetas[c]}")
        if not partes and self.defectos:
            partes.append(self.defectos)
        return "; ".join(partes) or "Ninguno"

    @property
    def verificacion_diametro(self):
        """(diferencia %, cumple) entre D1 y D2, o None si faltan."""
        from .calculos_compresion import verificar_diametro
        return verificar_diametro(self.d1, self.d2)

    def calcular(self):
        """Resultado de los cálculos con las medidas actuales (o DatosInsuficientes)."""
        from .calculos_compresion import calcular
        muestra = self.detalle.muestra
        return calcular(
            self.d1, self.d2, self.l1, self.l2, self.l3, self.carga_kn,
            masa_g=self.masa_g, fc_kgcm2=muestra.fc_diseno,
        )

    def guardar_resultados(self):
        r = self.calcular()
        muestra = self.detalle.muestra
        self.edad_dias = (
            (self.fecha_ensayo - muestra.fecha_fabricacion).days
            if self.fecha_ensayo and muestra.fecha_fabricacion else None
        )
        self.diametro_prom = r.diametro_prom
        self.longitud_prom = r.longitud_prom
        self.area = r.area
        self.relacion_ld = r.relacion_ld
        self.factor = r.factor
        self.resistencia_mpa = r.resistencia_mpa
        self.resistencia_kgcm2 = r.resistencia_kgcm2
        self.porcentaje = int(r.porcentaje) if r.porcentaje is not None else None
        self.densidad = int(r.densidad) if r.densidad is not None else None

    def tipos_faltantes(self):
        """Códigos de los tipos de foto que aún no se cargaron, en orden.

        En la galería del ensayo general no hay tipos fijos: falta `general`
        mientras haya menos de las fotos mínimas.
        """
        cargados = list(self.fotos.values_list('tipo', flat=True))
        return [codigo for codigo, _ in self.tipos_foto if codigo not in cargados]

    def _fotos_que_faltan(self):
        """Frases de las fotos pendientes: 6 por ensayo (2 antes, 2 durante la carga, 2 después)."""
        etiquetas = dict(FotoEnsayo.TIPOS)
        return [f"la foto «{etiquetas[t]}»" for t in self.tipos_faltantes()]

    def faltantes_para_terminar(self):
        """Lista legible de lo que falta para poder terminar (vacía = listo)."""
        faltan = []
        etiquetas = dict(FotoEnsayo.TIPOS)
        if not self.es_compresion:
            if not self.fecha_ensayo:
                faltan.append("la fecha de ensayo")
            # Formulario FOR-009 completo: solo se exige lo que el servicio defina como obligatorio.
            faltan.extend(f"«{e}»" for e in formularios_ensayo.faltantes(self.esquema or {}, self.datos or {}))
            faltan.extend(self._fotos_que_faltan())
            return faltan
        muestra = self.detalle.muestra
        if not muestra.fecha_fabricacion or not muestra.fc_diseno:
            faltan.append("la fecha de fabricación y el f'c de la probeta (datos FOR-004 de la recepción)")
        if not self.fecha_ensayo:
            faltan.append("la fecha de ensayo")
        etiquetas_campos = {f.name: f.verbose_name for f in self._meta.fields}
        for campo in self.CAMPOS_MEDIDOS:
            if getattr(self, campo) in (None, ''):
                faltan.append(str(etiquetas_campos[campo]))
        if not self.tipo_fractura:
            faltan.append("el tipo de fractura")
        if self.verif_perpendicularidad is None:
            faltan.append("la verificación de perpendicularidad")
        if self.verif_planitud is None:
            faltan.append("la verificación de planitud")
        if self.DEFECTO_OTROS in self.lista_defectos and not self.defectos.strip():
            faltan.append("el detalle del defecto «Otros»")
        faltan += [f"la foto «{etiquetas[t]}»" for t in self.tipos_faltantes()]
        return faltan


class CambioResultado(models.Model):
    """Trazabilidad: cada corrección de un dato ya guardado (valor anterior → nuevo).

    Solo se anota cuando un dato que ya tenía valor cambia, para que el revisor
    vea qué se digitó mal y qué quedó al final. El primer valor no es una
    corrección: es el ``anterior`` del primer cambio o el valor actual.
    """
    resultado = models.ForeignKey(
        'ResultadoEnsayo', on_delete=models.CASCADE, related_name='cambios',
    )
    campo = models.CharField(max_length=40)
    etiqueta = models.CharField(max_length=80)
    anterior = models.CharField(max_length=255, blank=True, default='')
    nuevo = models.CharField(max_length=255, blank=True, default='')
    usuario = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='+')
    registrado_en = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Corrección de resultado"
        verbose_name_plural = "Correcciones de resultados"
        ordering = ['registrado_en', 'pk']

    def __str__(self):
        return f"{self.etiqueta}: {self.anterior} → {self.nuevo}"


class FotoEnsayo(models.Model):
    TIPO_CARGA = 'carga'
    TIPO_DURANTE = 'durante'
    TIPO_ANTES = 'antes'
    TIPO_ANTES_PIZARRA = 'antes_pizarra'
    TIPO_DESPUES = 'despues'
    TIPO_DESPUES_PIZARRA = 'despues_pizarra'
    TIPOS = [
        (TIPO_CARGA, 'Durante el ensayo: lectura del equipo'),
        (TIPO_DURANTE, 'Durante el ensayo'),
        (TIPO_ANTES, 'Antes del ensayo'),
        (TIPO_ANTES_PIZARRA, 'Antes del ensayo, con pizarra'),
        (TIPO_DESPUES, 'Después del ensayo'),
        (TIPO_DESPUES_PIZARRA, 'Después del ensayo, con pizarra'),
        ('general_muestra', 'Muestra o montaje del ensayo'),
        ('general_resultado', 'Resultado o lectura del equipo'),
        ('general', 'Foto del ensayo'),
    ]
    # 2 antes + 2 durante la carga + 2 después (FOR-009: evidencia multimedia).
    TIPOS_COMPRESION = [TIPO_CARGA, TIPO_DURANTE, TIPO_ANTES, TIPO_ANTES_PIZARRA, TIPO_DESPUES, TIPO_DESPUES_PIZARRA]
    # Orden en que se toman en el laboratorio: en la prensa antes de ensayar,
    # el display con la carga de rotura y recién entonces la probeta rota.
    ORDEN_TOMA = [TIPO_ANTES, TIPO_ANTES_PIZARRA, TIPO_DURANTE, TIPO_CARGA, TIPO_DESPUES, TIPO_DESPUES_PIZARRA]
    # Ensayos sin formato propio: galería libre de fotos (`general`), al menos
    # MIN_FOTOS_GENERAL y como mucho MAX_FOTOS_GENERAL. Los dos tipos fijos
    # anteriores solo quedan para fotos ya subidas.
    TIPO_GENERAL = 'general'
    TIPOS_GENERAL = ['general_muestra', 'general_resultado']
    TIPOS_GALERIA = [TIPO_GENERAL, *TIPOS_GENERAL]
    MIN_FOTOS_GENERAL = 1
    MAX_FOTOS_GENERAL = 12
    # Proporción ancho:alto de cada recuadro, medida en el informe real
    # VCF-INF-2026-4582 (FOR-039 v17): carga 111,5 x 43,3 pt; probeta 55,6 x 97,6 pt.
    PROPORCIONES = {
        TIPO_CARGA: (18, 7),
        TIPO_DURANTE: (4, 7),
        TIPO_ANTES: (4, 7),
        TIPO_ANTES_PIZARRA: (4, 7),
        TIPO_DESPUES: (4, 7),
        TIPO_DESPUES_PIZARRA: (4, 7),
        'general_muestra': (4, 3),
        'general_resultado': (4, 3),
        TIPO_GENERAL: None,  # se guarda con su proporción original
    }
    # Lado mayor de la foto guardada, en px.
    LADO_MAXIMO = 1600

    ensayo = models.ForeignKey(ResultadoEnsayo, on_delete=models.CASCADE, related_name='fotos')
    tipo = models.CharField(max_length=20, choices=TIPOS)
    imagen = models.ImageField(
        storage=_almacen_fotos_ensayo,
        upload_to=ruta_foto_ensayo,
        width_field='ancho',
        height_field='alto',
    )
    ancho = models.PositiveIntegerField(default=0)
    alto = models.PositiveIntegerField(default=0)
    subido_por = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    subido_en = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Foto de ensayo"
        verbose_name_plural = "Fotos de ensayo"
        constraints = [
            # Una por tipo, salvo la galería del ensayo general, que admite varias.
            models.UniqueConstraint(fields=['ensayo', 'tipo'], condition=~models.Q(tipo='general'),
                                    name='foto_ensayo_unica_por_tipo'),
        ]

    def __str__(self):
        return f"{self.get_tipo_display()} · {self.ensayo}"

    @classmethod
    def tipos_de(cls, plantilla):
        """(código, etiqueta) de las fotos que pide la plantilla, en orden."""
        # Todo ensayo lleva las mismas 6 fotos (HU-LIMS-36); la galería libre solo queda para fotos ya subidas.
        codigos = cls.TIPOS_COMPRESION
        etiquetas = dict(cls.TIPOS)
        return [(c, etiquetas[c]) for c in codigos]

    @classmethod
    def total_requerido(cls, plantilla):
        """Cuántas fotos pide la plantilla para terminar."""
        return len(cls.TIPOS_COMPRESION)

    @classmethod
    def proporcion(cls, tipo):
        """Ancho/alto del recuadro, o None si la foto conserva la suya."""
        medida = cls.PROPORCIONES[tipo]
        if medida is None:
            return None
        ancho, alto = medida
        return ancho / alto


class BorradorInforme(models.Model):
    """Informe de la solicitud que se redacta en el editor tipo Word (fase 2).

    ``contenido`` es el documento del editor (JSON de TipTap/ProseMirror). Los
    bloques de datos (carátula, resultados, fotos, equipos, firmas) solo guardan
    su tipo y referencia: se dibujan siempre desde lo registrado, así el informe
    no puede contradecir los resultados. Al emitir se congela ``html_emitido``.
    """
    ESTADO_BORRADOR = 'borrador'
    ESTADO_EMITIDO = 'emitido'
    ESTADOS = [(ESTADO_BORRADOR, 'Borrador'), (ESTADO_EMITIDO, 'Emitido')]

    solicitud = models.OneToOneField(SolicitudEnsayo, on_delete=models.CASCADE, related_name='borrador_informe')
    contenido = models.JSONField(default=dict)
    version = models.PositiveIntegerField(default=1)
    estado = models.CharField(max_length=12, choices=ESTADOS, default=ESTADO_BORRADOR)
    html_emitido = models.TextField(blank=True, default='')
    creado_en = models.DateTimeField(auto_now_add=True)
    actualizado_en = models.DateTimeField(auto_now=True)
    actualizado_por = models.ForeignKey(
        TrabajadorProfile, on_delete=models.SET_NULL, null=True, blank=True, related_name='+',
    )

    class Meta:
        verbose_name = "Borrador de informe"
        verbose_name_plural = "Borradores de informe"

    def __str__(self):
        return f"Informe de {self.solicitud.codigo_solicitud}"

    @property
    def emitido(self):
        return self.estado == self.ESTADO_EMITIDO


class VersionInforme(models.Model):
    """Copia del borrador para el historial: quién cambió y cuándo."""
    borrador = models.ForeignKey(BorradorInforme, on_delete=models.CASCADE, related_name='versiones')
    numero = models.PositiveIntegerField()
    contenido = models.JSONField()
    autor = models.ForeignKey(TrabajadorProfile, on_delete=models.SET_NULL, null=True, blank=True, related_name='+')
    nota = models.CharField(max_length=120, blank=True, default='')
    creado_en = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Versión de informe"
        verbose_name_plural = "Versiones de informe"
        ordering = ['-numero']
