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

# Definición de Constantes Financieras
TASA_IGV_PORCENTAJE = Decimal('0.18') # 18% para el Impuesto General a las Ventas (Perú)

# ================================================================
# Modelos de Apoyo: Normas y Métodos
# ================================================================
class Norma(models.Model):
    codigo = models.CharField(max_length=50, unique=True, verbose_name="Código de Norma (e.g., ASTM D2216-19)")
    nombre = models.CharField(max_length=255, unique=True, verbose_name="Nombre Completo de la Norma")
    descripcion = models.TextField(blank=True, null=True)

    def __str__(self):
        return self.codigo

    class Meta:
        verbose_name = "Norma de Ensayo"
        verbose_name_plural = "Normas de Ensayo"
        ordering = ['codigo']

class Metodo(models.Model):
    codigo = models.CharField(max_length=50, unique=True, verbose_name="Código de Método (e.g., A/B, Ensayo)")
    nombre = models.CharField(max_length=100, unique=True, verbose_name="Nombre del Método")
    descripcion = models.TextField(blank=True, null=True)

    def __str__(self):
        return f"{self.codigo} - {self.nombre}"

    class Meta:
        verbose_name = "Método de Ensayo"
        verbose_name_plural = "Métodos de Ensayo"
        ordering = ['codigo']

# ================================================================
# Modelo de Servicio (Ensayo) - Base para el Tarifario
# ================================================================
class CategoriaServicio(models.Model):
    nombre = models.CharField(max_length=100, unique=True, verbose_name="Nombre de la Categoría (Ej: ENSAYOS EN SUELOS)")
    codigo_prefijo = models.CharField(max_length=10, unique=True, verbose_name="Prefijo de Código (Ej: ES, EC, EA)")
    descripcion = models.TextField(blank=True, null=True)

    def __str__(self):
        return self.nombre

    class Meta:
        verbose_name = "Categoría de Servicio"
        verbose_name_plural = "Categorías de Servicios"
        ordering = ['nombre']

class Servicio(models.Model):
    categoria = models.ForeignKey(
        'CategoriaServicio', 
        on_delete=models.SET_NULL, 
        related_name='servicios',
        null=True, 
        blank=True,
        verbose_name="Categoría del Ensayo"
    )
    codigo_facturacion = models.CharField(max_length=50, unique=True, verbose_name="Cód. Fact. (e.g., ES001, TC001)")
    nombre = models.CharField(max_length=150, verbose_name="Nombre del Servicio/Ensayo")
    descripcion = models.TextField(verbose_name="Descripción General del Servicio")
    
    # Tarifario base
    precio_base = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'), verbose_name="Precio Unitario Base (Normal)")
    precio_urgente = models.DecimalField(
        max_digits=10, 
        decimal_places=2, 
        null=True, 
        blank=True, 
        verbose_name="Precio Unitario Urgente"
    )

    # Bandera para manejar "SP" (Sujeto a Presupuesto)
    es_sujeto_a_presupuesto = models.BooleanField(
        default=False, 
        verbose_name="¿Sujeto a Presupuesto (SP)?"
    )
    unidad_base = models.CharField(max_length=50, default='Ensayo', verbose_name="Unidad de Medida Base")
    
    # Relaciones con Normas y Métodos (Muchos a Muchos)
    normas = models.ManyToManyField(Norma, related_name='servicios', blank=True, verbose_name="Normas Asociadas")
    metodos = models.ManyToManyField(Metodo, related_name='servicios', blank=True, verbose_name="Métodos Asociados")
    
    # Información Web/Visual
    imagen = models.ImageField(upload_to='servicios/', verbose_name="Imagen Representativa", blank=True, null=True)
    esta_acreditado = models.BooleanField(default=False, verbose_name="¿Acreditado por INACAL-DA?")

    def __str__(self):
        return f"{self.codigo_facturacion} - {self.nombre}"

    class Meta:
        verbose_name = "Servicio de Laboratorio"
        verbose_name_plural = "Servicios de Laboratorio"
        ordering = ['nombre', 'codigo_facturacion']


class DetalleServicio(models.Model):
    servicio = models.OneToOneField(
        Servicio, 
        on_delete=models.CASCADE, 
        related_name='detalle_web', 
        verbose_name="Servicio Web"
    )
    titulo = models.CharField(max_length=100, verbose_name="Título del Detalle")
    descripcion = models.TextField(verbose_name="Descripción del Detalle")
    imagen = models.ImageField(upload_to='servicios/detalles/', blank=True, null=True, verbose_name="Imagen o Ícono")

    def __str__(self):
        return f"{self.servicio.nombre} - {self.titulo}"

    class Meta:
        verbose_name = "Detalle de Servicio (Página Web)"
        verbose_name_plural = "Detalles de Servicios (Página Web)"

