from django.shortcuts import render, redirect, get_object_or_404
from django.db.models import Count, Q
from django.core.paginator import Paginator
from django.http import JsonResponse, HttpResponseForbidden
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required, user_passes_test 
from django.db import transaction, IntegrityError 
from .models import TrabajadorProfile, RolTrabajador  

User = get_user_model()

def is_admin_or_supervisor(user):
    if user.is_superuser:
        return True
    
    try:
        profile = TrabajadorProfile.objects.get(user=user)
        nombre_rol = profile.rol.nombre.lower()
        return 'administrador' in nombre_rol or 'supervisor' in nombre_rol
    except (TrabajadorProfile.DoesNotExist, AttributeError):
        return False

@login_required 
@user_passes_test(is_admin_or_supervisor) 
def crear_trabajador(request):
    # Obtenemos los roles para el select del template
    roles_disponibles = RolTrabajador.objects.all()
    
    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')
        email = request.POST.get('email')
        nombre_completo = request.POST.get('nombre_completo')
        rol_id = request.POST.get('rol') # Ahora recibimos el ID del RolTrabajador
        titulo_profesional = request.POST.get('titulo_profesional')
        
        if not all([username, password, email, nombre_completo, rol_id]):
            return render(request, 'trabajadores/trabajadores_form.html', {
                'error': 'Faltan campos obligatorios para la creación del usuario/perfil.',
                'roles_disponibles': roles_disponibles
            })
        
        try:
            with transaction.atomic():
                user = User.objects.create_user(
                    username=username, 
                    email=email, 
                    password=password,
                )
                
                # Obtenemos la instancia del rol seleccionado
                rol_obj = RolTrabajador.objects.get(id=rol_id)
                
                TrabajadorProfile.objects.create(
                    user=user,
                    nombre_completo=nombre_completo,
                    rol=rol_obj, # Asignamos el objeto rol
                    titulo_profesional=titulo_profesional,
                    correo_contacto=email,
                )
            
            return redirect('trabajadores:lista_trabajadores')
            
        except IntegrityError:
            return render(request, 'trabajadores/trabajadores_form.html', {
                'error': 'El nombre de usuario o el correo electrónico ya está en uso por otra persona.',
                'roles_disponibles': roles_disponibles
            })
        except Exception as e:
            return render(request, 'trabajadores/trabajadores_form.html', {
                'error': f'Ocurrió un error al crear el trabajador: {e}',
                'roles_disponibles': roles_disponibles
            })

    return render(request, 'trabajadores/trabajadores_form.html', {
        'roles_disponibles': roles_disponibles
    })

