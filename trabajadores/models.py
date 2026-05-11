from django.db import models
from django.conf import settings
from django.utils.text import slugify
from django.utils import timezone


class ModuloSistema(models.Model):
    nombre = models.CharField(max_length=100, unique=True, verbose_name="Nombre del Módulo")
    codigo = models.SlugField(max_length=100, unique=True, blank=True, verbose_name="Código")
    descripcion = models.TextField(blank=True, null=True, verbose_name="Descripción")
    icono = models.CharField(max_length=50, blank=True, null=True, verbose_name="Icono Lucide")
    orden = models.PositiveIntegerField(default=0, verbose_name="Orden")
    activo = models.BooleanField(default=True, verbose_name="Activo")
    creado_en = models.DateTimeField(auto_now_add=True)
    actualizado_en = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Módulo del Sistema"
        verbose_name_plural = "Módulos del Sistema"
        ordering = ['orden', 'nombre']

    def save(self, *args, **kwargs):
        from django.utils.text import slugify
        if not self.codigo:
            self.codigo = slugify(self.nombre).replace('-', '_')
        super().save(*args, **kwargs)

    def __str__(self):
        return self.nombre


class AccionPermiso(models.Model):
    nombre = models.CharField(max_length=100, unique=True, verbose_name="Nombre de Acción")
    codigo = models.SlugField(max_length=100, unique=True, blank=True, verbose_name="Código")
    descripcion = models.TextField(blank=True, null=True, verbose_name="Descripción")
    orden = models.PositiveIntegerField(default=0, verbose_name="Orden")
    activo = models.BooleanField(default=True, verbose_name="Activo")
    creado_en = models.DateTimeField(auto_now_add=True)
    actualizado_en = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Acción de Permiso"
        verbose_name_plural = "Acciones de Permisos"
        ordering = ['orden', 'nombre']

    def save(self, *args, **kwargs):
        from django.utils.text import slugify
        if not self.codigo:
            self.codigo = slugify(self.nombre).replace('-', '_')
        super().save(*args, **kwargs)

    def __str__(self):
        return self.nombre


class PermisoModulo(models.Model):
    modulo_sistema = models.ForeignKey(
        ModuloSistema,
        on_delete=models.PROTECT,
        related_name="permisos",
        verbose_name="Módulo del Sistema"
    )

    accion = models.ForeignKey(
        AccionPermiso,
        on_delete=models.PROTECT,
        related_name="permisos",
        verbose_name="Acción"
    )

    codigo = models.CharField(
        max_length=150,
        unique=True,
        editable=False,
        verbose_name="Código"
    )

    nombre = models.CharField(
        max_length=150,
        editable=False,
        verbose_name="Nombre del Permiso"
    )

    descripcion = models.TextField(
        blank=True,
        null=True,
        verbose_name="Descripción"
    )

    activo = models.BooleanField(
        default=True,
        verbose_name="Activo"
    )

    creado_en = models.DateTimeField(auto_now_add=True)
    actualizado_en = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Permiso de Módulo"
        verbose_name_plural = "Permisos de Módulo"
        ordering = [
            'modulo_sistema__orden',
            'modulo_sistema__nombre',
            'accion__orden',
            'accion__nombre'
        ]
        unique_together = ('modulo_sistema', 'accion')

    def save(self, *args, **kwargs):
        self.codigo = f"{self.modulo_sistema.codigo}.{self.accion.codigo}"
        self.nombre = f"{self.accion.nombre} {self.modulo_sistema.nombre}"

        super().save(*args, **kwargs)

    def __str__(self):
        return self.nombre

class RolTrabajador(models.Model):
    nombre = models.CharField(max_length=50, unique=True, verbose_name="Nombre del Rol")
    descripcion = models.TextField(blank=True, null=True, verbose_name="Descripción de Responsabilidades")
    permisos = models.ManyToManyField(
        PermisoModulo,
        blank=True,
        related_name="roles",
        verbose_name="Permisos del Rol"
    )

    class Meta:
        verbose_name = "Rol del Trabajador"
        verbose_name_plural = "Roles del Trabajador"
        ordering = ['nombre']

    def __str__(self):
        return self.nombre
    
class TrabajadorProfile(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, verbose_name="Usuario de Sistema")
    
    rol = models.ForeignKey(RolTrabajador, on_delete=models.PROTECT, related_name="perfiles", verbose_name="Rol en el Sistema")
    
    nombre_completo = models.CharField(max_length=255, verbose_name="Nombre Completo")
    titulo_profesional = models.CharField(max_length=50, blank=True, null=True, verbose_name="Título Profesional (Ej: Ing., Bach.)")
    telefono_contacto = models.CharField(max_length=20, blank=True, null=True, verbose_name="Teléfono de Contacto")
    correo_contacto = models.EmailField(blank=True, null=True, verbose_name="Correo de Contacto")
    foto = models.ImageField(upload_to='trabajadores_fotos/', blank=True, null=True, verbose_name="Foto de Perfil")
    firma_electronica = models.ImageField(upload_to='firmas/', blank=True, null=True, verbose_name="Firma Electrónica para Informes")
    linkedin = models.URLField(blank=True, null=True, verbose_name="URL de LinkedIn")
    creado_en = models.DateTimeField(auto_now_add=True, verbose_name="Fecha de Creación")
    actualizado_en = models.DateTimeField(auto_now=True, verbose_name="Última Actualización")

    def get_nombre_formal(self):
        if self.titulo_profesional:
            return f"{self.titulo_profesional}. {self.nombre_completo}"
        return self.nombre_completo

    def __str__(self):
        return f"{self.get_nombre_formal()} ({self.rol.nombre})"

    class Meta:
        verbose_name = "Perfil de Trabajador"
        verbose_name_plural = "Perfiles de Trabajadores"
        ordering = ['nombre_completo']
        
        
