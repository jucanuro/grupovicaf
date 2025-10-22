from django.db import models
from django.utils import timezone
from clientes.models import Cliente
from trabajadores.models import TrabajadorProfile
from servicios.models import Cotizacion, CotizacionDetalle 
import os

# ================================================================
# Funciones de utilidad
# ================================================================
def documento_file_path(instance, filename):
    """Genera la ruta de subida para documentos finales basados en cliente y proyecto."""
    proyecto_id = instance.proyecto.id if instance.proyecto else 'default'
    cliente_id = instance.proyecto.cliente.id if instance.proyecto and instance.proyecto.cliente else 'default'
    return f'proyectos/documentos/{cliente_id}/{proyecto_id}/{filename}'


# ================================================================
# 1. Modelo Principal: Proyecto
# (Se genera al aprobar una Cotización)
# ================================================================
class Proyecto(models.Model):
    """Representa un proyecto de trabajo generado tras la aprobación de una cotización."""
    
    cotizacion = models.ForeignKey(
        Cotizacion, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        verbose_name="Cotización de Origen"
    )
    
    ESTADOS_PROYECTO = [
        ('PENDIENTE', 'Pendiente de Inicio'),
        ('EN_CURSO', 'En Curso'),
        ('MUESTRAS_ASIGNADAS', 'Técnicos de Muestra Asignados'),
        ('MUESTRAS_VALIDADAS', 'Muestras Validadas (Listo para Informe)'),
        ('FINALIZADO', 'Finalizado'),
        ('CANCELADO', 'Cancelado'),
    ]

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
    
    # Campos de seguimiento
    numero_muestras = models.PositiveIntegerField(default=0, verbose_name="Número Total de Muestras (Según Cotización)")
    numero_muestras_registradas = models.PositiveIntegerField(default=0, verbose_name="Número de Muestras con Resultados Finales")

    creado_en = models.DateTimeField(auto_now_add=True)
    modificado_en = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.nombre_proyecto} ({self.codigo_proyecto})"

    class Meta:
        verbose_name = "Proyecto"
        verbose_name_plural = "Proyectos"
        ordering = ['-fecha_inicio']


# ================================================================
# 2. Modelo: Muestra
# (Recepción y Asignación de Técnico Principal)
# ================================================================
class Muestra(models.Model):
    """Representa una muestra física asociada a un proyecto, y lleva el técnico principal asignado."""
    
    ESTADOS_MUESTRA = [
        ('RECIBIDA', 'Recibida en Laboratorio'),
        ('ASIGNADA', 'Técnico Asignado, Pendiente de Órdenes'),
        ('EN_ANALISIS', 'Órdenes de Ensayo Generadas/En Curso'),
        ('RESULTADOS_REGISTRADOS', 'Resultados Registrados (Pendiente de Validación)'),
        ('VALIDADO', 'Validada (Lista para Informe Final)'),
    ]

    proyecto = models.ForeignKey(
        Proyecto, 
        on_delete=models.CASCADE, 
        related_name='muestras', 
        verbose_name="Proyecto Asociado"
    )
    codigo_muestra = models.CharField(max_length=100, verbose_name="Código de Muestra (Cliente)")
    id_lab = models.CharField(max_length=50, blank=True, null=True, verbose_name="ID de Laboratorio (Interno)")
    
    # 🎯 CAMBIO CLAVE: Asignación del Técnico Principal a la Muestra
    tecnico_responsable_muestra = models.ForeignKey(
        TrabajadorProfile, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        related_name='muestras_asignadas', 
        verbose_name="Técnico Responsable de la Muestra"
    )
    
    descripcion_muestra = models.TextField(blank=True, null=True, verbose_name="Descripción o Ubicación de Toma")
    tipo_muestra = models.CharField(max_length=100, blank=True, null=True, verbose_name="Tipo de Muestra")
    masa_aprox_kg = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True, verbose_name="Masa Aprox. (kg)")
    
    # Fechas relevantes
    fecha_recepcion = models.DateField(default=timezone.now, verbose_name="Fecha de Recepción en Lab")
    fecha_fabricacion = models.DateField(blank=True, null=True, verbose_name="Fecha de Fabricación (si aplica)")
    fecha_ensayo_rotura = models.DateField(blank=True, null=True, verbose_name="Fecha Prevista de Ensayo de Rotura (si aplica)")
    
    estado = models.CharField(max_length=30, choices=ESTADOS_MUESTRA, default='RECIBIDA', verbose_name="Estado de la Muestra")
    
    creado_en = models.DateTimeField(auto_now_add=True)
    modificado_en = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f"{self.codigo_muestra} - {self.tipo_muestra}"

    class Meta:
        verbose_name = "Muestra"
        verbose_name_plural = "Muestras"
        unique_together = ('proyecto', 'codigo_muestra')
        ordering = ['codigo_muestra']


