from django.contrib import admin

from .models import VistaAnalisis


@admin.register(VistaAnalisis)
class VistaAnalisisAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'conjunto', 'usuario', 'creada_en')
    list_filter = ('conjunto',)
    search_fields = ('nombre', 'usuario__username')
