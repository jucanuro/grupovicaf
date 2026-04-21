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
        verbose_name = "Categoría Principal"
        verbose_name_plural = "Categorías Principales"
        ordering = ['nombre']

class Subcategoria(models.Model):
    nombre = models.CharField(max_length=100, unique=True, verbose_name="Nombre de Subcategoría")
    def __str__(self):
        return self.nombre

    class Meta:
        verbose_name = "Subcategoría"
        verbose_name_plural = "Subcategorías"
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
    trabajador_responsable = models.ForeignKey(
        TrabajadorProfile,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='cotizaciones_emitidas',
        verbose_name="Responsable de la Oferta"
    )

    numero_oferta = models.CharField(max_length=50, unique=True, blank=True, null=True, verbose_name="Número de Oferta")
    fecha_generacion = models.DateField(default=timezone.now, verbose_name="Fecha de Generación")

    es_plantilla = models.BooleanField(default=False, verbose_name="¿Es una Plantilla?")
    nombre_plantilla = models.CharField(max_length=150, blank=True, null=True, verbose_name="Nombre identificador de la Plantilla")

    servicio_general = models.ForeignKey(
        'CategoriaServicio',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name="Categoría General"
    )
    asunto_servicio = models.CharField(max_length=255, verbose_name="Asunto del Servicio")
    proyecto_asociado = models.CharField(max_length=255, blank=True, null=True, verbose_name="Proyecto del Cliente")

    persona_contacto = models.CharField(max_length=200, verbose_name="Persona de Contacto")
    correo_contacto = models.EmailField(verbose_name="Correo de Contacto")
    telefono_contacto = models.CharField(max_length=20, verbose_name="Teléfono de Contacto")

    ESTADO_CHOICES = [
        ('Pendiente', 'Pendiente de Revisión'),
        ('Enviada', 'Enviada al Cliente'),
        ('Aceptada', 'Aceptada'),
        ('Rechazada', 'Rechazada'),
        ('Anulada', 'Anulada'),
    ]
    estado = models.CharField(max_length=20, choices=ESTADO_CHOICES, default='Pendiente', verbose_name="Estado")

    plazo_entrega_dias = models.IntegerField(default=30, verbose_name="Plazo de Entrega (Días)")

    FORMA_PAGO_CHOICES = [
        ('Contado', 'Al Contado'),
        ('15_dias', 'A 15 días'),
        ('30_dias', 'A 30 días'),
        ('60_dias', 'A 60 días'),
        ('Personalizado', 'Personalizado'),
    ]
    forma_pago = models.CharField(max_length=20, choices=FORMA_PAGO_CHOICES, default='Contado', verbose_name="Forma de Pago")
    validez_oferta_dias = models.IntegerField(default=30, validators=[MinValueValidator(1)], verbose_name="Validez de la Oferta (Días)")

    tasa_igv = models.DecimalField(max_digits=5, decimal_places=3, default=0.18)
    subtotal = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    impuesto_igv = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    monto_total = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))

    observaciones_condiciones = models.TextField(blank=True, null=True, verbose_name="Observaciones Adicionales")

    # NUEVO
    contenido_condiciones_configurado = models.BooleanField(
        default=False,
        verbose_name="¿Se configuró el contenido dinámico?"
    )
    contenido_condiciones_bloqueado = models.BooleanField(
        default=False,
        verbose_name="¿Contenido bloqueado para edición?"
    )
    contenido_condiciones_fecha_bloqueo = models.DateTimeField(
        blank=True,
        null=True,
        verbose_name="Fecha de bloqueo del contenido"
    )

    fecha_creacion = models.DateTimeField(auto_now_add=True)
    fecha_actualizacion = models.DateTimeField(auto_now=True)

    @property
    def detalles_cotizacion(self):
        from .models import CotizacionDetalle
        return CotizacionDetalle.objects.filter(grupo__cotizacion=self)

    def calcular_totales(self):
        total_neto = self.detalles_cotizacion.aggregate(
            sum_total=models.Sum('total_detalle')
        )['sum_total'] or Decimal('0.00')

        self.subtotal = total_neto
        self.impuesto_igv = self.subtotal * self.tasa_igv
        self.monto_total = self.subtotal + self.impuesto_igv

    def puede_editar_contenido_condiciones(self):
        return not self.contenido_condiciones_bloqueado and self.estado not in ('Aceptada', 'Anulada')

    def bloquear_contenido_condiciones(self):
        self.contenido_condiciones_bloqueado = True
        self.contenido_condiciones_fecha_bloqueo = timezone.now()
        self.save(update_fields=[
            'contenido_condiciones_bloqueado',
            'contenido_condiciones_fecha_bloqueo',
            'fecha_actualizacion',
        ])

    def save(self, *args, **kwargs):
        if self.es_plantilla:
            self.numero_oferta = None
            if not self.nombre_plantilla:
                self.nombre_plantilla = f"Modelo: {self.asunto_servicio}"

        super().save(*args, **kwargs)

        self.calcular_totales()

        super().save(update_fields=[
            'subtotal',
            'impuesto_igv',
            'monto_total',
            'numero_oferta',
            'nombre_plantilla',
        ])

    def __str__(self):
        if self.es_plantilla:
            return f"PLANTILLA: {self.nombre_plantilla}"
        return f"{self.numero_oferta or 'S/N'} - {self.cliente.razon_social}"

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
             
