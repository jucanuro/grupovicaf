from django.db import models
from django.conf import settings
from django.urls import reverse # Importar reverse para usar en get_absolute_url
from django.utils import timezone

class Cliente(models.Model):
    """
    Modelo principal para almacenar la información de las empresas/clientes.
    La información de contacto es esencial para la documentación (Oferta, Orden de Ensayo).
    """

    # --- Identificación Principal de la Empresa ---
    ruc = models.CharField(
        max_length=11, 
        unique=True, 
        verbose_name="RUC (N° de Identificación Tributaria)",
        help_text="Número de RUC de 11 dígitos. Debe ser único."
    )
    razon_social = models.CharField(
        max_length=255, 
        unique=True, 
        verbose_name="Razón Social / Nombre de la Empresa",
        help_text="Nombre legal o comercial de la empresa cliente."
    )
    direccion = models.CharField(
        max_length=255, 
        blank=True, 
        null=True, 
        verbose_name="Dirección Fiscal",
        help_text="Dirección principal de la empresa."
    )
    sitio_web = models.URLField(
        max_length=255, 
        blank=True, 
        null=True, 
        verbose_name="Página Web"
    )

    # --- Persona de Contacto Principal ---
    persona_contacto = models.CharField(
        max_length=255, 
        verbose_name="Persona de Contacto Principal"
    )
    cargo_contacto = models.CharField(
        max_length=100, 
        blank=True, 
        null=True, 
        verbose_name="Cargo del Contacto"
    )
    celular_contacto = models.CharField(
        max_length=20, 
        verbose_name="Celular del Contacto"
    )
    correo_contacto = models.EmailField(
        max_length=255, 
        verbose_name="Correo Electrónico del Contacto"
    )

    # --- Logística, Estado y Auditoría ---
    firma_electronica = models.ImageField(
        upload_to='firmas_clientes/', 
        blank=True, 
        null=True, 
        verbose_name="Firma Electrónica"
    )
    
    activo = models.BooleanField(
        default=True, 
        verbose_name="Cliente Activo",
        help_text="Indica si el cliente está habilitado."
    )
    
    # Auditoría: Quién creó el registro (debe ser un Admin/Supervisor)
    creado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        verbose_name="Creado Por",
        related_name='clientes_creados'
    )

    creado_en = models.DateTimeField(auto_now_add=True, verbose_name="Fecha de Creación")
    actualizado_en = models.DateTimeField(auto_now=True, verbose_name="Última Actualización")

    def __str__(self):
        return self.razon_social

    def get_absolute_url(self):
        """Devuelve la URL para ver los detalles de este cliente."""
        return reverse('clientes:cliente_detail', kwargs={'pk': self.pk})

    class Meta:
        verbose_name = "Cliente"
        verbose_name_plural = "Clientes"
        ordering = ['razon_social']
from django.db import models

# Create your models here.
