from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required, user_passes_test
from django.views.decorators.http import require_POST
from django.contrib import messages
from django.db.models import Q
from django.db import IntegrityError
from django.core.paginator import Paginator
from django.http import JsonResponse
import logging
from .models import Cliente 

logger = logging.getLogger(__name__) 

def is_admin_or_supervisor(user):
    """Verifica si el usuario es un administrador o supervisor del sistema."""
    return user.is_active and user.is_staff 

@login_required
@user_passes_test(is_admin_or_supervisor)
def lista_clientes(request):
    """Muestra el listado de todos los clientes con paginación y búsqueda."""
    
    query = request.GET.get('q')
    clientes = Cliente.objects.all().select_related('creado_por').order_by('-creado_en') 

    if query:
        clientes = clientes.filter(
            Q(codigo_confidencial__icontains=query) | 
            Q(razon_social__icontains=query) |
            Q(ruc__icontains=query) |
            Q(persona_contacto__icontains=query) |
            Q(correo_contacto__icontains=query)
        ).distinct()

    paginator = Paginator(clientes, 7) 
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    context = {
        'clientes': page_obj,  
        'query': query,
    }
    return render(request, 'clientes/clientes_list.html', context)

@login_required
@user_passes_test(is_admin_or_supervisor)
def buscar_clientes_api(request):
    """Devuelve un JSON con los resultados de búsqueda de clientes incluyendo ID y Logo."""
    try:
        query = request.GET.get('q', '').strip()

        # Validaciones de seguridad
        if len(query) > 100:
            return JsonResponse({'error': 'La consulta no puede exceder 100 caracteres.'}, status=400)
        
        # Validar caracteres peligrosos
        import re
        if re.search(r'[<>]', query):
            logger.warning(f"Intento de XSS en buscar_clientes_api por usuario {request.user.username}")
            return JsonResponse({'error': 'Caracteres no permitidos detectados.'}, status=400)

        clientes_qs = Cliente.objects.filter( 
            Q(codigo_confidencial__icontains=query) | 
            Q(razon_social__icontains=query) |
            Q(ruc__icontains=query) |
            Q(persona_contacto__icontains=query) |
            Q(correo_contacto__icontains=query)
        ).only( 
            'pk', 'codigo_confidencial', 'razon_social', 'ruc', 
            'persona_contacto', 'correo_contacto', 'creado_en', 'logo_empresa'
        )[:10]

        resultados = []
        for cliente in clientes_qs:
            resultados.append({
                'pk': cliente.pk,
                'codigo_confidencial': cliente.codigo_confidencial,
                'razon_social': cliente.razon_social,
                'ruc': cliente.ruc,
                'persona_contacto': cliente.persona_contacto,
                'correo_contacto': cliente.correo_contacto,
                'creado_en': cliente.creado_en.strftime("%d %b %Y") if cliente.creado_en else 'N/A',
                'logo_url': cliente.logo_empresa.url if cliente.logo_empresa else None,
            })

        # Log de seguridad para consultas potencialmente sospechosas
        if len(query) > 50:
            logger.info(f"Consulta larga en buscar_clientes_api por usuario {request.user.username}: {query[:50]}...")
        
        return JsonResponse(resultados, safe=False)
    except Exception as e:
        logger.error(f"Error en buscar_clientes_api por usuario {request.user.username}: {str(e)}")
        return JsonResponse({'error': 'Error interno del servidor.'}, status=500)

@login_required
@user_passes_test(is_admin_or_supervisor)
def crear_editar_cliente(request, pk=None):
    """Permite crear un nuevo cliente o editar uno existente incorporando logo y firma."""
    cliente = None
    if pk:
        cliente = get_object_or_404(Cliente, pk=pk)

    errors = {}
    data_cliente = cliente if cliente else {}

    if request.method == 'POST':
        data_cliente = request.POST.copy()
        
        ruc = request.POST.get('ruc')
        if Cliente.objects.filter(ruc=ruc).exclude(pk=pk).exists():
            errors['ruc'] = 'Ya existe un cliente con este número de RUC.'
        
        razon_social = request.POST.get('razon_social')
        if Cliente.objects.filter(razon_social=razon_social).exclude(pk=pk).exists():
             errors['razon_social'] = 'Ya existe un cliente con esta Razón Social.'

        if not errors:
            try:
                direccion = request.POST.get('direccion')
                sitio_web = request.POST.get('sitio_web') 
                persona_contacto = request.POST.get('persona_contacto')
                cargo_contacto = request.POST.get('cargo_contacto')
                celular_contacto = request.POST.get('celular_contacto')
                correo_contacto = request.POST.get('correo_contacto')
                activo = request.POST.get('activo') == 'on' 
                
                logo_empresa_file = request.FILES.get('logo_empresa') # Nuevo campo
                firma_electronica_file = request.FILES.get('firma_electronica')

                if cliente:
                    cliente.razon_social = razon_social
                    cliente.ruc = ruc
                    cliente.direccion = direccion
                    cliente.sitio_web = sitio_web
                    cliente.persona_contacto = persona_contacto
                    cliente.cargo_contacto = cargo_contacto
                    cliente.celular_contacto = celular_contacto
                    cliente.correo_contacto = correo_contacto
                    cliente.activo = activo

                    if logo_empresa_file:
                        cliente.logo_empresa = logo_empresa_file
                    if firma_electronica_file:
                        cliente.firma_electronica = firma_electronica_file
                        
                    cliente.save()
                    messages.success(request, f"Cliente '{razon_social}' actualizado exitosamente.")
                else:
                    Cliente.objects.create(
                        creado_por=request.user, 
                        razon_social=razon_social,
                        ruc=ruc,
                        direccion=direccion,
                        sitio_web=sitio_web,
                        persona_contacto=persona_contacto,
                        cargo_contacto=cargo_contacto,
                        celular_contacto=celular_contacto,
                        correo_contacto=correo_contacto,
                        activo=activo,
                        logo_empresa=logo_empresa_file, 
                        firma_electronica=firma_electronica_file
                    )
                    messages.success(request, f"Cliente '{razon_social}' creado exitosamente.")
                
                return redirect('clientes:lista_clientes') 
                
            except IntegrityError:
                errors['general'] = 'Error de base de datos. El RUC o la Razón Social ya existen.'
            except Exception as e:
                errors['general'] = f'Ocurrió un error inesperado al guardar: {e}'

    context = {
        'cliente': cliente,
        'errors': errors,
        'data_cliente': data_cliente
    }
    return render(request, 'clientes/clientes_form.html', context)


