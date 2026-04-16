from django.shortcuts import render, redirect, get_object_or_404
from django.db.models import Count, Q
from django.core.paginator import Paginator
from django.http import JsonResponse, HttpResponseForbidden
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required, user_passes_test
from django.db import transaction, IntegrityError
from django.contrib import messages
import logging
from .models import TrabajadorProfile, RolTrabajador

logger = logging.getLogger(__name__)
User = get_user_model()


def is_admin_or_supervisor(user):
    if user.is_superuser:
        return True

    try:
        profile = TrabajadorProfile.objects.select_related('rol').get(user=user)
        nombre_rol = (profile.rol.nombre or '').lower()
        return 'administrador' in nombre_rol or 'supervisor' in nombre_rol
    except (TrabajadorProfile.DoesNotExist, AttributeError):
        return False


@login_required
@user_passes_test(is_admin_or_supervisor)
def crear_trabajador(request):
    roles_disponibles = RolTrabajador.objects.all().order_by('nombre')

    if request.method == 'POST':
        username = request.POST.get('username', '').strip()
        password = request.POST.get('password', '')
        email = request.POST.get('email', '').strip()
        nombre_completo = request.POST.get('nombre_completo', '').strip()
        rol_id = request.POST.get('rol', '').strip()
        titulo_profesional = request.POST.get('titulo_profesional', '').strip()

        context = {
            'roles_disponibles': roles_disponibles,
            'user_username': username,
            'user_email': email,
            'form_nombre_completo': nombre_completo,
            'form_titulo_profesional': titulo_profesional,
            'form_rol_id': rol_id,
        }

        if not all([username, password, email, nombre_completo, rol_id]):
            context['error'] = 'Faltan campos obligatorios para la creación del usuario/perfil.'
            return render(request, 'trabajadores/trabajadores_form.html', context)

        try:
            rol_obj = RolTrabajador.objects.get(id=rol_id)
        except RolTrabajador.DoesNotExist:
            context['error'] = 'El rol seleccionado no existe.'
            return render(request, 'trabajadores/trabajadores_form.html', context)

        try:
            with transaction.atomic():
                user = User.objects.create_user(
                    username=username,
                    email=email,
                    password=password,
                )

                perfil = TrabajadorProfile.objects.create(
                    user=user,
                    nombre_completo=nombre_completo,
                    rol=rol_obj,
                    titulo_profesional=titulo_profesional,
                    correo_contacto=email,
                )

            messages.success(request, f'El colaborador "{perfil.nombre_completo}" fue creado correctamente.')
            return redirect('trabajadores:editar_trabajador', pk=perfil.pk)

        except IntegrityError:
            context['error'] = 'El nombre de usuario o el correo electrónico ya está en uso por otra persona.'
            return render(request, 'trabajadores/trabajadores_form.html', context)
        except Exception as e:
            logger.exception("Error al crear trabajador")
            context['error'] = f'Ocurrió un error al crear el trabajador: {e}'
            return render(request, 'trabajadores/trabajadores_form.html', context)

    return render(request, 'trabajadores/trabajadores_form.html', {
        'roles_disponibles': roles_disponibles
    })


@login_required
@user_passes_test(is_admin_or_supervisor)
def editar_trabajador(request, pk):
    trabajador = get_object_or_404(
        TrabajadorProfile.objects.select_related('user', 'rol'),
        pk=pk
    )
    roles_disponibles = RolTrabajador.objects.all().order_by('nombre')

    if request.method == 'POST':
        username = request.POST.get('username', '').strip()
        email = request.POST.get('email', '').strip()
        new_password = request.POST.get('new_password', '')
        nombre_completo = request.POST.get('nombre_completo', '').strip()
        rol_id = request.POST.get('rol', '').strip()
        titulo_profesional = request.POST.get('titulo_profesional', '').strip()

        context = {
            'trabajador': trabajador,
            'roles_disponibles': roles_disponibles,
            'user_username': username,
            'user_email': email,
            'form_nombre_completo': nombre_completo,
            'form_titulo_profesional': titulo_profesional,
            'form_rol_id': rol_id,
        }

        if not all([username, email, nombre_completo, rol_id]):
            context['error'] = 'Faltan campos obligatorios.'
            return render(request, 'trabajadores/trabajadores_form.html', context)

        try:
            rol_obj = RolTrabajador.objects.get(id=rol_id)
        except RolTrabajador.DoesNotExist:
            context['error'] = 'El rol seleccionado no existe.'
            return render(request, 'trabajadores/trabajadores_form.html', context)

        try:
            with transaction.atomic():
                user = trabajador.user
                user.username = username
                user.email = email

                if new_password:
                    user.set_password(new_password)

                user.save()

                trabajador.nombre_completo = nombre_completo
                trabajador.rol = rol_obj
                trabajador.titulo_profesional = titulo_profesional
                trabajador.correo_contacto = email
                trabajador.save()

            messages.success(request, f'El perfil de "{trabajador.nombre_completo}" fue actualizado correctamente.')
            return redirect('trabajadores:editar_trabajador', pk=trabajador.pk)

        except IntegrityError:
            context['error'] = 'El nombre de usuario o el correo electrónico ya está en uso por otra persona.'
            return render(request, 'trabajadores/trabajadores_form.html', context)
        except Exception as e:
            logger.exception("Error al editar trabajador")
            context['error'] = f'Ocurrió un error al editar el trabajador: {e}'
            return render(request, 'trabajadores/trabajadores_form.html', context)

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
        messages.success(request, f'El colaborador "{trabajador.nombre_completo}" fue eliminado correctamente.')
        return redirect('trabajadores:lista_trabajadores')

    return render(request, 'trabajadores/confirmar_eliminar_trabajador.html', {'trabajador': trabajador})


