from django.db import models
from django.utils import timezone
from django.contrib.auth.models import User

from clientes.models import Cliente
from trabajadores.models import TrabajadorProfile
from proyectos.models import Proyecto, RecepcionMuestra, SolicitudEnsayo, InformeFinal


class CalendarioCategoria(models.Model):
    nombre = models.CharField(max_length=100, unique=True)
    color = models.CharField(max_length=20, default='#2563eb')
    icono = models.CharField(max_length=50, blank=True, null=True)
    activo = models.BooleanField(default=True)

    class Meta:
        verbose_name = "Categoría de Calendario"
        verbose_name_plural = "Categorías de Calendario"
        ordering = ['nombre']

    def __str__(self):
        return self.nombre
       
class CalendarioActividad(models.Model):
    TIPO_ACTIVIDAD = [
        ('MANUAL', 'Manual'),
        ('SISTEMA', 'Generada por el sistema'),
    ]

    CLASE_ACTIVIDAD = [
        ('REUNION', 'Reunión'),
        ('LLAMADA', 'Llamada'),
        ('VISITA', 'Visita'),
        ('RECEPCION', 'Recepción de Muestras'),
        ('ENSAYO', 'Ensayo'),
        ('ENTREGA', 'Entrega'),
        ('INFORME', 'Informe'),
        ('SEGUIMIENTO', 'Seguimiento'),
        ('MANTENIMIENTO', 'Mantenimiento'),
        ('CAPACITACION', 'Capacitación'),
        ('AUDITORIA', 'Auditoría'),
        ('INTERNO', 'Actividad Interna'),
        ('BLOQUEO', 'Bloqueo de Agenda'),
        ('OTRO', 'Otro'),
    ]

    ESTADO_ACTIVIDAD = [
        ('PROGRAMADA', 'Programada'),
        ('EN_CURSO', 'En Curso'),
        ('COMPLETADA', 'Completada'),
        ('CANCELADA', 'Cancelada'),
        ('REPROGRAMADA', 'Reprogramada'),
        ('VENCIDA', 'Vencida'),
    ]

    PRIORIDAD = [
        ('BAJA', 'Baja'),
        ('MEDIA', 'Media'),
        ('ALTA', 'Alta'),
        ('URGENTE', 'Urgente'),
    ]

    titulo = models.CharField(max_length=255, verbose_name="Título")
    descripcion = models.TextField(blank=True, null=True, verbose_name="Descripción")

    tipo = models.CharField(
        max_length=20,
        choices=TIPO_ACTIVIDAD,
        default='MANUAL',
        verbose_name="Origen"
    )

    clase = models.CharField(
        max_length=20,
        choices=CLASE_ACTIVIDAD,
        default='OTRO',
        verbose_name="Clase de actividad"
    )

    estado = models.CharField(
        max_length=20,
        choices=ESTADO_ACTIVIDAD,
        default='PROGRAMADA',
        verbose_name="Estado"
    )

    prioridad = models.CharField(
        max_length=10,
        choices=PRIORIDAD,
        default='MEDIA',
        verbose_name="Prioridad"
    )

    categoria = models.ForeignKey(
        CalendarioCategoria,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='actividades',
        verbose_name="Categoría"
    )

    fecha_inicio = models.DateTimeField(verbose_name="Inicio")
    fecha_fin = models.DateTimeField(verbose_name="Fin")

    todo_el_dia = models.BooleanField(default=False, verbose_name="Todo el día")
    bloquea_agenda = models.BooleanField(default=False, verbose_name="Bloquea agenda")
    es_visible = models.BooleanField(default=True, verbose_name="Visible")
    es_automatica = models.BooleanField(default=False, verbose_name="Automática")
    permite_edicion_manual = models.BooleanField(default=True, verbose_name="Permite edición manual")

    ubicacion = models.CharField(max_length=255, blank=True, null=True, verbose_name="Ubicación")
    enlace_externo = models.URLField(blank=True, null=True, verbose_name="Enlace externo")
    observaciones = models.TextField(blank=True, null=True, verbose_name="Observaciones internas")

    cliente = models.ForeignKey(
        Cliente,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='actividades_calendario',
        verbose_name="Cliente"
    )

    cliente_nombre_manual = models.CharField(
        max_length=255,
        blank=True,
        null=True,
        verbose_name="Cliente manual"
    )

    proyecto = models.ForeignKey(
        Proyecto,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='actividades_calendario',
        verbose_name="Proyecto"
    )

    recepcion = models.ForeignKey(
        RecepcionMuestra,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='actividades_calendario',
        verbose_name="Recepción"
    )

    solicitud_ensayo = models.ForeignKey(
        SolicitudEnsayo,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='actividades_calendario',
        verbose_name="Solicitud de ensayo"
    )

    informe_final = models.ForeignKey(
        InformeFinal,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='actividades_calendario',
        verbose_name="Informe final"
    )

    creado_por = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        related_name='actividades_calendario_creadas',
        verbose_name="Creado por"
    )

    actualizado_por = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='actividades_calendario_actualizadas',
        verbose_name="Actualizado por"
    )

    fecha_completada = models.DateTimeField(null=True, blank=True, verbose_name="Fecha completada")
    fecha_cancelada = models.DateTimeField(null=True, blank=True, verbose_name="Fecha cancelada")

    origen_modelo = models.CharField(max_length=50, blank=True, null=True, verbose_name="Origen del sistema")
    origen_id = models.PositiveIntegerField(blank=True, null=True, verbose_name="ID de origen")

    creada_en = models.DateTimeField(auto_now_add=True)
    actualizada_en = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Actividad de Calendario"
        verbose_name_plural = "Actividades de Calendario"
        ordering = ['fecha_inicio']
        indexes = [
            models.Index(fields=['fecha_inicio']),
            models.Index(fields=['fecha_fin']),
            models.Index(fields=['estado']),
            models.Index(fields=['tipo']),
            models.Index(fields=['clase']),
            models.Index(fields=['prioridad']),
            models.Index(fields=['proyecto']),
            models.Index(fields=['solicitud_ensayo']),
        ]

    def __str__(self):
        return f"{self.titulo} ({self.fecha_inicio:%Y-%m-%d %H:%M})"

    @property
    def esta_vencida(self):
        return self.estado not in ['COMPLETADA', 'CANCELADA'] and self.fecha_fin < timezone.now()

    @property
    def duracion_minutos(self):
        return int((self.fecha_fin - self.fecha_inicio).total_seconds() / 60)

    @property
    def color_visual(self):
        if self.categoria and self.categoria.color:
            return self.categoria.color

        colores = {
            'REUNION': '#2563eb',
            'LLAMADA': '#0891b2',
            'VISITA': '#7c3aed',
            'RECEPCION': '#0ea5e9',
            'ENSAYO': '#f59e0b',
            'ENTREGA': '#ef4444',
            'INFORME': '#10b981',
            'SEGUIMIENTO': '#6366f1',
            'MANTENIMIENTO': '#64748b',
            'CAPACITACION': '#9333ea',
            'AUDITORIA': '#b45309',
            'INTERNO': '#475569',
            'BLOQUEO': '#dc2626',
            'OTRO': '#334155',
        }
        return colores.get(self.clase, '#334155')

    def save(self, *args, **kwargs):
        if self.fecha_fin < self.fecha_inicio:
            raise ValueError("La fecha_fin no puede ser menor que fecha_inicio.")

        if self.estado == 'COMPLETADA' and not self.fecha_completada:
            self.fecha_completada = timezone.now()

        if self.estado == 'CANCELADA' and not self.fecha_cancelada:
            self.fecha_cancelada = timezone.now()

        super().save(*args, **kwargs)
        