class PlantillaCotizacion(models.Model):
    nombre_plantilla = models.CharField(max_length=200, verbose_name="Nombre de la Plantilla")
    servicio_general = models.ForeignKey(
        'CategoriaServicio', 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        verbose_name="Categoría General"
    )
    asunto_referencial = models.CharField(max_length=255, verbose_name="Asunto Sugerido")
    activo = models.BooleanField(default=True)
    plazo_entrega_defecto = models.IntegerField(default=30)
    forma_pago_defecto = models.CharField(max_length=20, default='Contado')
    
    subtotal = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    
    fecha_creacion = models.DateTimeField(auto_now_add=True)

    def calcular_totales(self):
        total = PlantillaDetalle.objects.filter(grupo__plantilla=self).aggregate(
            sum_total=models.Sum('total_detalle'))['sum_total'] or Decimal('0.00')
        self.subtotal = total
        self.save(update_fields=['subtotal'])

    def __str__(self):
        return f"PLANTILLA: {self.nombre_plantilla.upper()}"

    class Meta:
        verbose_name = "Plantilla de Cotización"
        verbose_name_plural = "Plantillas de Cotizaciones"

class PlantillaGrupo(models.Model):
    plantilla = models.ForeignKey(PlantillaCotizacion, on_delete=models.CASCADE, related_name='grupos')
    nombre_grupo = models.CharField(max_length=255, verbose_name="Nombre de la Categoría/Subgrupo")
    orden = models.PositiveIntegerField(default=1)

    def __str__(self):
        return f"{self.nombre_grupo} (en {self.plantilla.nombre_plantilla})"

class PlantillaDetalle(models.Model):
    grupo = models.ForeignKey(PlantillaGrupo, on_delete=models.CASCADE, related_name='detalles_items')
    servicio = models.ForeignKey('Servicio', on_delete=models.RESTRICT)
    
    norma_manual = models.CharField(max_length=255, blank=True, null=True)
    metodo_manual = models.CharField(max_length=255, blank=True, null=True)
    
    descripcion_especifica = models.TextField()
    unidad_medida = models.CharField(max_length=50, default='Ensayo')
    cantidad = models.PositiveIntegerField(default=1)
    precio_unitario = models.DecimalField(max_digits=12, decimal_places=2)
    
    total_detalle = models.DecimalField(max_digits=12, decimal_places=2, editable=False)

    def save(self, *args, **kwargs):
        self.total_detalle = Decimal(self.cantidad) * self.precio_unitario
        super().save(*args, **kwargs)
        self.grupo.plantilla.calcular_totales()

    def delete(self, *args, **kwargs):
        plantilla = self.grupo.plantilla
        super().delete(*args, **kwargs)
        plantilla.calcular_totales()
        
