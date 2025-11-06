from django.db import models
from django.utils import timezone
from clientes.models import Cliente
from trabajadores.models import TrabajadorProfile # Importación clave
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
# 1. Modelo Principal: Proyecto (SIN CAMBIOS)
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
# 2. Modelo: Muestra (SIN CAMBIOS)
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
    
    # 🎯 CAMBIO CLAVE: Asignación del Técnico Principal a la Muestra (Mantenido)
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
# 3. NUEVO MODELO: TipoEnsayo (CATÁLOGO)
# ================================================================
class TipoEnsayo(models.Model):
    """
    Define los tipos de ensayos predefinidos del laboratorio (el catálogo). 
    """
    nombre = models.CharField(max_length=100, unique=True, verbose_name="Nombre del Ensayo (Catálogo)")
    descripcion = models.TextField(blank=True, null=True, verbose_name="Descripción Detallada")
    codigo_interno = models.CharField(max_length=20, unique=True, blank=True, null=True, verbose_name="Código Interno")

    class Meta:
        verbose_name = "Tipo de Ensayo"
        verbose_name_plural = "Tipos de Ensayos"
        ordering = ['nombre']

    def __str__(self):
        return self.nombre


# ================================================================
# 4. NUEVO MODELO: SolicitudEnsayo (CABECERA)
# ================================================================
class SolicitudEnsayo(models.Model):
    """Representa el documento cabecera (la Solicitud/Orden) de una Muestra."""
    
    muestra = models.OneToOneField( 
        'Muestra', 
        on_delete=models.CASCADE, 
        related_name='solicitud_ensayo', 
        verbose_name="Muestra Asociada"
    )
    codigo_solicitud = models.CharField(max_length=100, unique=True, verbose_name="Código de Solicitud/Orden") 
    fecha_solicitud = models.DateField(default=timezone.now, verbose_name="Fecha de Generación de la Solicitud")
    
    generada_por = models.ForeignKey(
        TrabajadorProfile, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        related_name='solicitudes_generadas', 
        verbose_name="Persona que Elabora la Solicitud"
    )
    
    @property
    def cotizacion(self):
        """Retorna la cotización del proyecto asociado a la muestra."""
        if self.muestra and self.muestra.proyecto:
            return self.muestra.proyecto.cotizacion
        return None
    
    # 2. Fechas de Entrega
    fecha_entrega_programada = models.DateField(blank=True, null=True, verbose_name="Fecha de Entrega de Registros (Programada)")
    fecha_entrega_real = models.DateField(blank=True, null=True, verbose_name="Fecha Real de Entrega de Registros")
    
    # 3. Firmas
    # **NOTA:** La firma del Jefe de Laboratorio se manejaría como un campo de imagen o un proceso de estado.
    # Por ahora, solo indicamos quién debe firmar/validar la solicitud.
    firma_jefe_laboratorio = models.ForeignKey(
        TrabajadorProfile, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        related_name='solicitudes_firmadas', 
        verbose_name="Jefe de Laboratorio que Firma"
    )
    
    ESTADOS_SOLICITUD = (
        ('ASIGNADA', 'Técnicos Asignados'),
        ('EN_ANALISIS', 'En Curso'),
        ('COMPLETADA', 'Todos los Ensayos Finalizados'),
        ('CERRADA', 'Cerrada con Informe')
    )
    estado = models.CharField(max_length=30, choices=ESTADOS_SOLICITUD, default='ASIGNADA', verbose_name="Estado de la Solicitud")

    creado_en = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return f"Solicitud {self.codigo_solicitud} para {self.muestra.codigo_muestra}"

    class Meta:
        verbose_name = "Solicitud de Ensayo (Cabecera)"
        verbose_name_plural = "Solicitudes de Ensayo (Cabeceras)"   
