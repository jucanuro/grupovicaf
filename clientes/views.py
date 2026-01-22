from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required, user_passes_test
from django.views.decorators.http import require_POST
from django.contrib import messages
from django.db.models import Q
from django.db import IntegrityError
from django.core.paginator import Paginator
from django.http import JsonResponse
from .models import Cliente 

def is_admin_or_supervisor(user):
    """Verifica si el usuario es un administrador o supervisor del sistema."""
    return user.is_active and user.is_staff 

@login_required
@user_passes_test(is_admin_or_supervisor)
def lista_clientes(request):
    """Muestra el listado de todos los clientes con paginación y búsqueda."""
    
    query = request.GET.get('q')
    clientes = Cliente.objects.all().order_by('-creado_en') 

    if query:
        clientes = clientes.filter(
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
    """Devuelve un JSON con los resultados de búsqueda de clientes."""
    query = request.GET.get('q', '')
    clientes = Cliente.objects.filter( 
        Q(razon_social__icontains=query) |
        Q(ruc__icontains=query) |
        Q(persona_contacto__icontains=query) |
        Q(correo_contacto__icontains=query)
    ).values(
        'pk', 
        'razon_social', 
        'ruc', 
        'persona_contacto', 
        'correo_contacto', 
        'creado_en'
    )[:10]

    for cliente in clientes:
        if cliente['creado_en']:
            cliente['creado_en'] = cliente['creado_en'].strftime("%d %b %Y")
        else:
            cliente['creado_en'] = 'N/A'

    return JsonResponse(list(clientes), safe=False)


@login_required
@user_passes_test(is_admin_or_supervisor)
def crear_editar_cliente(request, pk=None):
    """Permite crear un nuevo cliente o editar uno existente."""
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
                firma_electronica_file = request.FILES.get('firma_electronica')

                if cliente:
                    # Lógica de edición
                    cliente.razon_social = razon_social
                    cliente.ruc = ruc
                    cliente.direccion = direccion
                    cliente.sitio_web = sitio_web
                    cliente.persona_contacto = persona_contacto
                    cliente.cargo_contacto = cargo_contacto
                    cliente.celular_contacto = celular_contacto
                    cliente.correo_contacto = correo_contacto
                    cliente.activo = activo

                    if firma_electronica_file:
                        cliente.firma_electronica = firma_electronica_file
                        
                    cliente.save()
                    messages.success(request, f"Cliente '{razon_social}' actualizado exitosamente.")
                else:
                    # Lógica de creación - Usamos el modelo Cliente
                    Cliente.objects.create(
                        # CRUCIAL: Asignamos el usuario logeado al campo de auditoría
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
                        firma_electronica=firma_electronica_file
                    )
                    messages.success(request, f"Cliente '{razon_social}' creado exitosamente.")
                
                # Redireccionamos al listado de clientes
                return redirect('clientes:lista_clientes') 
                
            except IntegrityError:
                # Esto atraparía errores de unicidad que no se validaron antes
                errors['general'] = 'Error de base de datos. El RUC o la Razón Social ya existen.'
            except Exception as e:
                 # Errores generales (por ejemplo, campo obligatorio vacío)
                 errors['general'] = f'Ocurrió un error inesperado al guardar: {e}'

    context = {
        'cliente': cliente,       # Instancia del cliente para edición
        'errors': errors,
        'data_cliente': data_cliente # Datos POST/actuales para rellenar formulario
    }
    # Usaremos una plantilla única para creación y edición: clientes_form.html
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
def crear_cliente_ajax(request):
    try:
        cliente = Cliente.objects.create(
            ruc=request.POST.get('ruc'),
            razon_social=request.POST.get('razon_social'),
            direccion=request.POST.get('direccion'),
            persona_contacto=request.POST.get('persona_contacto'),
            cargo_contacto=request.POST.get('cargo_contacto'),
            celular_contacto=request.POST.get('celular_contacto'),
            correo_contacto=request.POST.get('correo_contacto'),
        )
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
        return JsonResponse({'status': 'error', 'message': str(e)}, status=400)