class CatalogoCondicionSeccion(models.Model):
    TIPO_CHOICES = [
        ('notas', 'Notas'),
        ('lista', 'Lista'),
    ]

    codigo = models.CharField(max_length=50, unique=True, verbose_name="Código interno")
    titulo = models.CharField(max_length=255, verbose_name="Título de la sección")
    tipo = models.CharField(
        max_length=20,
        choices=TIPO_CHOICES,
        default='lista',
        verbose_name="Tipo de presentación"
    )
    orden = models.PositiveIntegerField(default=1, verbose_name="Orden")
    activo = models.BooleanField(default=True, verbose_name="Activo")
    es_obligatoria = models.BooleanField(
        default=False,
        verbose_name="¿La sección siempre debe mostrarse?"
    )

    class Meta:
        verbose_name = "Catálogo - Sección de Condición"
        verbose_name_plural = "Catálogo - Secciones de Condiciones"
        ordering = ['orden', 'id']

    def __str__(self):
        return f"{self.orden}. {self.titulo}"


class CatalogoCondicionItem(models.Model):
    TIPO_NODO_CHOICES = [
        ('grupo', 'Grupo / Padre'),
        ('item', 'Ítem / Viñeta'),
    ]

    seccion = models.ForeignKey(
        CatalogoCondicionSeccion,
        on_delete=models.CASCADE,
        related_name='items',
        verbose_name="Sección"
    )
    parent = models.ForeignKey(
        'self',
        on_delete=models.CASCADE,
        related_name='children',
        blank=True,
        null=True,
        verbose_name="Padre"
    )

    tipo_nodo = models.CharField(
        max_length=20,
        choices=TIPO_NODO_CHOICES,
        default='item',
        verbose_name="Tipo de nodo"
    )
    titulo = models.CharField(
        max_length=255,
        blank=True,
        null=True,
        verbose_name="Título corto"
    )
    texto = models.TextField(verbose_name="Texto base")
    orden = models.PositiveIntegerField(default=1, verbose_name="Orden")
    nivel = models.PositiveSmallIntegerField(default=0, verbose_name="Nivel jerárquico")

    activo = models.BooleanField(default=True, verbose_name="Activo")
    seleccionado_por_defecto = models.BooleanField(
        default=False,
        verbose_name="Seleccionado por defecto"
    )
    editable_en_cotizacion = models.BooleanField(
        default=True,
        verbose_name="¿Editable en cotización?"
    )
    es_obligatorio = models.BooleanField(
        default=False,
        verbose_name="¿Siempre debe incluirse?"
    )

    class Meta:
        verbose_name = "Catálogo - Ítem de Condición"
        verbose_name_plural = "Catálogo - Ítems de Condiciones"
        ordering = ['seccion__orden', 'orden', 'id']
        indexes = [
            models.Index(fields=['seccion', 'orden']),
            models.Index(fields=['parent', 'orden']),
            models.Index(fields=['activo']),
        ]

    def clean(self):
        if self.parent and self.parent.seccion_id != self.seccion_id:
            raise ValidationError("El padre debe pertenecer a la misma sección.")
        if self.parent and self.parent_id == self.id:
            raise ValidationError("Un ítem no puede ser padre de sí mismo.")

    def __str__(self):
        base = self.titulo or self.texto[:70]
        return f"{self.seccion.titulo} - {base}"


