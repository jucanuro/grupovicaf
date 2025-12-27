from django.db import models
from django.utils import timezone
from django.db import transaction
from clientes.models import Cliente
from trabajadores.models import TrabajadorProfile 
from servicios.models import Cotizacion, CotizacionDetalle 
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
        
class Laboratorio(models.Model):
    """
    Define las áreas o divisiones de servicio del laboratorio.
    Ej: Mecánica de Suelos, Concreto, Ensayos Químicos.
    """
    nombre = models.CharField(
        max_length=100, 
        unique=True, 
        verbose_name="Nombre del Laboratorio/Área"
    )
    descripcion = models.TextField(
        blank=True, 
        null=True, 
        verbose_name="Descripción del Área"
    )
    
    def __str__(self):
        return self.nombre

    class Meta:
        verbose_name = "Laboratorio/Área"
        verbose_name_plural = "Laboratorios/Áreas"
        ordering = ['nombre']
        
class TipoMuestra(models.Model):
    """
    Define los tipos de muestras que ingresan al laboratorio.
    Se relaciona con el área de Laboratorio y contiene el prefijo
    para la codificación de la Muestra.
    """
    nombre = models.CharField(
        max_length=100, 
        unique=True, 
        verbose_name="Nombre del Tipo de Muestra (Ej: Suelo, Agua)"
    )
    
    tipo_laboratorio = models.ForeignKey(
        'Laboratorio', 
        on_delete=models.SET_NULL, 
        null=True,
        blank=True,
        verbose_name="Área de Laboratorio Asociada"
    )
    
    prefijo_codigo = models.CharField(
        max_length=2, 
        unique=True, 
        verbose_name="Prefijo de Codificación (Ej: S, C, A)"
    )
    
    def __str__(self):
        return f"{self.nombre} ({self.prefijo_codigo}) - Área: {self.tipo_laboratorio.nombre}"

    class Meta:
        verbose_name = "Tipo de Muestra (Catálogo)"
        verbose_name_plural = "Tipos de Muestra (Catálogo)"
        ordering = ['nombre']

