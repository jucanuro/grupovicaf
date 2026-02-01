import datetime
import os
from django.db import models, transaction  
from django.conf import settings
from django.urls import reverse 

class Cliente(models.Model):
    """
    Modelo principal para almacenar la información de las empresas/clientes.
    Incluye un código confidencial automático y gestión de branding (logo).
    """

    codigo_confidencial = models.CharField(
        max_length=20, 
        unique=True, 
        editable=False,
        verbose_name="Código de Cliente (Anónimo)",
        help_text="Generado automáticamente: CLI-YY-XXXX"
    )
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
    
    logo_empresa = models.ImageField(
        upload_to='clientes/logos/%Y/%m/',
        blank=True,
        null=True,
        verbose_name="Logo de la Empresa",
        help_text="Imagen opcional para personalizar informes."
    )
    firma_electronica = models.ImageField(
        upload_to='clientes/firmas/%Y/%m/',
        blank=True, 
        null=True, 
        verbose_name="Firma Electrónica"
    )

    direccion = models.CharField(
        max_length=255, 
        blank=True, 
        null=True, 
        verbose_name="Dirección Fiscal"
    )
    sitio_web = models.URLField(
        max_length=255, 
        blank=True, 
        null=True, 
        verbose_name="Página Web"
    )
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

    activo = models.BooleanField(
        default=True, 
        verbose_name="Cliente Activo"
    )
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

    class Meta:
        verbose_name = "Cliente"
        verbose_name_plural = "Clientes"
        ordering = ['-creado_en']
        indexes = [
            models.Index(fields=['codigo_confidencial']),
            models.Index(fields=['ruc']),
        ]

    def __str__(self):
        return f"{self.codigo_confidencial} | {self.razon_social}"

    def get_absolute_url(self):
        return reverse('clientes:cliente_detail', kwargs={'pk': self.pk})

    def save(self, *args, **kwargs):
        """Genera el código confidencial de forma segura y robusta."""
        if not self.codigo_confidencial:
            with transaction.atomic():
                anio = datetime.datetime.now().strftime('%y')
                prefijo = f"CLI-{anio}-"
                
                ultimo_cliente = Cliente.objects.filter(
                    codigo_confidencial__startswith=prefijo
                ).select_for_update().order_by('codigo_confidencial').last()

                if ultimo_cliente:
                    try:
                        partes = ultimo_cliente.codigo_confidencial.split('-')
                        ultimo_num = int(partes[-1])
                        nuevo_num = str(ultimo_num + 1).zfill(4)
                    except (ValueError, IndexError):
                        nuevo_num = "0001"
                else:
                    nuevo_num = "0001"

                self.codigo_confidencial = f"{prefijo}{nuevo_num}"
                super().save(*args, **kwargs)
        else:
            super().save(*args, **kwargs)