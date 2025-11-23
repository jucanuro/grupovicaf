from django.db import models
from django.conf import settings
from django.utils import timezone

class TrabajadorProfile(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, verbose_name="Usuario de Sistema")

    ROLES = [
        ('ADMIN', 'Administrador de Sistema'), 
        ('JEFE_LAB', 'Jefe de Laboratorio'), 
        ('SUPERVISOR', 'Supervisor de Laboratorio'), 
        ('TECNICO', 'Técnico de Laboratorio/Ejecutor'),
        ('COMERCIAL', 'Gerente Comercial/Administrativo'), 
    ]
    nombre_completo = models.CharField(max_length=255, verbose_name="Nombre Completo")
    titulo_profesional = models.CharField(max_length=50, blank=True, null=True, verbose_name="Título Profesional (Ej: Ing., Bach.)")
    role = models.CharField(max_length=20, choices=ROLES, default='TECNICO', verbose_name="Rol en el Sistema")
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
        return f"{self.get_nombre_formal()} ({self.get_role_display()})"

    class Meta:
        verbose_name = "Perfil de Trabajador"
        verbose_name_plural = "Perfiles de Trabajadores"
        ordering = ['nombre_completo']