# ================================================================
# 3. Modelo: OrdenDeEnsayo
# (Solicitud/Generación de un Ensayo Específico)
# ================================================================
class OrdenDeEnsayo(models.Model):
    """Representa la solicitud o documento de trabajo para realizar un ensayo específico sobre una muestra."""
    
    muestra = models.ForeignKey(
        Muestra, 
        on_delete=models.CASCADE, 
        related_name='ordenes', 
        verbose_name="Muestra a Ensayo"
    )
    # RELACIÓN CLAVE: Vincula la orden al ítem específico de la cotización para trazabilidad
    detalle_cotizacion = models.ForeignKey(
        CotizacionDetalle, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        verbose_name="Detalle de Cotización (Ensayo Solicitado)"
    )

    codigo_orden = models.CharField(max_length=100, unique=True, verbose_name="Código de la Orden (Ej: OE-M-1-E1)")
    tipo_ensayo = models.CharField(max_length=100, verbose_name="Tipo de Ensayo/Parámetro a Medir")
    norma_aplicable = models.CharField(max_length=150, blank=True, null=True, verbose_name="Norma de Ensayo Aplicable")
    
    # El técnico asignado para este ensayo específico (puede ser el mismo que el de la muestra)
    tecnico_asignado = models.ForeignKey(
        TrabajadorProfile, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        related_name='ordenes_ejecutadas', 
        verbose_name="Técnico Ejecutor del Ensayo"
    )
    
    fecha_limite_ejecucion = models.DateField(verbose_name="Fecha Límite de Ejecución")
    
    ESTADOS = (
        ('PENDIENTE', 'Pendiente de Inicio'),
        ('EN_PROCESO', 'En Proceso de Ensayo'),
        ('RESULTADOS_CARGADOS', 'Resultados Cargados (Pendiente de Verificación)'),
        ('FINALIZADA', 'Finalizada y Verificada')
    )
    estado_orden = models.CharField(max_length=50, choices=ESTADOS, default='PENDIENTE', verbose_name="Estado de la Orden")
    
    creado_en = models.DateTimeField(auto_now_add=True)
    modificado_en = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.codigo_orden}: {self.tipo_ensayo} para {self.muestra.codigo_muestra}"

    class Meta:
        verbose_name = "Orden de Ensayo"
        verbose_name_plural = "Órdenes de Ensayo"
        ordering = ['fecha_limite_ejecucion']
        
        
# ================================================================
# 4. Modelo: ResultadoEnsayo
# (Registro y Verificación de Resultados)
# ================================================================
class ResultadoEnsayo(models.Model):
    """Almacena los datos y la verificación de un ensayo realizado."""
    
    # RELACIÓN CLAVE: Un resultado pertenece a una orden de ensayo específica
    orden = models.OneToOneField(
        OrdenDeEnsayo,
        on_delete=models.CASCADE,
        related_name='resultado', # Cambiado de 'resultado_ensayo' a 'resultado' para limpieza
        verbose_name="Orden de Ensayo de Origen"
    )
    
    # Muestra (redundante pero útil para consultas directas)
    muestra = models.ForeignKey(
        Muestra, 
        on_delete=models.CASCADE, 
        related_name='resultados_registrados', 
        verbose_name="Muestra"
    )
    
    tecnico_registro = models.ForeignKey(
        TrabajadorProfile, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        related_name='registros_realizados', 
        verbose_name="Técnico que Registró"
    )
    
    # Resultados almacenados de forma estructurada (JSON) o descriptiva
    resultados_json = models.TextField(
        blank=True, 
        null=True, 
        verbose_name="Resultados del Ensayo (Datos JSON/Texto)"
    ) 
    
    observaciones = models.TextField(blank=True, null=True, verbose_name="Observaciones del Ensayo")
    fecha_realizacion = models.DateField(default=timezone.now, verbose_name="Fecha de Realización/Registro")
    
    # Auditoría y Validación por Supervisor
    verificado_por = models.ForeignKey(
        TrabajadorProfile, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        related_name='resultados_verificados', 
        verbose_name="Verificado por Supervisor"
    )
    fecha_verificacion = models.DateTimeField(blank=True, null=True, verbose_name="Fecha de Verificación")
    es_valido = models.BooleanField(default=False, verbose_name="Resultado Verificado y Válido")

    creado_en = models.DateTimeField(auto_now_add=True)
    modificado_en = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f"Resultado de {self.orden.codigo_orden} - Válido: {self.es_valido}"

    class Meta:
        verbose_name = "Resultado de Ensayo"
        verbose_name_plural = "Resultados de Ensayos"
        ordering = ['-fecha_realizacion']


# ================================================================
# 5. Modelo: DocumentoFinal
# (Informe/Validación Final del Proyecto)
# ================================================================
class DocumentoFinal(models.Model):
    """Representa el informe o documento final de un proyecto."""
    
    proyecto = models.OneToOneField(
        Proyecto, 
        on_delete=models.CASCADE, 
        related_name='documento_final', 
        verbose_name="Proyecto Asociado"
    )
    titulo = models.CharField(max_length=255, verbose_name="Título del Documento (Ej: Informe Técnico Final)")
    
    # Archivo original (PDF o generado)
    archivo_original = models.FileField(
        upload_to=documento_file_path,
        blank=True,
        null=True,
        verbose_name="Archivo del Informe Final (PDF)"
    )
    
    # Contenido generado (o asistido) por IA
    resumen_ejecutivo_ia = models.TextField(blank=True, null=True, verbose_name="Resumen Ejecutivo (IA)")
    analisis_detallado_ia = models.TextField(blank=True, null=True, verbose_name="Análisis Detallado de Resultados (IA)")
    recomendaciones_ia = models.TextField(blank=True, null=True, verbose_name="Recomendaciones (IA)")
    
    # Firmas
    firma_supervisor = models.ImageField(upload_to='firmas/', blank=True, null=True, verbose_name="Firma del Jefe/Supervisor de Laboratorio")
    firma_cliente = models.ImageField(upload_to='firmas_clientes/', blank=True, null=True, verbose_name="Firma de Conformidad del Cliente")
    
    fecha_emision = models.DateField(default=timezone.now, verbose_name="Fecha de Emisión del Informe")
    
    creado_en = models.DateTimeField(auto_now_add=True)
    modificado_en = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f"Informe Final de {self.proyecto.codigo_proyecto}: {self.titulo}"

    class Meta:
        verbose_name = "Documento Final"
        verbose_name_plural = "Documentos Finales"
        ordering = ['-fecha_emision']