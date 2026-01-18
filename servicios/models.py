# servicios/models.py
from django.db import models
from django.utils import timezone
from clientes.models import Cliente
from trabajadores.models import TrabajadorProfile
from decimal import Decimal
from django.utils import timezone
from django.db.utils import IntegrityError
from datetime import date
from django.db.models import Sum
from django.core.validators import FileExtensionValidator, MinValueValidator
from django.core.exceptions import ValidationError
from django.db import transaction

TASA_IGV_PORCENTAJE = Decimal('0.18') 

class Norma(models.Model):
    codigo = models.CharField(max_length=50, unique=True, verbose_name="Código de Norma")
    nombre = models.CharField(max_length=255, unique=True, verbose_name="Nombre Completo")
    descripcion = models.TextField(blank=True, null=True)

    def __str__(self):
        return self.codigo

    class Meta:
        verbose_name = "Norma de Ensayo"
        verbose_name_plural = "Normas de Ensayo"
        ordering = ['codigo']

class Metodo(models.Model):
    codigo = models.CharField(max_length=50, unique=True, verbose_name="Código de Método")
    nombre = models.CharField(max_length=100, unique=True, verbose_name="Nombre del Método")
    descripcion = models.TextField(blank=True, null=True)

    def __str__(self):
        return f"{self.codigo} - {self.nombre}"

    class Meta:
        verbose_name = "Método de Ensayo"
        verbose_name_plural = "Métodos de Ensayo"
        ordering = ['codigo']
        
class CategoriaServicio(models.Model):
    nombre = models.CharField(max_length=100, unique=True, verbose_name="Nombre de Categoría")

    def __str__(self):
        return self.nombre

    class Meta:
        verbose_name = "1. Categoría Principal"
        verbose_name_plural = "1. Categorías Principales"
        ordering = ['nombre']

class Subcategoria(models.Model):
    nombre = models.CharField(max_length=100, unique=True, verbose_name="Nombre de Subcategoría")
    def __str__(self):
        return self.nombre

    class Meta:
        verbose_name = "2. Subcategoría"
        verbose_name_plural = "2. Subcategorías"
        ordering = ['nombre']

class Servicio(models.Model):
    codigo_facturacion = models.CharField(max_length=50, unique=True)
    nombre = models.CharField(max_length=150, verbose_name="Nombre del Ensayo")
    norma = models.ForeignKey('Norma', on_delete=models.SET_NULL, null=True, blank=True)
    metodo = models.ForeignKey('Metodo', on_delete=models.SET_NULL, null=True, blank=True)
    
    precio_base = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'))
    unidad_base = models.CharField(max_length=50, default='Ensayo')
    esta_acreditado = models.BooleanField(default=False)

    def __str__(self):
        return f"{self.codigo_facturacion} - {self.nombre}"

    class Meta:
        verbose_name = "3. Servicio / Ensayo"
        verbose_name_plural = "3. Servicios / Ensayos"
        ordering = ['nombre']

class Cotizacion(models.Model):
    cliente = models.ForeignKey(Cliente, on_delete=models.CASCADE, related_name='cotizaciones', verbose_name="Cliente")
    trabajador_responsable = models.ForeignKey(TrabajadorProfile, on_delete=models.SET_NULL, null=True, blank=True, related_name='cotizaciones_emitidas', verbose_name="Responsable de la Oferta")
    
    numero_oferta = models.CharField(max_length=50, unique=True, blank=True, null=True, verbose_name="Número de Oferta (VCF-OTE-YYYY-XXX)")
    fecha_generacion = models.DateField(default=timezone.now, verbose_name="Fecha de Generación")
    
    asunto_servicio = models.CharField(max_length=255, verbose_name="Asunto del Servicio (Ej: Ensayos de Campo)")
    proyecto_asociado = models.CharField(max_length=255, blank=True, null=True, verbose_name="Proyecto del Cliente")
    
    persona_contacto = models.CharField(max_length=200, verbose_name="Persona de Contacto (Atención)")
    correo_contacto = models.EmailField(verbose_name="Correo de Contacto")
    telefono_contacto = models.CharField(max_length=20, verbose_name="Teléfono de Contacto")
    
    ESTADO_CHOICES = [
        ('Pendiente', 'Pendiente de Revisión'),
        ('Enviada', 'Enviada al Cliente'),
        ('Aceptada', 'Aceptada'),
        ('Rechazada', 'Rechazada'),
        ('Anulada', 'Anulada')
    ]
    estado = models.CharField(max_length=20, choices=ESTADO_CHOICES, default='Pendiente', verbose_name="Estado")
    
    plazo_entrega_dias = models.IntegerField(default=30, verbose_name="Plazo de Entrega (Días)")
    FORMA_PAGO_CHOICES = [
        ('Contado', 'Al Contado'),
        ('15_dias', 'A 15 días'),
        ('30_dias', 'A 30 días'),
        ('60_dias', 'A 60 días'),
        ('Personalizado', 'Personalizado')
    ]
    forma_pago = models.CharField(max_length=20, choices=FORMA_PAGO_CHOICES, default='Contado', verbose_name="Forma de Pago")
    validez_oferta_dias = models.IntegerField(default=30, validators=[MinValueValidator(1)], verbose_name="Validez de la Oferta (Días)")
    
    tasa_igv = models.DecimalField(max_digits=5, decimal_places=3, default=0.18)
    subtotal = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    impuesto_igv = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    monto_total = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    
    observaciones_condiciones = models.TextField(blank=True, null=True, verbose_name="Observaciones Adicionales")
    
    fecha_creacion = models.DateTimeField(auto_now_add=True)
    fecha_actualizacion = models.DateTimeField(auto_now=True)

    @property
    def detalles_cotizacion(self):
        """
        Atajo para obtener todos los ítems sin pasar manualmente por grupos.
        Esto permite que 'cotizacion.detalles_cotizacion.all()' funcione.
        """
        from .models import CotizacionDetalle 
        return CotizacionDetalle.objects.filter(grupo__cotizacion=self)

    def calcular_totales(self):
        total_neto = self.detalles_cotizacion.aggregate(
            sum_total=Sum('total_detalle')
        )['sum_total'] or Decimal('0.00')

        self.subtotal = total_neto
        self.impuesto_igv = self.subtotal * self.tasa_igv
        self.monto_total = self.subtotal + self.impuesto_igv

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        self.calcular_totales()
        super().save(update_fields=['subtotal', 'impuesto_igv', 'monto_total'])

    def __str__(self):
        return f"{self.numero_oferta} - {self.cliente.razon_social}"

    class Meta:
        verbose_name = "Cotización"
        ordering = ['-fecha_creacion']
        