# ================================================================
# 5. NUEVO MODELO: AsignacionTipoEnsayo (TABLA INTERMEDIA CRÍTICA)
# ================================================================
class AsignacionTipoEnsayo(models.Model):
    """
    Tabla intermedia que conecta DetalleEnsayo (la tarea) con TipoEnsayo (el catálogo) 
    y asigna un técnico específico a ESA combinación.
    """
    detalle = models.ForeignKey(
        'DetalleEnsayo', 
        on_delete=models.CASCADE, 
        related_name='asignaciones', 
        verbose_name="Tarea de Detalle"
    )
    tipo_ensayo = models.ForeignKey(
        TipoEnsayo, 
        on_delete=models.PROTECT, 
        related_name='asignaciones_tecnicos',
        verbose_name="Tipo de Ensayo a Ejecutar"
    )
    
    # 🎯 CLAVE: ASIGNACIÓN DEL TÉCNICO AL TIPO DE ENSAYO
    tecnico_asignado = models.ForeignKey(
        TrabajadorProfile, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        related_name='tipos_ensayos_asignados', 
        verbose_name="Técnico (Supervisor) Asignado"
    )
    
    class Meta:
        verbose_name = "Asignación de Ensayo a Técnico"
        verbose_name_plural = "Asignaciones de Ensayos a Técnicos"
        unique_together = ('detalle', 'tipo_ensayo') 

    def __str__(self):
        # Asume que TrabajadorProfile tiene un campo 'user' o un campo de identificación
        tecnico_info = self.tecnico_asignado.user.username if self.tecnico_asignado and hasattr(self.tecnico_asignado, 'user') else 'N/A'
        return f"{self.tipo_ensayo.nombre} asignado a {tecnico_info}"


# ================================================================
# 6. MODELO: DetalleEnsayo (LÍNEA DE TRABAJO/TAREA)
# 🎯 MODIFICACIÓN: Se elimina tecnico_asignado directo y se añade el 'through'
# ================================================================
class DetalleEnsayo(models.Model):
    """Representa una línea de trabajo individual dentro de una Solicitud (el tipo de ensayo a realizar)."""
    
    solicitud = models.ForeignKey(
        SolicitudEnsayo, 
        on_delete=models.CASCADE, 
        related_name='detalles_ensayo', 
        verbose_name="Solicitud de Ensayo de Origen"
    )
    
    tipos_ensayo = models.ManyToManyField(
        'TipoEnsayo', # O 'TipoEnsayoCatalogo' si lo tienes en 'servicios'
        through='AsignacionTipoEnsayo', 
        related_name='detalles_con_asignacion',
        verbose_name="Tipos de Ensayos Asignados"
    )
    
    # 🌟 CAMBIO: Las Normas y Métodos deben ser Catálogos si ya existen
    # Asumo que tienes modelos 'NormaEnsayo' y 'MetodoEnsayo' en tu app 'servicios'.
    norma = models.ForeignKey(
        'servicios.Norma', # Asegúrate de que este 'servicios.NormaEnsayo' sea correcto
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name="Norma de Ensayo"
    )
    metodo = models.ForeignKey(
        'servicios.Metodo', # Asegúrate de que este 'servicios.MetodoEnsayo' sea correcto
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name="Método de Ensayo"
    )
    
    # Se deja la descripción por si se requiere un texto libre adicional al catálogo
    tipo_ensayo_descripcion = models.CharField(max_length=150, verbose_name="Descripción del Ensayo") 
    
    fecha_limite_ejecucion = models.DateField(verbose_name="Fecha Límite de Ejecución (Entrega Programada)")
    fecha_entrega_real = models.DateField(blank=True, null=True, verbose_name="Fecha de Entrega Real (Técnico)")
    
    # Firma del Técnico
    firma_tecnico = models.ForeignKey(
        TrabajadorProfile, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        related_name='detalles_firmados', 
        verbose_name="Firma del Técnico (Completado)"
    )
    detalle_cotizacion = models.ForeignKey(
        CotizacionDetalle, 
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name="Detalle de Cotización de Origen"
    )
    
    # Definición de Estados
    ESTADOS_DETALLE = (
        ('PENDIENTE', 'Pendiente de Asignación'),
        ('ASIGNADO', 'Asignado a Técnico'),
        ('EN_EJECUCION', 'En Ejecución'),
        ('COMPLETADO', 'Completado por Técnico'),
        ('VALIDADO', 'Validado por Supervisor'),
    )
    
    # 🎯 CORRECCIÓN 2: Añadir campo de estado (para E108 y E116)
    estado_detalle = models.CharField(
        max_length=20, 
        choices=ESTADOS_DETALLE, 
        default='PENDIENTE', 
        verbose_name="Estado del Detalle de Ensayo"
    )
    observaciones_detalle = models.TextField(blank=True, null=True, verbose_name="Observaciones de la Tarea/Ensayo")
    
    # ... (estado_detalle y campos de tiempo mantenidos)
    
    def __str__(self):
        return f"Detalle de {self.solicitud.codigo_solicitud}: {self.tipo_ensayo_descripcion}"

    class Meta:
        verbose_name = "Detalle de Ensayo (Línea de Trabajo)"
        verbose_name_plural = "Detalles de Ensayos (Líneas de Trabajo)"
        