class CotizacionCondicionSeccion(models.Model):
    cotizacion = models.ForeignKey(
        Cotizacion,
        on_delete=models.CASCADE,
        related_name='condiciones_secciones',
        verbose_name="Cotización"
    )
    catalogo_seccion = models.ForeignKey(
        CatalogoCondicionSeccion,
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name='snapshots',
        verbose_name="Sección de catálogo origen"
    )

    codigo = models.CharField(max_length=50, verbose_name="Código congelado")
    titulo = models.CharField(max_length=255, verbose_name="Título congelado")
    tipo = models.CharField(max_length=20, default='lista', verbose_name="Tipo congelado")
    orden = models.PositiveIntegerField(default=1, verbose_name="Orden")

    seleccionada = models.BooleanField(default=False, verbose_name="Seleccionada")

    fecha_creacion = models.DateTimeField(auto_now_add=True)
    fecha_actualizacion = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Cotización - Sección de Condición"
        verbose_name_plural = "Cotización - Secciones de Condiciones"
        ordering = ['orden', 'id']
        unique_together = [('cotizacion', 'codigo')]
        indexes = [
            models.Index(fields=['cotizacion', 'orden']),
            models.Index(fields=['cotizacion', 'codigo']),
        ]

    def __str__(self):
        return f"{self.cotizacion} - {self.titulo}"


class CotizacionCondicionItem(models.Model):
    seccion = models.ForeignKey(
        CotizacionCondicionSeccion,
        on_delete=models.CASCADE,
        related_name='items',
        verbose_name="Sección de cotización"
    )
    catalogo_item = models.ForeignKey(
        CatalogoCondicionItem,
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name='snapshots',
        verbose_name="Ítem de catálogo origen"
    )
    parent = models.ForeignKey(
        'self',
        on_delete=models.CASCADE,
        related_name='children',
        blank=True,
        null=True,
        verbose_name="Padre"
    )

    tipo_nodo = models.CharField(
        max_length=20,
        choices=CatalogoCondicionItem.TIPO_NODO_CHOICES,
        default='item',
        verbose_name="Tipo de nodo"
    )
    titulo = models.CharField(
        max_length=255,
        blank=True,
        null=True,
        verbose_name="Título congelado"
    )

    texto_base = models.TextField(verbose_name="Texto base copiado del catálogo")
    texto_final = models.TextField(verbose_name="Texto final de la cotización")

    orden = models.PositiveIntegerField(default=1, verbose_name="Orden")
    nivel = models.PositiveSmallIntegerField(default=0, verbose_name="Nivel jerárquico")

    seleccionado = models.BooleanField(default=False, verbose_name="Seleccionado")
    es_obligatorio = models.BooleanField(default=False, verbose_name="Obligatorio")
    editable_en_cotizacion = models.BooleanField(default=True, verbose_name="Editable en cotización")
    fue_editado = models.BooleanField(default=False, verbose_name="¿Fue editado respecto al base?")

    fecha_creacion = models.DateTimeField(auto_now_add=True)
    fecha_actualizacion = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Cotización - Ítem de Condición"
        verbose_name_plural = "Cotización - Ítems de Condiciones"
        ordering = ['seccion__orden', 'orden', 'id']
        indexes = [
            models.Index(fields=['seccion', 'orden']),
            models.Index(fields=['parent', 'orden']),
            models.Index(fields=['seleccionado']),
        ]

    def clean(self):
        if self.parent and self.parent.seccion_id != self.seccion_id:
            raise ValidationError("El padre debe pertenecer a la misma sección de cotización.")
        if self.parent and self.parent_id == self.id:
            raise ValidationError("Un ítem no puede ser padre de sí mismo.")

    def save(self, *args, **kwargs):
        if not self.texto_final:
            self.texto_final = self.texto_base

        self.fue_editado = (self.texto_base or '').strip() != (self.texto_final or '').strip()
        super().save(*args, **kwargs)

    def __str__(self):
        base = self.titulo or self.texto_final[:70]
        return f"{self.seccion.titulo} - {base}"


