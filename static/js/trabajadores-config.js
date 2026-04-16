function openRolModal() {
    const modal = document.getElementById('modal-rol');
    if (!modal) return;

    modal.classList.remove('hidden');
    modal.classList.add('flex');
    document.body.classList.add('overflow-hidden');

    const inputNombre = document.getElementById('new_rol_name');
    if (inputNombre) {
        setTimeout(() => inputNombre.focus(), 80);
    }

    if (typeof lucide !== 'undefined') {
        lucide.createIcons();
    }
}

function closeRolModal() {
    const modal = document.getElementById('modal-rol');
    if (!modal) return;

    modal.classList.add('hidden');
    modal.classList.remove('flex');
    document.body.classList.remove('overflow-hidden');
}

async function saveNewRol() {
    const nombreInput = document.getElementById('new_rol_name');
    const descInput = document.getElementById('new_rol_desc');
    const select = document.getElementById('id_rol_select');
    const configEl = document.getElementById('rol-config');
    const saveBtn = document.getElementById('btn-save-rol');

    if (!configEl) {
        alert('Error de configuración: No se encontró el elemento rol-config.');
        return;
    }

    if (!nombreInput || !descInput || !select) {
        alert('Error de interfaz: faltan elementos del formulario.');
        return;
    }

    const nombre = nombreInput.value.trim();
    const desc = descInput.value.trim();
    const urlAction = configEl.getAttribute('data-url-crear');
    const csrfToken = configEl.getAttribute('data-csrf');

    if (!nombre) {
        alert('Por favor, ingrese un nombre.');
        nombreInput.focus();
        return;
    }

    const optionExistente = Array.from(select.options).find(
        opt => opt.text.trim().toLowerCase() === nombre.toLowerCase()
    );

    if (optionExistente) {
        select.value = optionExistente.value;
        closeRolModal();
        nombreInput.value = '';
        descInput.value = '';
        return;
    }

    const formData = new FormData();
    formData.append('nombre_rol', nombre);
    formData.append('descripcion_rol', desc);

    if (saveBtn) {
        saveBtn.disabled = true;
        saveBtn.dataset.originalText = saveBtn.innerHTML;
        saveBtn.innerHTML = 'Guardando...';
    }

    try {
        const response = await fetch(urlAction, {
            method: 'POST',
            body: formData,
            headers: {
                'X-CSRFToken': csrfToken,
                'X-Requested-With': 'XMLHttpRequest'
            },
            credentials: 'same-origin'
        });

        const contentType = response.headers.get('content-type') || '';
        if (!contentType.includes('application/json')) {
            const textError = await response.text();
            console.error('El servidor respondió con algo que no es JSON:', textError);
            throw new TypeError('La respuesta del servidor no es un JSON válido.');
        }

        const data = await response.json();

        if (!response.ok || !data.success) {
            alert('Error: ' + (data.error || 'No se pudo guardar'));
            return;
        }

        const nuevaOpcion = new Option(data.nombre, data.id, true, true);
        select.add(nuevaOpcion);
        select.value = String(data.id);
        select.dispatchEvent(new Event('change', { bubbles: true }));

        closeRolModal();
        nombreInput.value = '';
        descInput.value = '';

    } catch (error) {
        console.error('Error detallado:', error);
        alert('Ocurrió un error al procesar la solicitud. Revisa la consola.');
    } finally {
        if (saveBtn) {
            saveBtn.disabled = false;
            saveBtn.innerHTML = saveBtn.dataset.originalText || 'Guardar';
        }
    }
}

document.addEventListener('DOMContentLoaded', () => {
    if (typeof lucide !== 'undefined') {
        lucide.createIcons();
    }

    const modal = document.getElementById('modal-rol');
    const inputNombre = document.getElementById('new_rol_name');
    const inputDesc = document.getElementById('new_rol_desc');

    if (modal) {
        modal.addEventListener('click', (e) => {
            if (e.target === modal) {
                closeRolModal();
            }
        });
    }

    document.addEventListener('keydown', (e) => {
        const modalAbierto = modal && !modal.classList.contains('hidden');

        if (e.key === 'Escape' && modalAbierto) {
            closeRolModal();
        }

        if (e.key === 'Enter' && modalAbierto) {
            const target = document.activeElement;
            if (target === inputNombre || target === inputDesc) {
                e.preventDefault();
                saveNewRol();
            }
        }
    });
});