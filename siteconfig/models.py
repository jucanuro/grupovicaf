import re
from datetime import time

from django.db import models
from django.utils import timezone


class NegocioConfig(models.Model):
    """Datos NAP y de negocio para JSON-LD y footer del sitio público.

    Fuente única: cualquier plantilla que muestre nombre, dirección, teléfono
    u horario debe leerlo de aquí (vía el context processor
    ``siteconfig.context_processors.negocio``), nunca hardcodeado.
    Singleton: se espera una sola fila (pk=1).
    """

    nombre = models.CharField(max_length=150, default='Grupo VICAF SAC')
    ruc = models.CharField(
        max_length=11, blank=True,
        help_text='RUC de la propia empresa (dato público, no confundir con clientes.Cliente.ruc). '
                   'Se muestra en la barra inferior del footer.',
    )
    descripcion = models.CharField(max_length=300)

    direccion_calle = models.CharField(max_length=200)
    direccion_localidad = models.CharField(max_length=100, default='Cajamarca')
    direccion_region = models.CharField(max_length=100, default='Cajamarca')
    direccion_codigo_postal = models.CharField(max_length=20, blank=True)
    direccion_pais = models.CharField(max_length=2, default='PE')

    telefono = models.CharField(max_length=20)
    whatsapp = models.CharField(max_length=20, blank=True)
    correo = models.EmailField(default='informes@grupovicaf.com')

    latitud = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    longitud = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)

    horario_semana_apertura = models.TimeField(null=True, blank=True)
    horario_semana_cierre = models.TimeField(null=True, blank=True)
    # Receso de mediodía de lunes a viernes (ej. 13:00-15:00). Vacío = horario corrido.
    horario_semana_receso_inicio = models.TimeField(null=True, blank=True)
    horario_semana_receso_fin = models.TimeField(null=True, blank=True)
    horario_sabado_apertura = models.TimeField(null=True, blank=True)
    horario_sabado_cierre = models.TimeField(null=True, blank=True)

    ciudades_cobertura = models.JSONField(default=list, blank=True)

    acreditacion_entidad = models.CharField(max_length=100, default='INACAL')
    acreditacion_codigo = models.CharField(max_length=50, default='LE-230')
    # Override manual de la métrica "Ensayos acreditados" de la home. Existe
    # porque hoy el conteo automático no es confiable: Servicio.esta_acreditado
    # está mal poblado en el LIMS (96 de 99 servicios marcados), pendiente de
    # depurar con el cliente contra el alcance oficial de INACAL. Una vez
    # depurado, basta con vaciar este campo para volver al conteo automático
    # (web_inicio.views._metricas_credibilidad).
    ensayos_acreditados = models.PositiveIntegerField(
        null=True, blank=True,
        verbose_name='Ensayos acreditados (número oficial)',
        help_text='Número según el alcance de acreditación INACAL. Si se deja vacío, '
                  'se calcula desde Servicio.esta_acreditado.',
    )

    linkedin_url = models.URLField(blank=True)
    facebook_url = models.URLField(blank=True)
    instagram_url = models.URLField(blank=True)

    class Meta:
        verbose_name = 'Configuración del negocio'
        verbose_name_plural = 'Configuración del negocio'

    def __str__(self):
        return self.nombre

    @property
    def whatsapp_digitos(self):
        """Número de WhatsApp solo con dígitos, como lo exige wa.me."""
        return re.sub(r'\D', '', self.whatsapp or '')

    def _tiene_receso(self):
        return bool(self.horario_semana_receso_inicio and self.horario_semana_receso_fin)

    def tramos_semana(self):
        """Tramos (apertura, cierre) de lunes a viernes, partidos por el receso si existe."""
        if not (self.horario_semana_apertura and self.horario_semana_cierre):
            return []
        if self._tiene_receso():
            return [
                (self.horario_semana_apertura, self.horario_semana_receso_inicio),
                (self.horario_semana_receso_fin, self.horario_semana_cierre),
            ]
        return [(self.horario_semana_apertura, self.horario_semana_cierre)]

    def tramos_sabado(self):
        if not (self.horario_sabado_apertura and self.horario_sabado_cierre):
            return []
        return [(self.horario_sabado_apertura, self.horario_sabado_cierre)]

    @property
    def horario_semana_rango(self):
        """Ej. "08:00–13:00 y 15:00–18:00", para mostrar en plantillas."""
        return ' y '.join(f"{a:%H:%M}–{c:%H:%M}" for a, c in self.tramos_semana())

    def horario_texto(self):
        """Horario en lenguaje natural para el asistente de WhatsApp (aviso T-40)."""
        def rango(tramos):
            return ' y '.join(f"de {_hora(a)} a {_hora(c)}" for a, c in tramos)

        partes = []
        if self.tramos_semana():
            partes.append(f"lunes a viernes {rango(self.tramos_semana())}")
        if self.tramos_sabado():
            partes.append(f"sábados {rango(self.tramos_sabado())}")
        return ', '.join(partes)

    def esta_abierto(self, momento=None):
        """True si `momento` (por defecto, ahora) cae dentro del horario de atención,
        en hora de Lima (TIME_ZONE). El domingo siempre está cerrado."""
        momento = timezone.localtime(momento or timezone.now())
        dia = momento.weekday()
        if dia < 5:
            tramos = self.tramos_semana()
        elif dia == 5:
            tramos = self.tramos_sabado()
        else:
            tramos = []
        hora = momento.time()
        return any(apertura <= hora < cierre for apertura, cierre in tramos)

    def save(self, *args, **kwargs):
        self.pk = 1
        super().save(*args, **kwargs)


def _hora(valor: time) -> str:
    """08:00 -> "8:00" (formato de los textos aprobados del asistente)."""
    return f"{valor.hour}:{valor.minute:02d}"