class Muestra(models.Model):
    
    ESTADOS_MUESTRA = [
        ('RECIBIDA', 'Recibida en Laboratorio'),
        ('ASIGNADA', 'Técnico Asignado, Pendiente de Órdenes'),
        ('EN_ANALISIS', 'Órdenes de Ensayo Generadas/En Curso'),
        ('RESULTADOS_REGISTRADOS', 'Resultados Registrados (Pendiente de Validación)'),
        ('VALIDADO', 'Validada (Lista para Informe Final)'),
        ('ENTREGADO', 'Muestra Entregada/Dispuesta'),
    ]

    proyecto = models.ForeignKey(
        'proyectos.Proyecto',
        on_delete=models.CASCADE, 
        related_name='muestras', 
        verbose_name="Proyecto Asociado"
    )
    
    id_lab = models.ForeignKey( 
        'proyectos.Laboratorio',
        on_delete=models.CASCADE,
        related_name='muestras',
        verbose_name="Laboratorio Asociado"
    )
    
    codigo_lote_generado = models.CharField(
        max_length=100, 
        blank=True, 
        null=True, 
        verbose_name="Código de Lote (V-TIPO-AÑO)"
    )

    codigo_muestra = models.CharField(
        max_length=100, 
        unique=True, 
        blank=True, 
        verbose_name="Código de Muestra (ID_LAB-TIPO-001)"
    )
    
    descripcion_muestra = models.TextField(
        blank=True, 
        null=True, 
        verbose_name="Descripción o Ubicación de Toma (Cliente)"
    )
    
    tipo_muestra = models.ForeignKey(
        'proyectos.TipoMuestra',
        on_delete=models.RESTRICT,
        related_name='muestras',
        verbose_name="Tipo de Muestra"
    )
    
    masa_aprox_kg = models.DecimalField(
        max_digits=10, 
        decimal_places=3, 
        blank=True, 
        null=True, 
        verbose_name="Masa/Volumen Aprox. (kg/L)"
    )
    
    tomada_por = models.ForeignKey(
        'trabajadores.TrabajadorProfile',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='muestras_tomadas',
        verbose_name="Tomada Por"
    )
    fecha_toma_muestra = models.DateField(
        blank=True, 
        null=True, 
        verbose_name="Fecha Toma (Muestreo)"
    )
    ubicacion_gps = models.CharField(
        max_length=100, 
        blank=True, 
        null=True, 
        verbose_name="Ubicación GPS (Latitud, Longitud)"
    )

    fecha_recepcion = models.DateField(
        default=timezone.now, 
        verbose_name="Fecha de Recepción en Lab"
    )
    recepcionado_por = models.ForeignKey(
        'trabajadores.TrabajadorProfile', 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        related_name='muestras_recepcionadas', 
        verbose_name="Recepcionado Por"
    )
    estado_fisico_recepcion = models.CharField(
        max_length=100, 
        blank=True, 
        null=True, 
        verbose_name="Estado Físico (Recepción/Integridad)"
    )
    ubicacion_almacenamiento = models.CharField(
        max_length=100, 
        blank=True, 
        null=True, 
        verbose_name="Ubicación Muestra (En Almacén)"
    )
    
    fecha_fabricacion = models.DateField(
        blank=True, 
        null=True, 
        verbose_name="Fecha de Fabricación (si aplica)"
    )
    fecha_ensayo_rotura = models.DateField(
        blank=True, 
        null=True, 
        verbose_name="Fecha Prevista de Ensayo de Rotura (si aplica)"
    )
    
    estado = models.CharField(
        max_length=30, 
        choices=ESTADOS_MUESTRA, 
        default='RECIBIDA', 
        verbose_name="Estado de la Muestra"
    )
    tecnico_responsable_muestra = models.ForeignKey(
        'trabajadores.TrabajadorProfile', 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        related_name='muestras_asignadas_principal', 
        verbose_name="Técnico Responsable Principal"
    )
    notas_recepcion = models.TextField(
        blank=True, 
        null=True, 
        verbose_name="Notas de Recepción/Observaciones Internas"
    )
    
    creado_en = models.DateTimeField(auto_now_add=True)
    modificado_en = models.DateTimeField(auto_now=True)
    
    def get_tipo_prefix(self):
        if self.tipo_muestra and self.tipo_muestra.prefijo_codigo:
            return self.tipo_muestra.prefijo_codigo.upper()
        return 'X'
        
    def save(self, *args, **kwargs):
        if not self.pk:
            with transaction.atomic():
                current_year = datetime.datetime.now().year
                
                tipo_prefix = self.get_tipo_prefix()
                
                codigo_lote = f'V-{tipo_prefix}-{current_year}'
                self.codigo_lote_generado = codigo_lote 
                
                lab_pk = self.id_lab.pk if self.id_lab else '0'
                
                prefix_to_search = f'{lab_pk}-{tipo_prefix}-{current_year}-' 
                
                last_muestra = Muestra.objects.filter(
                    codigo_muestra__startswith=prefix_to_search
                ).order_by('-codigo_muestra').first()
                
                next_number = 1
                if last_muestra and last_muestra.codigo_muestra:
                    try:
                        parts = last_muestra.codigo_muestra.split('-')
                        if len(parts) >= 4:
                            last_number_str = parts[-1] 
                            last_number = int(last_number_str)
                            next_number = last_number + 1
                    except ValueError:
                        pass
                    
                consecutive_number = f'{next_number:03d}'
                
                self.codigo_muestra = f'{lab_pk}-{tipo_prefix}-{current_year}-{consecutive_number}'
                
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.codigo_muestra} - {self.tipo_muestra.nombre if self.tipo_muestra else 'Sin Tipo'} (Lote: {self.codigo_lote_generado})"

    class Meta:
        verbose_name = "Muestra de Laboratorio"
        verbose_name_plural = "Muestras de Laboratorio"
        ordering = ['codigo_muestra']

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

