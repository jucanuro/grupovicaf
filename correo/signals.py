from django.db.models.signals import post_save
from django.dispatch import receiver

from .models import CuentaCorreo


@receiver(post_save, sender=CuentaCorreo)
def crear_carpetas_del_sistema(sender, instance, created, **kwargs):
    if created:
        from .mensajeria import asegurar_carpetas
        asegurar_carpetas(instance)
