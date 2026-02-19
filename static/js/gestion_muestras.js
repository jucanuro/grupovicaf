const tbody = document.getElementById('tbody-muestras');
const tiposMuestra = JSON.parse(document.getElementById('data-tipos').textContent || '[]');
const selectorGlobal = document.getElementById('tipo_global_selector');
let filaEnEdicion = null;

function initSelectorGlobal() {
    if (!selectorGlobal) return;
    let options = `<option value="" selected disabled hidden>Selecciona muestra</option>`;
    options += tiposMuestra.map(t => 
        `<option value="${t.id}" data-prefijo="${t.prefijo}">${t.nombre}</option>`
    ).join('');
    selectorGlobal.innerHTML = options;
}

function generarCodigoLab(prefijo, index) {
    const anio = new Date().getFullYear();
    return `V-M-${anio}-${prefijo}-${index.toString().padStart(4, '0')}`;
}

function limpiarSelector() {
    if (selectorGlobal) selectorGlobal.value = "";
}

function crearOActualizarFila() {
    if (filaEnEdicion) {
        confirmarEdicion();
    } else {
        crearFila();
    }
}

function crearFila() {
    if (!selectorGlobal || !selectorGlobal.value) {
        alert("Selecciona un tipo de muestra.");
        return;
    }

    const tr = document.createElement('tr');
    tr.className = "group hover:bg-slate-50 transition-all duration-200 border-b border-slate-100";
    const index = tbody.children.length + 1;
    const tipoId = selectorGlobal.value;
    const option = selectorGlobal.options[selectorGlobal.selectedIndex];
    const prefijo = option.getAttribute('data-prefijo');
    const nombreTipo = option.text;
    const idLabAuto = generarCodigoLab(prefijo, index);

    tr.innerHTML = `
        <td class="px-3 py-2 text-center border-r border-slate-100/50">
            <span class="text-[10px] font-medium text-slate-400 font-mono">${index.toString().padStart(2, '0')}</span>
        </td>
        <td class="px-4 py-2 border-r border-slate-100/50">
            <div class="relative group/id">
                <input type="text" name="id_lab[]" value="${idLabAuto}" readonly 
                    class="w-full bg-slate-50/50 border-none rounded-lg px-2 py-1.5 text-[11px] font-bold text-blue-600 text-center ring-1 ring-blue-100/50 outline-none transition-all group-hover/id:bg-blue-50">
            </div>
        </td>
        <td class="px-4 py-2 border-r border-slate-100/50">
            <div onclick="activarEdicion(this)" 
                class="flex items-center justify-between gap-2 bg-white border border-slate-200 rounded-xl px-3 py-1.5 cursor-pointer hover:border-blue-400 hover:shadow-sm transition-all group/tipo">
                <div class="flex items-center gap-2">
                    <span class="w-1.5 h-1.5 rounded-full bg-blue-500 animate-pulse"></span>
                    <span class="tipo-label text-[10px] font-black text-slate-700 uppercase tracking-tight">${nombreTipo}</span>
                </div>
                <i data-lucide="edit-3" class="w-3 h-3 text-slate-300 group-hover/tipo:text-blue-500 transition-colors"></i>
                <input type="hidden" name="tipo_muestra_id[]" value="${tipoId}">
            </div>
        </td>
        <td class="px-2 py-2 border-r border-slate-100/50">
            <input type="number" step="0.01" name="cantidad[]" placeholder="0.00" required 
                class="w-full px-2 py-1.5 bg-transparent border-none text-center text-[12px] font-bold text-slate-800 outline-none focus:ring-2 focus:ring-blue-500/10 focus:bg-slate-50 rounded-lg transition-all">
        </td>
        <td class="px-2 py-2 border-r border-slate-100/50">
            <input type="text" name="unidad[]" placeholder="U.M" required 
                class="w-full px-2 py-1.5 bg-slate-100/50 border-none rounded-lg text-center text-[10px] font-black text-slate-500 uppercase outline-none focus:ring-2 focus:ring-slate-200">
        </td>
        <td class="px-2 py-2 border-r border-slate-100/50">
            <div class="relative">
                <input type="text" name="masa[]" placeholder="0.00" 
                    class="w-full px-2 py-1.5 bg-transparent border-none text-center text-[11px] font-mono font-bold text-slate-700 outline-none focus:ring-2 focus:ring-blue-500/10 rounded-lg">
            </div>
        </td>
        <td class="px-4 py-2 border-r border-slate-100/50">
            <input type="text" name="descripcion[]" placeholder="Describa la muestra..." 
                class="w-full px-0 py-1.5 bg-transparent border-none text-[11px] text-slate-600 placeholder:text-slate-300 outline-none focus:ring-0">
        </td>
        <td class="px-4 py-2 border-r border-slate-100/50">
            <div class="flex items-center gap-2">
                <i data-lucide="message-square" class="w-3 h-3 text-slate-300"></i>
                <input type="text" name="observaciones[]" placeholder="Notas..." 
                    class="w-full px-0 py-1.5 bg-transparent border-none text-[10px] text-slate-400 italic placeholder:text-slate-200 outline-none focus:ring-0">
            </div>
        </td>
        <td class="px-4 py-2 text-center">
            <button type="button" onclick="eliminarFila(this)" 
                class="group/del p-2 hover:bg-rose-50 rounded-xl transition-all duration-300">
                <i data-lucide="trash-2" class="w-4 h-4 text-slate-300 group-hover/del:text-rose-500 group-hover/del:scale-110 transition-all"></i>
            </button>
        </td>
    `;

    tbody.appendChild(tr);
    limpiarSelector();
    if (window.lucide) lucide.createIcons();
}

