function openRolModal() {
    document.getElementById('modal-rol').classList.remove('hidden');
    document.getElementById('modal-rol').classList.add('flex');
}

function closeRolModal() {
    document.getElementById('modal-rol').classList.add('hidden');
    document.getElementById('modal-rol').classList.remove('flex');
}

async function saveNewRol() {
    const nombre = document.getElementById('new_rol_name').value;
    const desc = document.getElementById('new_rol_desc').value;
    
    if(!nombre) return alert('Por favor, ingrese un nombre.');

    const formData = new FormData();
    formData.append('nombre_rol', nombre);
    formData.append('descripcion_rol', desc);
    formData.append('csrfmiddlewaretoken', '{{ csrf_token }}');

    try {
        const response = await fetch("{% url 'trabajadores:crear_rol_ajax' %}", {
            method: 'POST',
            body: formData
        });
        
        const data = await response.json();
        
        if(data.success) {
            // Añadir al select y seleccionar
            const select = document.getElementById('id_rol_select');
            const option = new Option(data.nombre, data.id, true, true);
            select.add(option);
            closeRolModal();
            // Limpiar campos
            document.getElementById('new_rol_name').value = '';
            document.getElementById('new_rol_desc').value = '';
        } else {
            alert(data.error);
        }
    } catch (error) {
        console.error('Error:', error);
    }
}
document.addEventListener('DOMContentLoaded', () => {
    if (typeof lucide !== 'undefined') lucide.createIcons();
});