class ReporteIncidencia(models.Model):
    """Registra cualquier incidencia o cambio en la Solicitud de Ensayo."""

    solicitud = models.ForeignKey(
        SolicitudEnsayo,
        on_delete=models.CASCADE,
        related_name='incidencias',
        verbose_name="Solicitud de Ensayo Asociada"
    )
    
    TIPOS_INCIDENCIA = (
        ('CAMBIO', 'Cambio en Solicitud/Alcance'),
        ('ANULACION', 'Anulación de Ensayo/Detalle'),
        ('INCREMENTO', 'Incremento de Ensayos'),
        ('OTRO', 'Otro')
    )
    tipo_incidencia = models.CharField(max_length=20, choices=TIPOS_INCIDENCIA, default='OTRO', verbose_name="Tipo de Incidencia")
    
    detalle_incidencia = models.TextField(verbose_name="Detalle de la Incidencia")
    fecha_ocurrencia = models.DateField(default=timezone.now, verbose_name="Fecha de Ocurrencia")
    
    # Responsables y Firmas
    representante_cliente = models.CharField(max_length=150, verbose_name="Representante del Cliente (Nombre/Firma)")
    responsable_laboratorio = models.ForeignKey(
        TrabajadorProfile, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        related_name='incidencias_registradas', 
        verbose_name="Responsable del Laboratorio (Jefe/Supervisor)"
    )
    
    # **NOTA:** La gestión de la firma como archivo de imagen se haría aparte si es necesario.
    # Por ahora, el campo FK al TrabajadorProfile es suficiente para la trazabilidad.
    
    creado_en = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return f"Incidencia {self.id} en {self.solicitud.codigo_solicitud} - Tipo: {self.get_tipo_incidencia_display()}"

    class Meta:
        verbose_name = "Reporte de Incidencia"
        verbose_name_plural = "Reportes de Incidencias"
        ordering = ['-fecha_ocurrencia']
# ================================================================
# 7. MODELO MODIFICADO: ResultadoEnsayo 
# 🎯 MODIFICACIÓN: Se quita la FK a Muestra (ya está en DetalleEnsayo)
# ================================================================
class ResultadoEnsayo(models.Model):
    """Almacena los datos y la verificación de un ensayo realizado."""
    
    # CLAVE: Apunta al DetalleEnsayo (la tarea individual que ahora incluye el tipo de ensayo y el técnico)
    detalle_ensayo = models.OneToOneField(
        DetalleEnsayo,
        on_delete=models.CASCADE,
        related_name='resultado', 
        verbose_name="Detalle de Ensayo de Origen"
    )
    

    tecnico_registro = models.ForeignKey(
        TrabajadorProfile, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        related_name='registros_realizados', 
        verbose_name="Técnico que Registró"
    )
    
    # Resultados almacenados de forma estructurada
    resultados_data = models.JSONField(
        blank=True, 
        null=True, 
        verbose_name="Resultados del Ensayo (Datos Estructurados)"
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
        return f"Resultado de {self.detalle_ensayo.solicitud.codigo_solicitud} - Válido: {self.es_valido}"

    class Meta:
        verbose_name = "Resultado de Ensayo"
        verbose_name_plural = "Resultados de Ensayos"
        ordering = ['-fecha_realizacion']


# ================================================================
# 8. Modelo: DocumentoFinal (SIN CAMBIOS)
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