@login_required
@user_passes_test(is_admin_or_supervisor)
def lista_trabajadores(request):
    query = request.GET.get('q', '').strip()
    trabajadores = TrabajadorProfile.objects.select_related('user', 'rol').all().order_by('nombre_completo')

    if query:
        trabajadores = trabajadores.filter(
            Q(nombre_completo__icontains=query) |
            Q(rol__nombre__icontains=query) |
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


@login_required
@user_passes_test(is_admin_or_supervisor)
def buscar_trabajadores_api(request):
    try:
        query = request.GET.get('q', '').strip()

        if len(query) > 100:
            return JsonResponse({'error': 'La consulta no puede exceder 100 caracteres.'}, status=400)

        import re
        if re.search(r'[<>]', query):
            logger.warning(f"Intento de XSS en buscar_trabajadores_api por usuario {request.user.username}")
            return JsonResponse({'error': 'Caracteres no permitidos detectados.'}, status=400)

        trabajadores = TrabajadorProfile.objects.filter(
            Q(nombre_completo__icontains=query) |
            Q(rol__nombre__icontains=query) |
            Q(user__email__icontains=query)
        ).select_related('user', 'rol').values(
            'pk',
            'nombre_completo',
            'rol__nombre',
            'creado_en',
            'user__email',
            'user__username'
        )[:10]

        result = []
        for t in trabajadores:
            result.append({
                'pk': t['pk'],
                'nombre_completo': t['nombre_completo'],
                'role': t['rol__nombre'],
                'creado_en': t['creado_en'].strftime("%d %b %Y"),
                'email': t['user__email'],
                'username': t['user__username']
            })

        if len(query) > 50:
            logger.info(f"Consulta larga en buscar_trabajadores_api por usuario {request.user.username}: {query[:50]}...")

        return JsonResponse(result, safe=False)
    except Exception as e:
        logger.error(f"Error en buscar_trabajadores_api por usuario {request.user.username}: {str(e)}")
        return JsonResponse({'error': 'Error interno del servidor.'}, status=500)


@login_required
@user_passes_test(is_admin_or_supervisor)
def crear_rol_ajax(request):
    if request.method == 'POST':
        try:
            nombre = request.POST.get('nombre_rol', '').strip()
            descripcion = request.POST.get('descripcion_rol', '').strip()

            if not nombre or len(nombre) < 2 or len(nombre) > 50:
                return JsonResponse({'success': False, 'error': 'El nombre del rol debe tener entre 2 y 50 caracteres.'}, status=400)

            if len(descripcion) > 200:
                return JsonResponse({'success': False, 'error': 'La descripción no puede exceder 200 caracteres.'}, status=400)

            import re
            if re.search(r'[<>]', nombre) or re.search(r'[<>]', descripcion):
                logger.warning(f"Intento de XSS en crear_rol_ajax por usuario {request.user.username}")
                return JsonResponse({'success': False, 'error': 'Caracteres no permitidos detectados.'}, status=400)

            nuevo_rol = RolTrabajador.objects.create(
                nombre=nombre,
                descripcion=descripcion
            )

            logger.info(f"Rol creado exitosamente: {nombre} por usuario {request.user.username}")

            return JsonResponse({
                'success': True,
                'id': nuevo_rol.id,
                'nombre': nuevo_rol.nombre
            })
        except IntegrityError:
            return JsonResponse({'success': False, 'error': 'Este rol ya existe.'}, status=400)
        except Exception as e:
            logger.error(f"Error al crear rol por usuario {request.user.username}: {str(e)}")
            return JsonResponse({'success': False, 'error': 'Error interno del servidor.'}, status=500)

    return JsonResponse({'success': False, 'error': 'Método no permitido.'}, status=405)


@login_required
@user_passes_test(is_admin_or_supervisor)
def lista_roles(request):
    query = request.GET.get('q', '').strip()

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


@login_required
@user_passes_test(is_admin_or_supervisor)
def crear_rol(request):
    if request.method == 'POST':
        nombre = request.POST.get('nombre', '').strip()
        descripcion = request.POST.get('descripcion', '').strip()

        if nombre:
            try:
                RolTrabajador.objects.create(
                    nombre=nombre,
                    descripcion=descripcion
                )
                messages.success(request, f'El rol "{nombre}" ha sido creado correctamente.')
                return redirect('trabajadores:lista_roles')
            except IntegrityError:
                messages.error(request, 'Ya existe un rol con ese nombre.')
            except Exception as e:
                logger.exception("Error al crear rol")
                messages.error(request, f'Error al crear el rol: {e}')
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
        nombre = request.POST.get('nombre', '').strip()
        descripcion = request.POST.get('descripcion', '').strip()

        if not nombre:
            messages.error(request, 'El nombre del rol es obligatorio.')
            return render(request, 'trabajadores/rol_form.html', {
                'rol': rol,
                'titulo_pagina': f'Editando Rol: {rol.nombre}',
            })

        try:
            rol.nombre = nombre
            rol.descripcion = descripcion
            rol.save()
            messages.success(request, f'Rol "{rol.nombre}" actualizado.')
            return redirect('trabajadores:lista_roles')
        except IntegrityError:
            messages.error(request, 'Ya existe un rol con ese nombre.')
        except Exception as e:
            logger.exception("Error al editar rol")
            messages.error(request, f'Error al editar el rol: {e}')

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
        try:
            nombre_eliminado = rol.nombre
            rol.delete()
            messages.success(request, f'El rol "{nombre_eliminado}" ha sido eliminado correctamente.')
        except Exception as e:
            logger.exception("Error al eliminar rol")
            messages.error(request, f'Error al eliminar el rol: {e}')

    return redirect('trabajadores:lista_roles')