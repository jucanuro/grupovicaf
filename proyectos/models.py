from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
from django.db import transaction
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