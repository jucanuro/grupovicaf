from django.conf import settings
from django.db import models


class VistaAnalisis(models.Model):
    """Configuración guardada de la tabla dinámica (HU-LIMS-08, DP-LIMS-11 A).

    Solo guarda la disposición (filas, columnas, cálculo, filtros), nunca datos:
    al abrirla se vuelven a pedir al servidor con los permisos del momento.
    """

    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='vistas_analisis',
    )
    nombre = models.CharField(max_length=80)
    conjunto = models.CharField(max_length=40)
    configuracion = models.JSONField(default=dict)
    creada_en = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Vista de análisis'
        verbose_name_plural = 'Vistas de análisis'
        ordering = ['nombre']
        constraints = [
            models.UniqueConstraint(fields=['usuario', 'conjunto', 'nombre'], name='vista_analisis_unica'),
        ]

    def __str__(self):
        return f'{self.nombre} ({self.conjunto})'