# ================================================================
# Modelo de Cotización (Oferta Técnica-Económica) - CLAVE
# ================================================================
class Cotizacion(models.Model):
    # ... (Campos de encabezado y relaciones) ...
    cliente = models.ForeignKey(Cliente, on_delete=models.CASCADE, related_name='cotizaciones', verbose_name="Cliente")
    trabajador_responsable = models.ForeignKey(TrabajadorProfile, on_delete=models.SET_NULL, null=True, blank=True, related_name='cotizaciones_emitidas', verbose_name="Responsable de la Oferta")
    numero_oferta = models.CharField(
        max_length=50, 
        unique=True, 
        blank=True, 
        null=True, 
        verbose_name="Número de Oferta (VCF-OTE-YYYY-XXX)"
    )
    fecha_generacion = models.DateField(
        default=timezone.now, 
        verbose_name="Fecha de Generación de la Oferta"
    )
    asunto_servicio = models.CharField(max_length=255, verbose_name="Asunto del Servicio (Ej: Ensayos de Campo)")
    proyecto_asociado = models.CharField(max_length=255, blank=True, null=True, verbose_name="Referencia/Nombre del Proyecto del Cliente")
    persona_contacto = models.CharField(max_length=200, verbose_name="Persona de Contacto (Atención)")
    correo_contacto = models.EmailField(verbose_name="Correo de Contacto")
    telefono_contacto = models.CharField(max_length=20, verbose_name="Teléfono de Contacto")
    
    ESTADO_CHOICES = [
        ('Pendiente', 'Pendiente de Revisión Interna'),
        ('Enviada', 'Enviada al Cliente'),
        ('Aceptada', 'Aceptada'),
        ('Rechazada', 'Rechazada'),
        ('Anulada', 'Anulada')
    ]
    estado = models.CharField(max_length=20, choices=ESTADO_CHOICES, default='Pendiente', verbose_name="Estado de la Oferta")
    aprobada_por_cliente = models.BooleanField(default=False, verbose_name="Aprobación Final del Cliente")
    
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
    
    tasa_igv = models.DecimalField(max_digits=5, decimal_places=3, default=0.18, verbose_name="Tasa IGV Aplicada (Ej: 0.18)") # Usar 0.18 si TASA_IGV_PORCENTAJE no está importado
    subtotal = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'), verbose_name="Subtotal (Sin IGV)")
    impuesto_igv = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'), verbose_name="Monto IGV")
    monto_total = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'), verbose_name="Monto Total (Final)")
    
    observaciones_condiciones = models.TextField(blank=True, null=True, verbose_name="Observaciones o Condiciones Adicionales")
    
    fecha_creacion = models.DateTimeField(auto_now_add=True)
    fecha_actualizacion = models.DateTimeField(auto_now=True)

    def calcular_totales(self):
        """ Lógica de cálculo de totales basada en los detalles. """
        
        if self.pk is None:
            return 

        # Se usa 'total_detalle'
        total_neto = self.detalles_cotizacion.aggregate(
            sum_total=Sum('total_detalle') 
        )['sum_total'] or Decimal('0.00')

        self.subtotal = total_neto
        self.impuesto_igv = self.subtotal * self.tasa_igv
        self.monto_total = self.subtotal + self.impuesto_igv


    def save(self, *args, **kwargs):
        self.calcular_totales()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.numero_oferta} - {self.cliente.razon_social}"

    class Meta:
        verbose_name = "Cotización (Oferta Técnica)"
        verbose_name_plural = "Cotizaciones (Ofertas Técnicas)"
        ordering = ['-fecha_creacion']
# ================================================================
# Modelo para el detalle de la cotización (Line Items)
# ================================================================
class CotizacionDetalle(models.Model):
    cotizacion = models.ForeignKey(Cotizacion, on_delete=models.CASCADE, related_name='detalles_cotizacion', verbose_name="Cotización Padre")
    
    # Detalle del Servicio
    servicio = models.ForeignKey(Servicio, on_delete=models.RESTRICT, verbose_name="Servicio (Ensayo) Cotizado")
    norma = models.ForeignKey(Norma, on_delete=models.SET_NULL, null=True, blank=True, verbose_name="Norma de Ensayo Aplicada")
    metodo = models.ForeignKey(Metodo, on_delete=models.SET_NULL, null=True, blank=True, verbose_name="Método Aplicado")
    
    # Montos
    descripcion_especifica = models.TextField(verbose_name="Descripción del Ítem (Incluye notas específicas)")
    unidad_medida = models.CharField(max_length=50, default='Ensayo', verbose_name="Unidad de Medida (Ej: Und, Ensayo, DM)")
    cantidad = models.PositiveIntegerField(default=1, validators=[MinValueValidator(1)], verbose_name="Cantidad")
    precio_unitario = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="Precio Unitario Acordado")
    
    # ✅ CAMPO DE BASE DE DATOS REQUERIDO
    total_detalle = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'), editable=False, verbose_name="Subtotal de Línea") 

    @property
    def subtotal_linea(self):
        return self.cantidad * self.precio_unitario

    def save(self, *args, **kwargs):
        # ✅ Cálculo del valor del nuevo campo antes de guardar.
        self.total_detalle = self.cantidad * self.precio_unitario
        
        with transaction.atomic():
            super().save(*args, **kwargs)
            self.cotizacion.save() # Recalcula el padre

    def delete(self, *args, **kwargs):
        cotizacion = self.cotizacion
        with transaction.atomic():
            super().delete(*args, **kwargs)
            cotizacion.save()

    def __str__(self):
        return f"Línea {self.id} de {self.cotizacion.numero_oferta}: {self.descripcion_especifica[:30]}..."

    class Meta:
        verbose_name = "Detalle de Cotización"
        verbose_name_plural = "Detalles de Cotización"
        ordering = ['id']
# ================================================================
# Modelo Voucher (Pago)
# ================================================================
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
    fecha_subida = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return f'Voucher {self.codigo} para {self.cotizacion.numero_oferta}'
    
    class Meta:
        verbose_name = "Voucher de Pago"
        verbose_name_plural = "Vouchers de Pago"