function openRolModal() {
    const modal = document.getElementById('modal-rol');
    if (modal) {
        modal.classList.remove('hidden');
        modal.classList.add('flex');
    }
}

function closeRolModal() {
    const modal = document.getElementById('modal-rol');
    if (modal) {
        modal.classList.add('hidden');
        modal.classList.remove('flex');
    }
}

async function saveNewRol() {
    const nombre = document.getElementById('new_rol_name').value;
    const desc = document.getElementById('new_rol_desc').value;
    
    const configEl = document.getElementById('rol-config');
    
    if (!configEl) {
        return alert('Error de configuración: No se encontró el elemento rol-config.');
    }

    const urlAction = configEl.getAttribute('data-url-crear');
    const csrfToken = configEl.getAttribute('data-csrf');

    if(!nombre) return alert('Por favor, ingrese un nombre.');

    const formData = new FormData();
    formData.append('nombre_rol', nombre);
    formData.append('descripcion_rol', desc);
    formData.append('csrfmiddlewaretoken', csrfToken); 

    try {
        const response = await fetch(urlAction, {
            method: 'POST',
            body: formData,
            headers: {
                'X-Requested-With': 'XMLHttpRequest'
            }
        });
        
        const contentType = response.headers.get("content-type");
        if (!contentType || !contentType.includes("application/json")) {
            const textError = await response.text();
            console.error("El servidor respondió con algo que no es JSON:", textError);
            throw new TypeError("La respuesta del servidor no es un JSON válido.");
        }

        const data = await response.json();
        
        if(data.success) {
            const select = document.getElementById('id_rol_select');
            const option = new Option(data.nombre, data.id, true, true);
            select.add(option);
            
            closeRolModal();
            
            document.getElementById('new_rol_name').value = '';
            document.getElementById('new_rol_desc').value = '';
            
        } else {
            alert('Error: ' + (data.error || 'No se pudo guardar'));
        }
    } catch (error) {
        console.error('Error detallado:', error);
        alert('Ocurrió un error al procesar la solicitud. Revisa la consola.');
    }
}

document.addEventListener('DOMContentLoaded', () => {
    if (typeof lucide !== 'undefined') lucide.createIcons();
});