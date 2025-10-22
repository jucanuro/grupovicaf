from django.shortcuts import render, redirect, get_object_or_404
from django.db.models import Q
from django.core.paginator import Paginator
from django.http import JsonResponse, HttpResponseForbidden
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required, user_passes_test 
from django.db import transaction, IntegrityError 
from .models import TrabajadorProfile

User = get_user_model()

# Función de permisos is_admin_or_supervisor (Requerida por user_passes_test)
# La he reconstruido basándome en el código que comentaste en el prompt original
def is_admin_or_supervisor(user):
    if user.is_superuser:
        return True
    
    try:
        profile = TrabajadorProfile.objects.get(user=user)
        return profile.role in ['Administrador', 'Supervisor']
    except TrabajadorProfile.DoesNotExist:
        return False


# VISTA: crear_trabajador (REQUIERE LOGIN)
@login_required 
@user_passes_test(is_admin_or_supervisor) 
def crear_trabajador(request):
    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')
        email = request.POST.get('email')
        nombre_completo = request.POST.get('nombre_completo')
        role = request.POST.get('role')
        titulo_profesional = request.POST.get('titulo_profesional')
        
        if not all([username, password, email, nombre_completo, role]):
            return render(request, 'trabajadores/trabajadores_form.html', {
                'error': 'Faltan campos obligatorios para la creación del usuario/perfil.'
            })
        
        try:
            with transaction.atomic():
                user = User.objects.create_user(
                    username=username, 
                    email=email, 
                    password=password,
                )
                
                TrabajadorProfile.objects.create(
                    user=user,
                    nombre_completo=nombre_completo,
                    role=role,
                    titulo_profesional=titulo_profesional,
                    correo_contacto=email,
                )
            
            return redirect('trabajadores:lista_trabajadores')
            
        except IntegrityError:
            return render(request, 'trabajadores/trabajadores_form.html', {
                'error': 'El nombre de usuario o el correo electrónico ya está en uso por otra persona.'
            })
        except Exception as e:
            return render(request, 'trabajadores/trabajadores_form.html', {
                'error': f'Ocurrió un error al crear el trabajador: {e}'
            })

    return render(request, 'trabajadores/trabajadores_form.html')

# -------------------------------------------------------------------------
# VISTA: editar_trabajador (REQUIERE LOGIN)
@login_required 
@user_passes_test(is_admin_or_supervisor) 
def editar_trabajador(request, pk):
    trabajador = get_object_or_404(TrabajadorProfile, pk=pk)
    
    if request.method == 'POST':
        username = request.POST.get('username')
        email = request.POST.get('email')
        new_password = request.POST.get('new_password')
        nombre_completo = request.POST.get('nombre_completo')
        role = request.POST.get('role')
        titulo_profesional = request.POST.get('titulo_profesional')

        if not all([username, email, nombre_completo, role]):
            return render(request, 'trabajadores/trabajadores_form.html', {
                'trabajador': trabajador,
                'error': 'Faltan campos obligatorios.'
            })

        try:
            with transaction.atomic():
                user = trabajador.user
                
                user.username = username
                user.email = email
                
                if new_password:
                    user.set_password(new_password)
                
                user.save()

                trabajador.nombre_completo = nombre_completo
                trabajador.role = role
                trabajador.titulo_profesional = titulo_profesional
                trabajador.correo_contacto = email
                
                trabajador.save()

            return redirect('trabajadores:lista_trabajadores')
        
        except IntegrityError:
            return render(request, 'trabajadores/trabajadores_form.html', {
                'trabajador': trabajador,
                'error': 'El nombre de usuario o el correo electrónico ya está en uso por otra persona.'
            })
        except Exception as e:
            return render(request, 'trabajadores/trabajadores_form.html', {
                'trabajador': trabajador,
                'error': f'Ocurrió un error al editar el trabajador: {e}'
            })

    context = {
        'trabajador': trabajador,
        'user_username': trabajador.user.username,
        'user_email': trabajador.user.email,
    }
    return render(request, 'trabajadores/trabajadores_form.html', context)

# -------------------------------------------------------------------------
# VISTA: eliminar_trabajador (REQUIERE LOGIN)
@login_required 
@user_passes_test(is_admin_or_supervisor) 
def eliminar_trabajador(request, pk):
    trabajador = get_object_or_404(TrabajadorProfile, pk=pk)
    
    if request.method == 'POST':
        trabajador.user.delete()
        return redirect('trabajadores:lista_trabajadores')
    
    return render(request, 'trabajadores/confirmar_eliminar_trabajador.html', {'trabajador': trabajador})

# -------------------------------------------------------------------------
# VISTAS DE LECTURA (PÚBLICAS)
def lista_trabajadores(request):
    query = request.GET.get('q')
    trabajadores = TrabajadorProfile.objects.select_related('user').all()

    if query:
        trabajadores = trabajadores.filter(
            Q(nombre_completo__icontains=query) |
            Q(role__icontains=query) |
            Q(user__username__icontains=query) |
            Q(user__email__icontains=query)
        ).distinct()

    paginator = Paginator(trabajadores, 5)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    context = {
        'trabajadores': page_obj,
        'query': query,
    }
    return render(request, 'trabajadores/trabajadores_list.html', context)


def buscar_trabajadores_api(request):
    query = request.GET.get('q', '')
    trabajadores = TrabajadorProfile.objects.filter(
        Q(nombre_completo__icontains=query) |
        Q(role__icontains=query) |
        Q(user__email__icontains=query)
    ).select_related('user').values(
        'pk', 
        'nombre_completo', 
        'role',
        'creado_en',
        'user__email',
        'user__username'
    )[:10]

    for trabajador in trabajadores:
        trabajador['creado_en'] = trabajador['creado_en'].strftime("%d %b %Y")
        trabajador['email'] = trabajador.pop('user__email')
        trabajador['username'] = trabajador.pop('user__username')

    return JsonResponse(list(trabajadores), safe=False)