class PlantillaCondicionSeccion(models.Model):
    plantilla = models.ForeignKey(
        PlantillaCotizacion,
        on_delete=models.CASCADE,
        related_name='condiciones_secciones',
        verbose_name="Plantilla"
    )
    catalogo_seccion = models.ForeignKey(
        CatalogoCondicionSeccion,
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name='snapshots_plantilla',
        verbose_name="Sección de catálogo origen"
    )

    codigo = models.CharField(max_length=50, verbose_name="Código congelado")
    titulo = models.CharField(max_length=255, verbose_name="Título congelado")
    tipo = models.CharField(max_length=20, default='lista', verbose_name="Tipo congelado")
    orden = models.PositiveIntegerField(default=1, verbose_name="Orden")

    seleccionada = models.BooleanField(default=False, verbose_name="Seleccionada")

    fecha_creacion = models.DateTimeField(auto_now_add=True)
    fecha_actualizacion = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Plantilla - Sección de Condición"
        verbose_name_plural = "Plantilla - Secciones de Condiciones"
        ordering = ['orden', 'id']
        unique_together = [('plantilla', 'codigo')]
        indexes = [
            models.Index(fields=['plantilla', 'orden']),
            models.Index(fields=['plantilla', 'codigo']),
        ]

    def __str__(self):
        return f"{self.plantilla} - {self.titulo}"


class PlantillaCondicionItem(models.Model):
    seccion = models.ForeignKey(
        PlantillaCondicionSeccion,
        on_delete=models.CASCADE,
        related_name='items',
        verbose_name="Sección de plantilla"
    )
    catalogo_item = models.ForeignKey(
        CatalogoCondicionItem,
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name='snapshots_plantilla',
        verbose_name="Ítem de catálogo origen"
    )
    parent = models.ForeignKey(
        'self',
        on_delete=models.CASCADE,
        related_name='children',
        blank=True,
        null=True,
        verbose_name="Padre"
    )

    tipo_nodo = models.CharField(
        max_length=20,
        choices=CatalogoCondicionItem.TIPO_NODO_CHOICES,
        default='item',
        verbose_name="Tipo de nodo"
    )
    titulo = models.CharField(
        max_length=255,
        blank=True,
        null=True,
        verbose_name="Título congelado"
    )

    texto_base = models.TextField(verbose_name="Texto base copiado del catálogo")
    texto_final = models.TextField(verbose_name="Texto final de la plantilla")

    orden = models.PositiveIntegerField(default=1, verbose_name="Orden")
    nivel = models.PositiveSmallIntegerField(default=0, verbose_name="Nivel jerárquico")

    seleccionado = models.BooleanField(default=False, verbose_name="Seleccionado")
    es_obligatorio = models.BooleanField(default=False, verbose_name="Obligatorio")
    editable_en_cotizacion = models.BooleanField(default=True, verbose_name="Editable")
    fue_editado = models.BooleanField(default=False, verbose_name="¿Fue editado respecto al base?")

    fecha_creacion = models.DateTimeField(auto_now_add=True)
    fecha_actualizacion = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Plantilla - Ítem de Condición"
        verbose_name_plural = "Plantilla - Ítems de Condiciones"
        ordering = ['seccion__orden', 'orden', 'id']
        indexes = [
            models.Index(fields=['seccion', 'orden']),
            models.Index(fields=['parent', 'orden']),
            models.Index(fields=['seleccionado']),
        ]

    def clean(self):
        if self.parent and self.parent.seccion_id != self.seccion_id:
            raise ValidationError("El padre debe pertenecer a la misma sección de plantilla.")
        if self.parent and self.parent_id == self.id:
            raise ValidationError("Un ítem no puede ser padre de sí mismo.")

    def save(self, *args, **kwargs):
        if not self.texto_final:
            self.texto_final = self.texto_base
        self.fue_editado = (self.texto_base or '').strip() != (self.texto_final or '').strip()
        super().save(*args, **kwargs)

    def __str__(self):
        base = self.titulo or self.texto_final[:70]
        return f"{self.seccion.titulo} - {base}"
    
    