class CotizacionGrupo(models.Model):
    cotizacion = models.ForeignKey(Cotizacion, on_delete=models.CASCADE, related_name='grupos')
    nombre_grupo = models.CharField(max_length=255, verbose_name="Nombre de la Categoría/Subgrupo")
    orden = models.PositiveIntegerField(default=1, verbose_name="Orden de visualización")

    class Meta:
        verbose_name = "Grupo de Cotización"
        verbose_name_plural = "Grupos de Cotización"
        ordering = ['orden']

    def __str__(self):
        return f"{self.nombre_grupo} - {self.cotizacion.numero_oferta}"

class CotizacionDetalle(models.Model):
    grupo = models.ForeignKey(CotizacionGrupo, on_delete=models.CASCADE, related_name='detalles_items')
    
    servicio = models.ForeignKey('Servicio', on_delete=models.RESTRICT, verbose_name="Servicio (Ensayo)")
    
    norma_manual = models.CharField(max_length=255, blank=True, null=True, verbose_name="Norma (Manual)")
    metodo_manual = models.CharField(max_length=255, blank=True, null=True, verbose_name="Método (Manual)")
    
    descripcion_especifica = models.TextField(verbose_name="Descripción detallada para el ítem")
    unidad_medida = models.CharField(max_length=50, default='Ensayo')
    cantidad = models.PositiveIntegerField(default=1, validators=[MinValueValidator(1)])
    precio_unitario = models.DecimalField(max_digits=12, decimal_places=2)
    
    total_detalle = models.DecimalField(max_digits=12, decimal_places=2, editable=False)

    def save(self, *args, **kwargs):
        self.total_detalle = Decimal(self.cantidad) * self.precio_unitario
        
        from django.db import transaction
        with transaction.atomic():
            super().save(*args, **kwargs)
            self.grupo.cotizacion.save()

    def delete(self, *args, **kwargs):
        cotizacion_padre = self.grupo.cotizacion
        super().delete(*args, **kwargs)
        cotizacion_padre.save()

    class Meta:
        verbose_name = "Detalle de Cotización"
        ordering = ['id']

class Voucher(models.Model):
    cotizacion = models.OneToOneField(
        Cotizacion, 
        on_delete=models.CASCADE, 
        related_name='voucher', 
        verbose_name="Cotización Asociada"
    )
    codigo = models.CharField(max_length=100, verbose_name="Código de la Transacción/Voucher")
    monto_pagado = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="Monto Pagado")
    
    imagen = models.FileField(
        upload_to='vouchers/',
        verbose_name="Archivo (PDF/Imagen) del Voucher",
        validators=[FileExtensionValidator(allowed_extensions=['jpg', 'jpeg', 'png', 'pdf'])]
    )

    documento_firmado = models.FileField(
        upload_to='vouchers/documentos_firmados/', 
        null=True, 
        blank=True,
        verbose_name="Oferta/Contrato Firmado por Cliente",
        validators=[FileExtensionValidator(allowed_extensions=['pdf'])]
    )
    fecha_subida = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return f'Voucher {self.codigo} para {self.cotizacion.numero_oferta}'
    
    class Meta:
        verbose_name = "Voucher de Pago"
        verbose_name_plural = "Vouchers de Pago"