@login_required 
@user_passes_test(is_admin_or_supervisor) 
def editar_trabajador(request, pk):
    trabajador = get_object_or_404(TrabajadorProfile, pk=pk)
    roles_disponibles = RolTrabajador.objects.all()
    
    if request.method == 'POST':
        username = request.POST.get('username')
        email = request.POST.get('email')
        new_password = request.POST.get('new_password')
        nombre_completo = request.POST.get('nombre_completo')
        rol_id = request.POST.get('rol') # ID del RolTrabajador
        titulo_profesional = request.POST.get('titulo_profesional')

        if not all([username, email, nombre_completo, rol_id]):
            return render(request, 'trabajadores/trabajadores_form.html', {
                'trabajador': trabajador,
                'error': 'Faltan campos obligatorios.',
                'roles_disponibles': roles_disponibles
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
                trabajador.rol = RolTrabajador.objects.get(id=rol_id) # Actualizamos el objeto rol
                trabajador.titulo_profesional = titulo_profesional
                trabajador.correo_contacto = email
                
                trabajador.save()

            return redirect('trabajadores:lista_trabajadores')
        
        except IntegrityError:
            return render(request, 'trabajadores/trabajadores_form.html', {
                'trabajador': trabajador,
                'error': 'El nombre de usuario o el correo electrónico ya está en uso por otra persona.',
                'roles_disponibles': roles_disponibles
            })
        except Exception as e:
            return render(request, 'trabajadores/trabajadores_form.html', {
                'trabajador': trabajador,
                'error': f'Ocurrió un error al editar el trabajador: {e}',
                'roles_disponibles': roles_disponibles
            })

    context = {
        'trabajador': trabajador,
        'roles_disponibles': roles_disponibles,
        'user_username': trabajador.user.username,
        'user_email': trabajador.user.email,
    }
    return render(request, 'trabajadores/trabajadores_form.html', context)

@login_required 
@user_passes_test(is_admin_or_supervisor) 
def eliminar_trabajador(request, pk):
    trabajador = get_object_or_404(TrabajadorProfile, pk=pk)
    
    if request.method == 'POST':
        trabajador.user.delete()
        return redirect('trabajadores:lista_trabajadores')
    
    return render(request, 'trabajadores/confirmar_eliminar_trabajador.html', {'trabajador': trabajador})

def lista_trabajadores(request):
    query = request.GET.get('q')
    # select_related('rol') agregado para optimizar la consulta
    trabajadores = TrabajadorProfile.objects.select_related('user', 'rol').all()

    if query:
        trabajadores = trabajadores.filter(
            Q(nombre_completo__icontains=query) |
            Q(rol__nombre__icontains=query) | # Cambiado a rol__nombre
            Q(user__username__icontains=query) |
            Q(user__email__icontains=query)
        ).distinct()

    paginator = Paginator(trabajadores, 7)
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
        Q(rol__nombre__icontains=query) | # Cambiado a rol__nombre
        Q(user__email__icontains=query)
    ).select_related('user', 'rol').values(
        'pk', 
        'nombre_completo', 
        'rol__nombre', # Traemos el nombre del rol relacionado
        'creado_en',
        'user__email',
        'user__username'
    )[:10]

    result = []
    for t in trabajadores:
        result.append({
            'pk': t['pk'],
            'nombre_completo': t['nombre_completo'],
            'role': t['rol__nombre'], # Mapeado a 'role' para no romper el JS
            'creado_en': t['creado_en'].strftime("%d %b %Y"),
            'email': t['user__email'],
            'username': t['user__username']
        })

    return JsonResponse(result, safe=False)


@login_required
@user_passes_test(is_admin_or_supervisor)
def crear_rol_ajax(request):
    if request.method == 'POST':
        nombre = request.POST.get('nombre_rol')
        descripcion = request.POST.get('descripcion_rol', '')

        if not nombre:
            return JsonResponse({'success': False, 'error': 'El nombre del rol es obligatorio.'}, status=400)

        try:
            nuevo_rol = RolTrabajador.objects.create(
                nombre=nombre,
                descripcion=descripcion
            )
            return JsonResponse({
                'success': True,
                'id': nuevo_rol.id,
                'nombre': nuevo_rol.nombre
            })
        except IntegrityError:
            return JsonResponse({'success': False, 'error': 'Este rol ya existe.'}, status=400)
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)}, status=500)

    return JsonResponse({'success': False, 'error': 'Método no permitido.'}, status=405)


@login_required
@user_passes_test(is_admin_or_supervisor)
def lista_roles(request):
    query = request.GET.get('q')
    
    roles = RolTrabajador.objects.annotate(
        num_trabajadores=Count('perfiles') 
    ).all().order_by('nombre')

    if query:
        roles = roles.filter(
            Q(nombre__icontains=query) |
            Q(descripcion__icontains=query)
        ).distinct()

    paginator = Paginator(roles, 10)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    context = {
        'roles': page_obj,
        'query': query,
    }
    return render(request, 'trabajadores/roles_list.html', context)

from django.shortcuts import render, redirect
from django.contrib import messages
from .models import RolTrabajador

@login_required
@user_passes_test(is_admin_or_supervisor)
def crear_rol(request):
    if request.method == 'POST':
        nombre = request.POST.get('nombre')
        descripcion = request.POST.get('descripcion')
        
        if nombre:
            # Crear el objeto
            RolTrabajador.objects.create(
                nombre=nombre,
                descripcion=descripcion
            )
            messages.success(request, f'El rol "{nombre}" ha sido creado correctamente.')
            return redirect('trabajadores:lista_roles')
        else:
            messages.error(request, 'El nombre del rol es obligatorio.')

    return render(request, 'trabajadores/rol_form.html', {
        'titulo_pagina': 'Crear Nuevo Rol',
        'icono': 'shield-plus'
    })
    
@login_required
@user_passes_test(is_admin_or_supervisor)
def editar_rol(request, pk):
    rol = get_object_or_404(RolTrabajador, pk=pk)
    if request.method == 'POST':
        rol.nombre = request.POST.get('nombre')
        rol.descripcion = request.POST.get('descripcion')
        rol.save()
        messages.success(request, f'Rol "{rol.nombre}" actualizado.')
        return redirect('trabajadores:lista_roles')
    
    return render(request, 'trabajadores/rol_form.html', {
        'rol': rol,
        'titulo_pagina': f'Editando Rol: {rol.nombre}',
    })
    
@login_required
@user_passes_test(is_admin_or_supervisor)
def eliminar_rol(request, pk):
    rol = get_object_or_404(RolTrabajador, pk=pk)
    
    if rol.perfiles.exists():
        messages.error(request, f'No se puede eliminar el rol "{rol.nombre}" porque tiene trabajadores asociados.')
    else:
        nombre_eliminado = rol.nombre
        rol.delete()
        messages.success(request, f'El rol "{nombre_eliminado}" ha sido eliminado correctamente.')
    
    return redirect('trabajadores:lista_roles')