function activarEdicion(celda) {
    if (filaEnEdicion) filaEnEdicion.classList.remove('bg-amber-50', 'ring-2', 'ring-amber-200');
    filaEnEdicion = celda.closest('tr');
    filaEnEdicion.classList.add('bg-amber-50', 'ring-2', 'ring-amber-200');
    
    selectorGlobal.value = filaEnEdicion.querySelector('input[name="tipo_muestra_id[]"]').value;
    
    const btn = document.getElementById('btn_generar');
    btn.classList.replace('bg-slate-900', 'bg-amber-500');
    btn.classList.replace('hover:bg-blue-600', 'hover:bg-amber-600');
    
    document.getElementById('btn_text').innerText = "ACTUALIZAR TIPO";
    document.getElementById('label_selector').innerText = "Editando tipo de muestra:";
    document.getElementById('label_selector').classList.replace('text-slate-400', 'text-amber-600');
    document.getElementById('btn_icon_container').classList.replace('bg-blue-500', 'bg-amber-600');
    document.getElementById('btn_icon').setAttribute('data-lucide', 'refresh-cw');
    
    if (window.lucide) lucide.createIcons();
}

function confirmarEdicion() {
    if (!selectorGlobal.value) return;
    const option = selectorGlobal.options[selectorGlobal.selectedIndex];
    const nuevoPrefijo = option.getAttribute('data-prefijo');
    const index = filaEnEdicion.cells[0].innerText;
    
    filaEnEdicion.querySelector('.tipo-label').innerText = option.text;
    filaEnEdicion.querySelector('input[name="tipo_muestra_id[]"]').value = selectorGlobal.value;
    filaEnEdicion.querySelector('input[name="id_lab[]"]').value = generarCodigoLab(nuevoPrefijo, parseInt(index));
    
    filaEnEdicion.classList.add('bg-green-50');
    setTimeout(() => {
        filaEnEdicion.classList.remove('bg-green-50', 'bg-amber-50', 'ring-2', 'ring-amber-200');
        cancelarEdicion();
    }, 400);
}