class SolicitudEnsayo(models.Model):
    """Representa el documento cabecera (la Solicitud/Orden) de una Muestra."""
    
    muestra = models.OneToOneField( 
        Muestra, 
        on_delete=models.CASCADE, 
        related_name='solicitud_ensayo', 
        verbose_name="Muestra Asociada"
    )
    codigo_solicitud = models.CharField(
        max_length=100, 
        unique=True, 
        verbose_name="Código de Solicitud/Orden",
        blank=True,
        null=True
    ) 
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
        if self.muestra and self.muestra.proyecto:
            return self.muestra.proyecto.cotizacion
        return None
    
    fecha_entrega_programada = models.DateField(blank=True, null=True, verbose_name="Fecha de Entrega de Registros (Programada)")
    fecha_entrega_real = models.DateField(blank=True, null=True, verbose_name="Fecha Real de Entrega de Registros")
    
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

    def save(self, *args, **kwargs):
        if not self.pk and not self.codigo_solicitud:
            now = timezone.now()
            year = str(now.year)
            month = now.strftime('%m')
            prefix = 'SOL'
            sub_code = '0^0-01' 
            
            base_code_pattern = f'{prefix}-{year}-{month}-{sub_code}'
            
            last_solicitud = SolicitudEnsayo.objects.filter(
                codigo_solicitud__startswith=base_code_pattern
            ).order_by('-codigo_solicitud').first()

            sequence = 1
            if last_solicitud:
                try:
                    last_sequence_str = last_solicitud.codigo_solicitud.split('-')[-1]
                    last_sequence = int(last_sequence_str)
                    sequence = last_sequence + 1
                except ValueError:
                    sequence = 1

            sequence_str = str(sequence).zfill(3)
            self.codigo_solicitud = f'{base_code_pattern}-{sequence_str}'

        super().save(*args, **kwargs)

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
    
    norma = models.ForeignKey(
        'servicios.Norma', 
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name="Norma de Ensayo"
    )
    metodo = models.ForeignKey(
        'servicios.Metodo', 
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name="Método de Ensayo"
    )
    
    tipo_ensayo_descripcion = models.CharField(max_length=150, verbose_name="Descripción del Ensayo") 
    
    fecha_limite_ejecucion = models.DateField(verbose_name="Fecha Límite de Ejecución (Entrega Programada)")
    fecha_entrega_real = models.DateField(blank=True, null=True, verbose_name="Fecha de Entrega Real (Técnico)")
    
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


class ResultadoEnsayo(models.Model):
    """
    Cabecera formal del registro de resultados de un ensayo de laboratorio.
    Modelo diseñado para uso profesional (LIMS).
    """

    # 🔗 RELACIONES CLAVE
    detalle_ensayo = models.ForeignKey(
        DetalleEnsayo,
        on_delete=models.CASCADE,
        related_name='resultados',
        verbose_name="Detalle de Ensayo (Tarea)"
    )

    tipo_ensayo = models.ForeignKey(
        TipoEnsayo,
        on_delete=models.PROTECT,
        verbose_name="Tipo de Ensayo Ejecutado"
    )

    # 🧪 NORMA Y MÉTODO (CONFORME A PERÚ / ASTM / NTP)
    norma_aplicada = models.ForeignKey(
        'servicios.Norma',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name="Norma Aplicada"
    )

    metodo_aplicado = models.ForeignKey(
        'servicios.Metodo',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name="Método de Ensayo"
    )

    # 🧑‍🔬 RESPONSABILIDAD TÉCNICA
    tecnico_ejecutor = models.ForeignKey(
        TrabajadorProfile,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='resultados_ejecutados',
        verbose_name="Técnico Ejecutor"
    )

    supervisor_revisor = models.ForeignKey(
        TrabajadorProfile,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='resultados_revisados',
        verbose_name="Supervisor Revisor"
    )

    # 📅 FECHAS CLAVE
    fecha_inicio_ensayo = models.DateField(
        verbose_name="Fecha de Inicio del Ensayo"
    )

    fecha_fin_ensayo = models.DateField(
        blank=True,
        null=True,
        verbose_name="Fecha de Finalización del Ensayo"
    )

    fecha_registro = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Fecha de Registro en el Sistema"
    )

    fecha_revision = models.DateTimeField(
        blank=True,
        null=True,
        verbose_name="Fecha de Revisión / Validación"
    )

    # 🔁 CONTROL DE REENSAYOS
    es_reensayo = models.BooleanField(
        default=False,
        verbose_name="¿Es Reensayo?"
    )

    resultado_origen = models.ForeignKey(
        'self',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='reensayos',
        verbose_name="Resultado Original (si es reensayo)"
    )

    # 📌 ESTADOS DEL RESULTADO (FLUJO REAL DE LABORATORIO)
    ESTADOS_RESULTADO = (
        ('BORRADOR', 'Borrador'),
        ('EN_PROCESO', 'En Proceso'),
        ('COMPLETADO', 'Completado por Técnico'),
        ('VALIDADO', 'Validado por Supervisor'),
        ('APROBADO', 'Aprobado para Informe'),
        ('OBSERVADO', 'Observado'),
        ('ANULADO', 'Anulado'),
    )

    estado = models.CharField(
        max_length=20,
        choices=ESTADOS_RESULTADO,
        default='BORRADOR',
        verbose_name="Estado del Resultado"
    )

    # 📝 OBSERVACIONES
    observaciones_tecnicas = models.TextField(
        blank=True,
        null=True,
        verbose_name="Observaciones Técnicas del Ensayo"
    )

    observaciones_revision = models.TextField(
        blank=True,
        null=True,
        verbose_name="Observaciones de Revisión / Supervisor"
    )

    # 🧾 RESPALDO DE DATOS NO ESTRUCTURADOS
    datos_crudos = models.JSONField(
        blank=True,
        null=True,
        verbose_name="Datos Crudos / Curvas / Registros de Equipo"
    )

    creado_en = models.DateTimeField(auto_now_add=True)
    modificado_en = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Resultado de Ensayo"
        verbose_name_plural = "Resultados de Ensayos"
        unique_together = ('detalle_ensayo', 'tipo_ensayo')
        ordering = ['-fecha_inicio_ensayo']

    def __str__(self):
        return (
            f"Resultado {self.tipo_ensayo.nombre} | "
            f"{self.detalle_ensayo.solicitud.codigo_solicitud}"
        )


