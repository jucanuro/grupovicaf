from django.db import models
from django.conf import settings
from django.utils import timezone

class TrabajadorProfile(models.Model):
    # Relación uno a uno con el modelo de usuario por defecto de Django
    # Esto asegura que cada usuario (para login) tenga un perfil de trabajador asociado.
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, verbose_name="Usuario de Sistema")

    # Definición de Roles Clave basados en el flujo del proyecto
    ROLES = [
        ('ADMIN', 'Administrador de Sistema'), # Acceso completo
        ('JEFE_LAB', 'Jefe de Laboratorio'), # Aprobación final (JL/Jessica Riojas)
        ('SUPERVISOR', 'Supervisor de Laboratorio'), # Validación de datos (Frank Gonzáles)
        ('TECNICO', 'Técnico de Laboratorio/Ejecutor'), # Ingreso de resultados
        ('COMERCIAL', 'Gerente Comercial/Administrativo'), # Pagos y Facturación (Carmen Bernui)
    ]

    # --- Información Personal y de Contacto ---
    nombre_completo = models.CharField(max_length=255, verbose_name="Nombre Completo")
    
    # Campo para el título/cargo que se usa en documentos (ej: Ing., Bach., Gerente)
    titulo_profesional = models.CharField(max_length=50, blank=True, null=True, verbose_name="Título Profesional (Ej: Ing., Bach.)")
    
    # Rol dentro de la jerarquía del sistema
    role = models.CharField(max_length=20, choices=ROLES, default='TECNICO', verbose_name="Rol en el Sistema")
    
    # Datos de contacto adicionales para coordinaciones (como en el VCF-OTE-2025-371)
    telefono_contacto = models.CharField(max_length=20, blank=True, null=True, verbose_name="Teléfono de Contacto")
    correo_contacto = models.EmailField(blank=True, null=True, verbose_name="Correo de Contacto")
    
    # --- Archivos y Documentación ---
    foto = models.ImageField(upload_to='trabajadores_fotos/', blank=True, null=True, verbose_name="Foto de Perfil")
    firma_electronica = models.ImageField(upload_to='firmas/', blank=True, null=True, verbose_name="Firma Electrónica para Informes")
    linkedin = models.URLField(blank=True, null=True, verbose_name="URL de LinkedIn")

    # --- Trazabilidad ---
    creado_en = models.DateTimeField(auto_now_add=True, verbose_name="Fecha de Creación")
    actualizado_en = models.DateTimeField(auto_now=True, verbose_name="Última Actualización")

    def get_nombre_formal(self):
        """Retorna el nombre con el título profesional para documentos (ej: Ing. Jessica Riojas Ortiz)"""
        if self.titulo_profesional:
            return f"{self.titulo_profesional}. {self.nombre_completo}"
        return self.nombre_completo

    def __str__(self):
        return f"{self.get_nombre_formal()} ({self.get_role_display()})"

    class Meta:
        verbose_name = "Perfil de Trabajador"
        verbose_name_plural = "Perfiles de Trabajadores"
        ordering = ['nombre_completo']
