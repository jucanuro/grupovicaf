from django.db import models
from django.conf import settings
from django.utils import timezone

class RolTrabajador(models.Model):
    nombre = models.CharField(max_length=50, unique=True, verbose_name="Nombre del Rol")
    descripcion = models.TextField(blank=True, null=True, verbose_name="Descripción de Responsabilidades")

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
        # Nota: aquí quitamos el .get_role_display() porque ahora es un objeto
        return f"{self.get_nombre_formal()} ({self.rol.nombre})"

    class Meta:
        verbose_name = "Perfil de Trabajador"
        verbose_name_plural = "Perfiles de Trabajadores"
        ordering = ['nombre_completo']