class EnsayoParametro(models.Model):
    """
    Catálogo de parámetros medibles por tipo de ensayo.
    Ej: Resistencia, Humedad, Densidad, CBR, etc.
    """

    tipo_ensayo = models.ForeignKey(
        TipoEnsayo,
        on_delete=models.CASCADE,
        related_name='parametros',
        verbose_name="Tipo de Ensayo"
    )

    nombre = models.CharField(
        max_length=100,
        verbose_name="Nombre del Parámetro"
    )

    unidad = models.CharField(
        max_length=30,
        blank=True,
        null=True,
        verbose_name="Unidad (MPa, %, g/cm3, etc.)"
    )

    es_numerico = models.BooleanField(
        default=True,
        verbose_name="¿Valor Numérico?"
    )

    orden = models.PositiveIntegerField(
        default=1,
        verbose_name="Orden de Visualización"
    )

    class Meta:
        verbose_name = "Parámetro de Ensayo"
        verbose_name_plural = "Parámetros de Ensayo"
        ordering = ('orden',)
        unique_together = ('tipo_ensayo', 'nombre')

    def __str__(self):
        return f"{self.nombre} ({self.unidad or '-'})"



class ResultadoEnsayoValor(models.Model):
    """
    Valores obtenidos para cada parámetro del ensayo.
    """

    resultado = models.ForeignKey(
        ResultadoEnsayo,
        on_delete=models.CASCADE,
        related_name='valores',
        verbose_name="Resultado de Ensayo"
    )

    parametro = models.ForeignKey(
        'EnsayoParametro',
        on_delete=models.PROTECT,
        verbose_name="Parámetro Medido"
    )

    valor_numerico = models.DecimalField(
        max_digits=15,
        decimal_places=6,
        null=True,
        blank=True,
        verbose_name="Valor Numérico"
    )

    valor_texto = models.CharField(
        max_length=255,
        blank=True,
        null=True,
        verbose_name="Valor Textual / Cualitativo"
    )

    cumple = models.BooleanField(
        null=True,
        blank=True,
        verbose_name="¿Cumple Especificación?"
    )

    class Meta:
        verbose_name = "Valor del Resultado"
        verbose_name_plural = "Valores de Resultados"
        unique_together = ('resultado', 'parametro')

    def __str__(self):
        return f"{self.parametro.nombre}"



class DocumentoFinal(models.Model):
    proyecto = models.OneToOneField(
        'Proyecto', 
        on_delete=models.CASCADE, 
        related_name='documento_final'
    )
    titulo = models.CharField(max_length=255, default="Informe Técnico Final")
    archivo_pdf = models.FileField(upload_to='informes_finales/%Y/%m/')
    fecha_emision = models.DateField(auto_now_add=True)
    publicado = models.BooleanField(default=False, help_text="Si está marcado, el cliente puede verlo.")

    def __str__(self):
        return f"Informe: {self.proyecto.codigo_proyecto}"