class CalendarioParticipante(models.Model):
    ROL_PARTICIPANTE = [
        ('RESPONSABLE', 'Responsable'),
        ('APOYO', 'Apoyo'),
        ('INVITADO', 'Invitado'),
        ('SUPERVISOR', 'Supervisor'),
    ]

    actividad = models.ForeignKey(
        CalendarioActividad,
        on_delete=models.CASCADE,
        related_name='participantes'
    )

    trabajador = models.ForeignKey(
        TrabajadorProfile,
        on_delete=models.CASCADE,
        related_name='participaciones_calendario'
    )

    rol = models.CharField(
        max_length=20,
        choices=ROL_PARTICIPANTE,
        default='RESPONSABLE'
    )

    confirmado = models.BooleanField(default=False)
    comentario = models.CharField(max_length=255, blank=True, null=True)

    class Meta:
        verbose_name = "Participante de Actividad"
        verbose_name_plural = "Participantes de Actividades"
        unique_together = ('actividad', 'trabajador')

    def __str__(self):
        return f"{self.trabajador} - {self.actividad.titulo}"
       
class CalendarioRecordatorio(models.Model):
    TIPO_RECORDATORIO = [
        ('APP', 'Notificación interna'),
        ('EMAIL', 'Correo'),
    ]

    actividad = models.ForeignKey(
        CalendarioActividad,
        on_delete=models.CASCADE,
        related_name='recordatorios'
    )

    minutos_antes = models.PositiveIntegerField(verbose_name="Minutos antes")
    tipo = models.CharField(
        max_length=20,
        choices=TIPO_RECORDATORIO,
        default='APP'
    )

    enviado = models.BooleanField(default=False)
    fecha_envio = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = "Recordatorio de Actividad"
        verbose_name_plural = "Recordatorios de Actividades"
        ordering = ['minutos_antes']

    def __str__(self):
        return f"{self.actividad.titulo} - {self.minutos_antes} min"