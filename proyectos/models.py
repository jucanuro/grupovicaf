from django.db import models
import uuid
import qrcode
from io import BytesIO
from django.core.files import File
from django.conf import settings
from django.contrib.auth.models import User
from django.utils.timezone import now
from django.utils import timezone
import io
from django.core.files.base import ContentFile
from pypdf import PdfReader, PdfWriter
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter
from django.db import transaction
from django.core.validators import MinValueValidator
from clientes.models import Cliente
from trabajadores.models import TrabajadorProfile 
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
    
class MuestraDetalle(models.Model):
    recepcion = models.ForeignKey(RecepcionMuestra, related_name='muestras', on_delete=models.CASCADE)
    tipo_muestra = models.ForeignKey(TipoMuestra, on_delete=models.PROTECT)
    
    nro_item = models.IntegerField(default=1) 
    
    descripcion = models.CharField(max_length=255) 
    masa_aprox = models.DecimalField(max_digits=10, decimal_places=2)
    cantidad = models.IntegerField(default=1)
    unidad = models.CharField(max_length=50, default='UND')
    observaciones = models.TextField(null=True, blank=True) 
    
    codigo_laboratorio = models.CharField(max_length=50, unique=True, blank=True)

    def save(self, *args, **kwargs):
        if not self.codigo_laboratorio:
            anio = timezone.now().year
            sigla = self.tipo_muestra.sigla
            
            ultimo = MuestraDetalle.objects.filter(
                codigo_laboratorio__startswith=f"V-M-{anio}-{sigla}-"
            ).order_by('codigo_laboratorio').last()

            if ultimo:
                ultimo_nro = int(ultimo.codigo_laboratorio.split('-')[-1]) + 1
            else:
                ultimo_nro = 1
                
            self.codigo_laboratorio = f"V-M-{anio}-{sigla}-{ultimo_nro:04d}"
        super().save(*args, **kwargs)
              
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

    class Meta:
        verbose_name = "Informe Final"
        verbose_name_plural = "Informes Finales"

    def save(self, *args, **kwargs):
        if not self.codigo_informe:
            anio = now().year
            ultimo = InformeFinal.objects.filter(fecha_emision__year=anio).count()
            self.codigo_informe = f"INF-{anio}-{(ultimo + 1):04d}"
        
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