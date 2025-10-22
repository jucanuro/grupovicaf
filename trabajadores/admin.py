from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth.models import User
from .models import TrabajadorProfile

# -----------------------------------------------------------
# 1. ADMIN INLINE: Integra el perfil en el formulario de User
# -----------------------------------------------------------
class TrabajadorProfileInline(admin.StackedInline):
    """Permite crear/editar el TrabajadorProfile al crear/editar un User."""
    model = TrabajadorProfile
    can_delete = False
    verbose_name_plural = 'Perfil del Trabajador'
    fk_name = 'user'
    
    fieldsets = (
        ('INFORMACIÓN PROFESIONAL Y ROL', {
            'fields': ('nombre_completo', 'role', 'titulo_profesional', 'firma_electronica', 'foto', 'linkedin')
        }),
        ('INFORMACIÓN DE CONTACTO', {
            'fields': ('telefono_contacto', 'correo_contacto')
        }),
        ('AUDITORÍA', {
            # Campos de solo lectura para la trazabilidad
            'fields': ('creado_en', 'actualizado_en'),
            'classes': ('collapse',),
        })
    )
    # Declaramos los campos de auditoría como solo lectura
    readonly_fields = ('creado_en', 'actualizado_en') 

# -----------------------------------------------------------
# 2. ADMIN para el modelo DJANGO USER (CUSTOM)
# -----------------------------------------------------------
class TrabajadorUserAdmin(BaseUserAdmin):
    """Sustituye el UserAdmin por defecto para inyectar el TrabajadorProfile."""
    inlines = (TrabajadorProfileInline,)
    
    # Mantenemos la redefinición del fieldsets para evitar el error admin.E012
    fieldsets = (
        (None, {'fields': ('username', 'password')}),
        ('Información Personal (Login)', {'fields': ('first_name', 'last_name', 'email')}),
        ('Permisos de Acceso', {
            'fields': ('is_active', 'is_staff', 'is_superuser',
                       'groups', 'user_permissions'),
        }),
        ('Fechas Importantes', {'fields': ('last_login', 'date_joined')}),
    )
    
    def get_inline_instances(self, request, obj=None):
        if not obj:
            return [TrabajadorProfileInline(self.model, self.admin_site)]
        return super().get_inline_instances(request, obj)


# -----------------------------------------------------------
# 3. ADMIN para el MODELO TrabajadorProfile (Gestión Directa)
# -----------------------------------------------------------
@admin.register(TrabajadorProfile)
class TrabajadorProfileAdmin(admin.ModelAdmin):
    """Permite la gestión directa de los perfiles."""
    list_display = (
        'nombre_completo', 
        'role', 
        'user_username', 
        'correo_contacto', 
        'user_is_active', 
        'creado_en'
    )
    
    list_filter = ('role', 'creado_en', 'user__is_active')
    search_fields = (
        'nombre_completo', 
        'user__username', 
        'correo_contacto', 
        'user__email'
    )
    
    fieldsets = (
        ('USUARIO DE LOGIN', {
            'fields': ('user',),
        }),
        ('INFORMACIÓN PROFESIONAL Y ROL', {
            'fields': ('nombre_completo', 'titulo_profesional', 'role', 'firma_electronica', 'foto', 'linkedin')
        }),
        ('INFORMACIÓN DE CONTACTO', {
            'fields': ('telefono_contacto', 'correo_contacto')
        }),
        ('AUDITORÍA', {
            # Sección de Auditoría para la vista de edición directa
            'fields': ('creado_en', 'actualizado_en'),
            'classes': ('collapse',),
        })
    )
    
    # Declaramos los campos de auditoría como solo lectura
    readonly_fields = ('creado_en', 'actualizado_en') 

    def user_username(self, obj):
        return obj.user.username
    user_username.short_description = 'Usuario de Sistema'

    def user_is_active(self, obj):
        return obj.user.is_active
    user_is_active.short_description = 'Activo'
    user_is_active.boolean = True


# -----------------------------------------------------------
# 4. REGISTRO FINAL
# -----------------------------------------------------------
admin.site.unregister(User)
admin.site.register(User, TrabajadorUserAdmin)