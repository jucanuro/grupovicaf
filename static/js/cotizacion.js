/* static/js/cotizacion.js - Versión Full Integrada */
document.addEventListener('DOMContentLoaded', () => {
    // --- VARIABLES DE ESTADO GLOBAL ---
    let ALL_SERVICES_DATA = [];
    let ALL_SERVICES_OPTIONS = [];
    
    // Referencias al DOM (Tal cual tus partes 1, 2 y 3)
    const clientesSelect = document.getElementById('id_cliente_ruc');
    const categoriaServicioSelect = document.getElementById('id_servicio_general');
    const detallesContainer = document.getElementById('cotizacion-detalles');
    const addItemBtn = document.getElementById('addItemBtn');
    const cotizacionForm = document.getElementById('cotizacion-form');
    const subtotalSpan = document.getElementById('subtotal_cotizacion');
    const igvSpan = document.getElementById('igv_cotizacion');
    const totalFinalSpan = document.getElementById('total_final_cotizacion');
    const montoTotalInput = document.getElementById('id_monto_total');
    const detallesJsonInput = document.getElementById('detalles_json');
    const tasaIgvInput = document.getElementById('tasa_igv');
    const fechaGeneracionInput = document.getElementById('id_fecha_generacion');
    const formaPagoSelect = document.querySelector('select[name="forma_pago"]');

    // --- FUNCIONES DE SOPORTE Y PARSEO (De tu Parte 2) ---
    const parseValue = (value) => {
        if (value === null || value === undefined) return 0;
        if (typeof value === 'number') return value;
        let cleanValue = String(value).trim().replace(',', '.');
        let parsed = parseFloat(cleanValue);
        return isNaN(parsed) ? 0 : parsed;
    };

    const initializeTomSelect = (element, customConfig = {}) => {
        if (typeof TomSelect === 'undefined' || !element) return null;
        if (element.tomselect) element.tomselect.destroy();

        const defaultConfig = {
            create: false,
            placeholder: 'Seleccione una opción',
            allowEmptyOption: true,
            maxOptions: 1000,
            onDropdownOpen: () => {
                if (typeof lucide !== 'undefined') lucide.createIcons();
            }
        };
        return new TomSelect(element, { ...defaultConfig, ...customConfig });
    };

    // --- CARGA DE DATOS (De tu Parte 2) ---
    const loadAllServicesData = () => {
        const dataElement = document.getElementById('all-services-data');
        if (dataElement) {
            try {
                ALL_SERVICES_DATA = JSON.parse(dataElement.textContent || '[]');
                ALL_SERVICES_OPTIONS = ALL_SERVICES_DATA.map(service => ({
                    value: String(service.pk),
                    text: `${service.nombre} ${service.codigo_facturacion ? '[' + service.codigo_facturacion + ']' : ''}`
                }));
            } catch (e) {
                console.error("Error parseando servicios:", e);
            }
        }
    };

    const loadClientData = (selectedOption) => {
        const razonSocialInput = document.getElementById('id_razon_social');
        const contactoInput = document.getElementById('id_persona_contacto');
        const correoInput = document.getElementById('id_correo_contacto');
        const telefonoInput = document.getElementById('id_telefono_contacto');

        if (selectedOption && selectedOption.value) {
            if (razonSocialInput) razonSocialInput.value = selectedOption.dataset.razonSocial || '';
            if (contactoInput) contactoInput.value = selectedOption.dataset.contacto || '';
            if (telefonoInput) telefonoInput.value = selectedOption.dataset.telefono || '';
            if (correoInput) correoInput.value = selectedOption.dataset.correo || '';
        }
    };

    // --- GENERACIÓN DE FILAS (De tu Parte 3) ---
    const createItemRowHTML = (servicioId, cantidad, precio, und, normaId, metodoId, descripcion) => {
        return `
            <div class="item-row-v2 p-5 mb-4 animate-fade-in-up bg-white border border-gray-200 rounded-2xl shadow-sm" 
                 data-servicio-id="${servicioId}" data-norma-id="${normaId}" data-metodo-id="${metodoId}">
                <div class="grid grid-cols-1 md:grid-cols-12 gap-4 items-end">
                    <div class="md:col-span-5">
                        <label class="block text-[10px] font-black text-gray-400 uppercase mb-1">Servicio / Ensayo</label>
                        <select class="form-control-v2 servicio-select" required>
                            <option value="${servicioId}" selected>Cargando servicio...</option>
                        </select>
                    </div>
                    <div class="md:col-span-4">
                        <label class="block text-[10px] font-black text-gray-400 uppercase mb-1">Nota / Descripción Específica</label>
                        <input type="text" class="form-control-v2 descripcion-input" value="${descripcion}" placeholder="Ej: Muestra sector A...">
                    </div>
                    <div class="md:col-span-1">
                        <label class="block text-[10px] font-black text-gray-400 uppercase mb-1 text-center">Cant.</label>
                        <input type="number" class="form-control-v2 cantidad-input text-center font-bold" value="${cantidad}" min="1">
                    </div>
                    <div class="md:col-span-2 flex items-center justify-end gap-3">
                        <div class="text-right">
                            <span class="block text-[10px] font-black text-gray-400 uppercase">Parcial</span>
                            <span class="text-lg font-black text-emerald-600">S/. <span class="subtotal-cell">0.00</span></span>
                        </div>
                        <button type="button" class="remove-item-btn p-2 text-red-400 hover:bg-red-50 hover:text-red-600 rounded-xl transition-colors">
                            <i data-lucide="trash-2" class="w-5 h-5"></i>
                        </button>
                    </div>
                </div>
                <div class="grid grid-cols-1 md:grid-cols-4 gap-4 mt-4 pt-4 border-t border-gray-50">
                    <div>
                        <label class="block text-[10px] font-bold text-gray-400 mb-1">Norma</label>
                        <select class="form-control-v2 normas-select text-xs"></select>
                    </div>
                    <div>
                        <label class="block text-[10px] font-bold text-gray-400 mb-1">Método</label>
                        <select class="form-control-v2 metodos-select text-xs"></select>
                    </div>
                    <div>
                        <label class="block text-[10px] font-bold text-gray-400 mb-1">Precio Unit.</label>
                        <div class="relative">
                            <span class="absolute left-3 top-2.5 text-gray-400 text-xs font-bold">S/.</span>
                            <input type="number" step="0.01" class="form-control-v2 precio-input pl-8 font-bold" value="${precio}">
                        </div>
                    </div>
                    <div>
                        <label class="block text-[10px] font-bold text-gray-400 mb-1">Unidad</label>
                        <input type="text" class="form-control-v2 und-input text-xs" value="${und}" placeholder="und, m3, etc.">
                    </div>
                </div>
            </div>`;
    };

    const addRow = (servicioId = '', cantidad = '1', precio = '0.00', und = 'und', normaId = '', metodoId = '', descripcion = '') => {
        const rowHTML = createItemRowHTML(servicioId, cantidad, precio, und, normaId, metodoId, descripcion); 
        const tempDiv = document.createElement('div');
        tempDiv.innerHTML = rowHTML.trim();
        const newRow = tempDiv.firstChild;
        detallesContainer.appendChild(newRow);
        
        if (typeof lucide !== 'undefined') lucide.createIcons();

        const servicioSelect = newRow.querySelector('.servicio-select');
        initializeTomSelect(servicioSelect, {
            options: ALL_SERVICES_OPTIONS,
            items: servicioId ? [String(servicioId)] : []
        });

        if (servicioId) {
            loadServiceData(servicioSelect, normaId, metodoId);
        } else {
            updateTotals();
        }
    };

    const loadServiceData = (selectElement, selectedNormaId, selectedMetodoId) => {
        const pk = selectElement.value;
        const row = selectElement.closest('.item-row-v2'); 
        const precioInput = row.querySelector('.precio-input');
        const undInput = row.querySelector('.und-input');
        const normasSelect = row.querySelector('.normas-select');
        const metodosSelect = row.querySelector('.metodos-select');

        const servicio = ALL_SERVICES_DATA.find(s => String(s.pk) === pk);

        if (normasSelect.tomselect) normasSelect.tomselect.destroy();
        if (metodosSelect.tomselect) metodosSelect.tomselect.destroy();

        normasSelect.innerHTML = '<option value="">Seleccione norma</option>';
        metodosSelect.innerHTML = '<option value="">Seleccione método</option>';

        if (servicio) {
            // Solo sobreescribir precio si es 0 (para no borrar lo que viene de la base de datos en edición)
            if (parseValue(precioInput.value) === 0) {
                precioInput.value = String(servicio.precio_base).replace(',', '.');
            }
            undInput.value = servicio.unidad_base || 'und';
            
            if (servicio.normas) {
                servicio.normas.forEach(norma => {
                    const opt = new Option(`${norma.codigo || ''} ${norma.nombre}`, norma.pk);
                    if (String(norma.pk) === String(selectedNormaId)) opt.selected = true;
                    normasSelect.add(opt);
                });
            }
            if (servicio.metodos) {
                servicio.metodos.forEach(metodo => {
                    const opt = new Option(`${metodo.codigo || ''} ${metodo.nombre}`, metodo.pk);
                    if (String(metodo.pk) === String(selectedMetodoId)) opt.selected = true;
                    metodosSelect.add(opt);
                });
            }

            initializeTomSelect(normasSelect, { placeholder: 'Seleccione norma' });
            initializeTomSelect(metodosSelect, { placeholder: 'Seleccione método' });
        }
        updateTotals();
    };

    const updateAllServiceSelects = (isMasterCategoryChange = false) => {
        detallesContainer.querySelectorAll('.item-row-v2').forEach(row => {
            const servicioSelect = row.querySelector('.servicio-select');
            
            if (isMasterCategoryChange) {
                if (servicioSelect.tomselect) servicioSelect.tomselect.setValue('', true);
                row.dataset.servicioId = ''; 
                row.querySelector('.precio-input').value = '0.00';
                row.querySelector('.und-input').value = 'und';
                const dI = row.querySelector('.descripcion-input');
                if (dI) dI.value = '';
            }
            
            if (!servicioSelect.tomselect) initializeTomSelect(servicioSelect);
            if (servicioSelect.value) loadServiceData(servicioSelect, row.dataset.normaId, row.dataset.metodoId);
        });
        updateTotals(); 
    };

    // --- CÁLCULO DE TOTALES (De tu Parte 3) ---
    const updateTotals = () => {
        let subtotal = 0;
        const detalles = [];
        let tasaIgv = parseValue(tasaIgvInput?.value || 0.18);
        if (tasaIgv > 1) tasaIgv = tasaIgv / 100;

        detallesContainer.querySelectorAll('.item-row-v2').forEach(row => { 
            const sId = row.querySelector('.servicio-select').value;
            const cant = parseValue(row.querySelector('.cantidad-input').value);
            const prec = parseValue(row.querySelector('.precio-input').value);
            const subCell = row.querySelector('.subtotal-cell');
            
            const itemSubtotal = cant * prec;
            subtotal += itemSubtotal;
            subCell.textContent = itemSubtotal.toFixed(2);

            if (sId) {
                detalles.push({
                    servicio_id: sId,
                    cantidad: cant,
                    precio_unitario: prec.toFixed(2), 
                    unidad_medida: row.querySelector('.und-input').value,
                    norma_id: row.querySelector('.normas-select').value || null,
                    metodo_id: row.querySelector('.metodos-select').value || null,
                    descripcion_especifica: row.querySelector('.descripcion-input').value.trim()
                });
            }
        });

        const igv = subtotal * tasaIgv;
        const totalFinal = subtotal + igv;
        
        subtotalSpan.textContent = subtotal.toFixed(2);
        igvSpan.textContent = igv.toFixed(2);
        totalFinalSpan.textContent = totalFinal.toFixed(2);
        montoTotalInput.value = totalFinal.toFixed(2);
        detallesJsonInput.value = JSON.stringify(detalles);
    };

    // --- EVENTOS Y TRIGGERS (Restaurado de Parte 3) ---
    categoriaServicioSelect.addEventListener('change', () => {
        // En tu original, el cambio de categoría limpia o resetea selects
        updateAllServiceSelects(true);
    });
    
    if (tasaIgvInput) tasaIgvInput.addEventListener('input', updateTotals);
    
    clientesSelect.addEventListener('change', () => {
        loadClientData(clientesSelect.options[clientesSelect.selectedIndex]);
    });

    addItemBtn.addEventListener('click', () => {
        addRow();
        updateAllServiceSelects(); 
    });
    
    detallesContainer.addEventListener('change', (e) => { 
        if (e.target.matches('.servicio-select')) {
            const row = e.target.closest('.item-row-v2');
            row.dataset.servicioId = e.target.value; 
            row.dataset.normaId = '';
            row.dataset.metodoId = '';
            loadServiceData(e.target, '', '');
        }
        if (e.target.matches('.normas-select, .metodos-select')) updateTotals();
    });

    detallesContainer.addEventListener('input', (e) => {
        if (e.target.matches('.cantidad-input, .precio-input, .und-input, .descripcion-input')) {
            updateTotals();
        }
    });

    detallesContainer.addEventListener('paste', (e) => {
        if (e.target.matches('.cantidad-input, .precio-input, .descripcion-input')) {
            setTimeout(updateTotals, 50); 
        }
    });
    
    detallesContainer.addEventListener('click', (e) => {
        const removeBtn = e.target.closest('.remove-item-btn');
        if (removeBtn) {
            removeBtn.closest('.item-row-v2').remove(); 
            updateTotals();
        }
    });

    cotizacionForm.addEventListener('submit', (e) => {
        updateTotals();
        const data = JSON.parse(detallesJsonInput.value || '[]');
        if (data.length === 0) {
            e.preventDefault();
            alert('Debe agregar al menos un ítem a la cotización.');
        }
    });

    // --- INICIALIZACIÓN FINAL ---
    loadAllServicesData(); 

    if (typeof TomSelect !== 'undefined') {
        initializeTomSelect(clientesSelect, { placeholder: 'Seleccione cliente' });
        initializeTomSelect(formaPagoSelect);
        initializeTomSelect(categoriaServicioSelect); 
    }

    // Cargar cliente inicial si existe
    if (clientesSelect.selectedIndex > 0) {
        loadClientData(clientesSelect.options[clientesSelect.selectedIndex]);
    }

    // Cargar ítems desde JSON (Modo Edición)
    const initialDetailsElement = document.getElementById('initial-detalles-json');
    if (initialDetailsElement) {
        try {
            const initialDetails = JSON.parse(initialDetailsElement.textContent || '[]');
            detallesContainer.innerHTML = '';
            if (initialDetails.length > 0) {
                initialDetails.forEach(d => {
                    addRow(
                        String(d.servicio_id || ''), 
                        String(d.cantidad || '1'), 
                        String(d.precio_unitario || '0.00'), 
                        String(d.unidad_medida || 'und'), 
                        String(d.norma_id || ''), 
                        String(d.metodo_id || ''),
                        String(d.descripcion_especifica || '')
                    );
                });
            } else {
                addRow();
            }
        } catch (e) {
            addRow();
        }
    } else {
        addRow();
    }

    // Fecha hoy
    if (fechaGeneracionInput && !fechaGeneracionInput.value) {
        fechaGeneracionInput.value = new Date().toISOString().split('T')[0];
    }
    
    updateTotals(); 
});