@login_required
@user_passes_test(is_admin_or_supervisor)
def confirmar_eliminar_cliente(request, pk):
    """Muestra la confirmación para eliminar un cliente y lo procesa."""
    
    cliente = get_object_or_404(Cliente, pk=pk) 
    
    if request.method == 'POST':
        try:
            nombre = cliente.razon_social
            cliente.delete()
            messages.success(request, f"Cliente '{nombre}' eliminado permanentemente.")
            return redirect('clientes:lista_clientes') 
        except IntegrityError:
            messages.error(request, f"No se pudo eliminar el cliente '{cliente.razon_social}'. Tiene datos relacionados (proyectos/cotizaciones) que impiden su eliminación.")
            return redirect('clientes:lista_clientes')
        except Exception as e:
            messages.error(request, f"Error al intentar eliminar el cliente: {e}")
            return redirect('clientes:lista_clientes')

    return render(request, 'clientes/clientes_confirm_delete.html', {'cliente': cliente})

@require_POST
@login_required
def crear_cliente_ajax(request):
    try:
        # Obtener y sanitizar datos
        ruc = request.POST.get('ruc', '').strip()
        razon_social = request.POST.get('razon_social', '').strip()
        direccion = request.POST.get('direccion', '').strip()
        persona_contacto = request.POST.get('persona_contacto', '').strip()
        cargo_contacto = request.POST.get('cargo_contacto', '').strip()
        celular_contacto = request.POST.get('celular_contacto', '').strip()
        correo_contacto = request.POST.get('correo_contacto', '').strip()

        # Validaciones de seguridad
        if not ruc or len(ruc) < 8 or len(ruc) > 20:
            return JsonResponse({'status': 'error', 'message': 'RUC debe tener entre 8 y 20 caracteres.'}, status=400)
        
        if not razon_social or len(razon_social) < 2 or len(razon_social) > 200:
            return JsonResponse({'status': 'error', 'message': 'Razón social debe tener entre 2 y 200 caracteres.'}, status=400)
        
        if len(direccion) > 300:
            return JsonResponse({'status': 'error', 'message': 'Dirección no puede exceder 300 caracteres.'}, status=400)
        
        if len(persona_contacto) > 100:
            return JsonResponse({'status': 'error', 'message': 'Persona de contacto no puede exceder 100 caracteres.'}, status=400)
        
        if len(cargo_contacto) > 100:
            return JsonResponse({'status': 'error', 'message': 'Cargo de contacto no puede exceder 100 caracteres.'}, status=400)
        
        if len(celular_contacto) > 20:
            return JsonResponse({'status': 'error', 'message': 'Celular no puede exceder 20 caracteres.'}, status=400)
        
        if len(correo_contacto) > 100:
            return JsonResponse({'status': 'error', 'message': 'Correo no puede exceder 100 caracteres.'}, status=400)

        # Validar caracteres peligrosos
        import re
        campos_a_validar = [ruc, razon_social, direccion, persona_contacto, cargo_contacto, celular_contacto, correo_contacto]
        for campo in campos_a_validar:
            if re.search(r'[<>]', campo):
                logger.warning(f"Intento de XSS en crear_cliente_ajax por usuario {request.user.username}")
                return JsonResponse({'status': 'error', 'message': 'Caracteres no permitidos detectados.'}, status=400)

        # Verificar duplicados
        if Cliente.objects.filter(ruc=ruc).exists():
            return JsonResponse({'status': 'error', 'message': 'Ya existe un cliente con este RUC.'}, status=400)

        cliente = Cliente.objects.create(
            ruc=ruc,
            razon_social=razon_social,
            direccion=direccion,
            persona_contacto=persona_contacto,
            cargo_contacto=cargo_contacto,
            celular_contacto=celular_contacto,
            correo_contacto=correo_contacto,
        )
        
        # Log de seguridad
        logger.info(f"Cliente creado exitosamente: {razon_social} (RUC: {ruc}) por usuario {request.user.username}")
        
        return JsonResponse({
            'status': 'success',
            'id': cliente.pk,
            'ruc': cliente.ruc,
            'razon_social': cliente.razon_social,
            'persona_contacto': cliente.persona_contacto,
            'correo_contacto': cliente.correo_contacto,
            'celular_contacto': cliente.celular_contacto
        })
    except Exception as e:
        logger.error(f"Error al crear cliente por usuario {request.user.username}: {str(e)}")
        return JsonResponse({'status': 'error', 'message': 'Error interno del servidor.'}, status=500)