function cancelarEdicion() {
    filaEnEdicion = null;
    limpiarSelector();
    
    const btn = document.getElementById('btn_generar');
    btn.classList.replace('bg-amber-500', 'bg-slate-900');
    btn.classList.replace('hover:bg-amber-600', 'hover:bg-blue-600');
    
    document.getElementById('btn_text').innerText = "AÑADIR NUEVA MUESTRA";
    document.getElementById('label_selector').innerText = "Tipo de muestra a generar:";
    document.getElementById('label_selector').classList.replace('text-amber-600', 'text-slate-400');
    document.getElementById('btn_icon_container').classList.replace('bg-amber-600', 'bg-blue-500');
    document.getElementById('btn_icon').setAttribute('data-lucide', 'plus');
    
    if (window.lucide) lucide.createIcons();
}

function reenumerarItems() {
    Array.from(tbody.children).forEach((row, idx) => {
        const index = idx + 1;
        row.cells[0].querySelector('span').innerText = index.toString().padStart(2, '0');
        const hiddenTipo = row.querySelector('input[name="tipo_muestra_id[]"]').value;
        const tipoData = tiposMuestra.find(t => t.id == hiddenTipo);
        row.querySelector('input[name="id_lab[]"]').value = generarCodigoLab(tipoData ? tipoData.prefijo : 'XX', index);
    });
}

function eliminarFila(btn) {
    btn.closest('tr').remove();
    reenumerarItems();
    if (filaEnEdicion) cancelarEdicion();
}

function openTipoMuestraModal() {
    const modal = document.getElementById('modal-tipo-muestra');
    if (modal) {
        modal.classList.remove('hidden');
        modal.classList.add('flex');
        document.getElementById('new_tipo_nombre').focus();
    }
}

function closeTipoMuestraModal() {
    const modal = document.getElementById('modal-tipo-muestra');
    if (modal) {
        modal.classList.add('hidden');
        modal.classList.remove('flex');
        document.getElementById('new_tipo_nombre').value = '';
        document.getElementById('new_tipo_sigla').value = '';
    }
}

function saveNewTipoMuestra() {
    const nombreInput = document.getElementById('new_tipo_nombre');
    const siglaInput = document.getElementById('new_tipo_sigla');
    const nombre = nombreInput.value.trim();
    const sigla = siglaInput.value.trim();
    const btnSave = document.getElementById('btn-save-tipo');
    
    if (!nombre || !sigla) { alert("Complete los campos."); return; }

    btnSave.disabled = true;
    btnSave.innerHTML = `<span class="animate-spin mr-2">◌</span> GUARDANDO...`;

    const formData = new FormData();
    formData.append('nombre', nombre);
    formData.append('sigla', sigla);
    formData.append('csrfmiddlewaretoken', window.DjangoConfig.csrfToken);

    fetch(window.DjangoConfig.crearTipoMuestraUrl, {
        method: 'POST',
        body: formData,
        headers: { 'X-Requested-With': 'XMLHttpRequest' }
    })
    .then(async response => {
        const isJson = response.headers.get('content-type')?.includes('application/json');
        const data = isJson ? await response.json() : null;

        if (!response.ok) {
            if (!isJson) {
                const errorText = await response.text();
                console.error("Error del servidor (HTML):", errorText);
                throw new Error(`Error del servidor (${response.status}). Revisa la consola.`);
            }
            throw data || { message: 'Error desconocido' };
        }
        return data;
    })
    .then(data => {
        if (data.status === 'success') {
            tiposMuestra.push({ id: data.id, nombre: data.nombre, prefijo: data.sigla });
            const newOption = new Option(data.nombre, data.id, true, true);
            newOption.setAttribute('data-prefijo', data.sigla);
            selectorGlobal.add(newOption);
            
            nombreInput.value = '';
            siglaInput.value = '';
            closeTipoMuestraModal();
        }
    })
    .catch(error => {
        console.error('Error completo:', error);
        alert(error.message || "Error al guardar el tipo de muestra.");
    })
    .finally(() => {
        btnSave.disabled = false;
        btnSave.innerHTML = `<i data-lucide="save" class="w-4 h-4"></i> GUARDAR`;
        if (window.lucide) lucide.createIcons();
    });
}

document.addEventListener('DOMContentLoaded', () => {
    initSelectorGlobal();
    if (window.lucide) lucide.createIcons();
});