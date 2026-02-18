/**
 * VICAF PRO V2.0 - Gestión de Cotizaciones
 * Archivo: cotizacion-config.js
 */

document.addEventListener('DOMContentLoaded', () => {
    // Inicialización de Iconos
    if (typeof lucide !== 'undefined') lucide.createIcons();

    // --- VARIABLES DE ESTADO ---
    let EDIT_INDEX = null; 
    const config = window.CotizacionConfig || {};
    
    // Recuperación de Data inyectada desde el HTML
    const ALL_SERVICES = JSON.parse(document.getElementById('all-services-data')?.textContent || '[]');
    const INITIAL_DATA = JSON.parse(document.getElementById('initial-detalles-json')?.textContent || '[]');
    
    // Array principal de la cotización
    let DATA_ARRAY = INITIAL_DATA;

    // --- MANEJO DE FORMA DE PAGO ---
    document.getElementById('id_forma_pago')?.addEventListener('change', function() {
        const customContainer = document.getElementById('pago_personalizado_container');
        if (this.value === 'Personalizado') {
            customContainer.classList.remove('hidden');
        } else {
            customContainer.classList.add('hidden');
        }
    });

    // --- FUNCIONES DE APOYO ---
    const loadClientData = (opt) => {
        const fields = {
            'id_razon_social': opt?.dataset.razonSocial || '',
            'id_persona_contacto': opt?.dataset.contacto || '',
            'id_correo_contacto': opt?.dataset.correo || '',
            'id_telefono_contacto': opt?.dataset.telefono || ''
        };
        for (const [id, value] of Object.entries(fields)) {
            const el = document.getElementById(id);
            if (el) el.value = value;
        }
    };

    const getLetter = (num, upper = true) => String.fromCharCode((upper ? 65 : 97) + (num - 1));

    // --- 1. BUSCADOR: CLIENTE ---
    const clientesSelect = document.getElementById('id_cliente_ruc');
    let tsCliente = null;
    if (clientesSelect) {
        tsCliente = new TomSelect('#id_cliente_ruc', {
            onInitialize: function() {
                this.wrapper.classList.add('vicaf-search');
                if (this.getValue()) {
                    const selected = clientesSelect.options[clientesSelect.selectedIndex];
                    loadClientData(selected);
                }
            },
            onChange: function(value) {
                const selectedOption = Array.from(clientesSelect.options).find(opt => opt.value === value);
                loadClientData(selectedOption);
            }
        });
    }

    // --- 2. BUSCADOR: CATEGORÍA GENERAL (CABECERA) ---
    const tsServicioGeneral = new TomSelect('#id_servicio_general', {
        onInitialize: function() { 
            this.wrapper.classList.add('vicaf-search'); 
        },
        placeholder: 'BUSCAR CATEGORÍA PRINCIPAL...',
        create: false
    });

    // --- 3. BUSCADOR: CATEGORÍA (EN EL PANEL DE REGISTRO) ---
    const tsRegCategoria = new TomSelect('#reg_categoria', {
        onInitialize: function() { this.wrapper.classList.add('vicaf-search'); },
        onChange: function(val) {
            if (!val || this.isUpdating) return; 
            if (EDIT_INDEX !== null && DATA_ARRAY[EDIT_INDEX].tipo_fila === 'categoria') {
                DATA_ARRAY[EDIT_INDEX].descripcion_especifica = val.toUpperCase();
                resetEditor();
                renderTable();
            } else if (EDIT_INDEX === null) {
                window.addHeader('categoria', val);
                this.clear(true);
            }
        }
    });

    // --- 4. BUSCADOR: SUB-CATEGORÍA ---
    const tsRegSubcategoria = new TomSelect('#reg_subcategoria', {
        onInitialize: function() { this.wrapper.classList.add('vicaf-search'); },
        onChange: function(val) {
            if (!val || this.isUpdating) return;
            if (EDIT_INDEX !== null && DATA_ARRAY[EDIT_INDEX].tipo_fila === 'subcategoria') {
                DATA_ARRAY[EDIT_INDEX].descripcion_especifica = val.toUpperCase();
                resetEditor();
                renderTable();
            } else if (EDIT_INDEX === null) {
                window.addHeader('subcategoria', val);
                this.clear(true);
            }
        }
    });

    // --- 5. BUSCADOR: SERVICIOS (ENSAYOS) ---
    const tsServicio = new TomSelect('#reg_servicio', {
        options: ALL_SERVICES.map(s => ({ value: s.pk, text: s.nombre })),
        placeholder: 'BUSCAR SERVICIO...',
        onInitialize: function() { this.wrapper.classList.add('vicaf-search'); },
        onChange: function(val) {
            if (this.isUpdating) return;
            const s = ALL_SERVICES.find(x => String(x.pk) === String(val));
            if (s) {
                const normaDiv = document.getElementById('reg_norma_txt');
                const metodoDiv = document.getElementById('reg_metodo_txt');
                normaDiv.textContent = s.norma_codigo || 'N/A'; 
                metodoDiv.textContent = s.metodo_codigo || 'N/A';
                document.getElementById('reg_precio').value = s.precio_base;
                [normaDiv, metodoDiv].forEach(el => {
                    el.classList.remove('text-slate-400', 'italic');
                    el.classList.add('text-slate-700', 'font-bold');
                });
            } else {
                document.getElementById('reg_norma_txt').textContent = 'Auto...';
                document.getElementById('reg_metodo_txt').textContent = 'Auto...';
                document.getElementById('reg_precio').value = '';
            }
        }
    });

    // --- MODALES (GLOBALES) ---
    window.openClienteModal = () => { document.getElementById('modalCliente')?.classList.remove('hidden'); document.body.style.overflow = 'hidden'; };
    window.closeClienteModal = () => { document.getElementById('modalCliente')?.classList.add('hidden'); document.body.style.overflow = 'auto'; };
    window.openCategoriaModal = () => { document.getElementById('modalCategoria')?.classList.remove('hidden'); document.body.style.overflow = 'hidden'; };
    window.closeCategoriaModal = () => { document.getElementById('modalCategoria')?.classList.add('hidden'); document.body.style.overflow = 'auto'; };
    window.openSubcategoriaModal = () => { 
        const m = document.getElementById('modalSubcategoria'); 
        if(m){ m.classList.remove('hidden'); m.style.display = 'flex'; } 
        document.body.style.overflow = 'hidden'; 
    };
    window.closeSubcategoriaModal = () => { 
        const m = document.getElementById('modalSubcategoria'); 
        if(m){ m.classList.add('hidden'); m.style.display = 'none'; } 
        document.body.style.overflow = 'auto'; 
    };

    // --- LÓGICA DE EDICIÓN ---
    window.editItem = (index) => {
        const item = DATA_ARRAY[index];
        EDIT_INDEX = index;
        
        // Abrir panel si está cerrado
        const content = document.getElementById('content-registro');
        if (content && content.classList.contains('hidden')) {
             if (typeof toggleRegistroPanel === 'function') toggleRegistroPanel();
        }

        tsRegCategoria.isUpdating = true;
        tsRegSubcategoria.isUpdating = true;
        tsServicio.isUpdating = true;

        tsRegCategoria.clear(true);
        tsRegSubcategoria.clear(true);
        tsServicio.clear(true);

        if (item.tipo_fila === 'categoria') {
            if (!tsRegCategoria.options[item.descripcion_especifica]) {
                tsRegCategoria.addOption({value: item.descripcion_especifica, text: item.descripcion_especifica});
            }
            tsRegCategoria.setValue(item.descripcion_especifica);
        } else if (item.tipo_fila === 'subcategoria') {
            if (!tsRegSubcategoria.options[item.descripcion_especifica]) {
                tsRegSubcategoria.addOption({value: item.descripcion_especifica, text: item.descripcion_especifica});
            }
            tsRegSubcategoria.setValue(item.descripcion_especifica);
        } else {
            tsServicio.setValue(item.servicio_id);
            document.getElementById('reg_cantidad').value = item.cantidad;
            document.getElementById('reg_precio').value = item.precio_unitario;
        }

        tsRegCategoria.isUpdating = false;
        tsRegSubcategoria.isUpdating = false;
        tsServicio.isUpdating = false;

        const btn = document.querySelector('button[onclick="addItem()"]');
        if (btn) {
            btn.innerHTML = `<i data-lucide="refresh-cw" class="w-4 h-4"></i> ACTUALIZAR ÍTEM`;
            btn.classList.replace('bg-slate-900', 'bg-orange-600');
            if (typeof lucide !== 'undefined') lucide.createIcons();
        }
        document.getElementById('content-registro').scrollIntoView({ behavior: 'smooth', block: 'center' });
    };

    window.resetEditor = () => {
        EDIT_INDEX = null;
        tsRegCategoria.isUpdating = true;
        tsRegSubcategoria.isUpdating = true;
        tsServicio.isUpdating = true;
        
        tsRegCategoria.clear(true);
        tsRegSubcategoria.clear(true);
        tsServicio.clear(true);
        
        tsRegCategoria.isUpdating = false;
        tsRegSubcategoria.isUpdating = false;
        tsServicio.isUpdating = false;

        document.getElementById('reg_cantidad').value = "1";
        document.getElementById('reg_precio').value = "";
        
        const btn = document.querySelector('button[onclick="addItem()"]');
        if (btn) {
            btn.innerHTML = `<i data-lucide="plus-circle" class="w-4 h-4"></i> Agregar Ítem al Detalle`;
            btn.classList.replace('bg-orange-600', 'bg-slate-900');
            if (typeof lucide !== 'undefined') lucide.createIcons();
        }
    };

    // --- AGREGAR CABECERAS Y ÍTEMS ---
    window.addHeader = (tipo, valOverride = null) => {
        let val = valOverride || document.getElementById(tipo === 'categoria' ? 'reg_categoria' : 'reg_subcategoria')?.value;
        if(!val) return;
        DATA_ARRAY.push({ 
            tipo_fila: tipo, 
            descripcion_especifica: val.toUpperCase() 
        });
        renderTable();
    };

    window.addItem = () => {
        const sId = document.getElementById('reg_servicio')?.value;
        if(!sId) return;
        const sBase = ALL_SERVICES.find(x => String(x.pk) === String(sId));
        
        const data = {
            tipo_fila: 'servicio', 
            servicio_id: sId,
            descripcion_especifica: sBase.nombre,
            cantidad: parseFloat(document.getElementById('reg_cantidad').value) || 1,
            precio_unitario: parseFloat(document.getElementById('reg_precio').value) || 0,
            norma_id: sBase.norma_pk, 
            metodo_id: sBase.metodo_pk,
            norma_nombre: sBase.norma_codigo + (sBase.metodo_codigo ? ' / ' + sBase.metodo_codigo : ''),
            unidad_medida: sBase.unidad_base || 'UND'
        };

        if (EDIT_INDEX !== null) {
            DATA_ARRAY[EDIT_INDEX] = data;
            resetEditor(); 
        } else {
            DATA_ARRAY.push(data);
            tsServicio.clear(); 
        }
        renderTable();
    };

    window.remove = (idx) => { 
        DATA_ARRAY.splice(idx, 1); 
        if (EDIT_INDEX === idx) resetEditor();
        renderTable(); 
    };

    // --- RENDERIZADO DE TABLA ---
    window.renderTable = () => {
        const body = document.getElementById('cotizacion-detalles');
        if (!body) return;
        body.innerHTML = '';
        let subtotal = 0;
        let catCount = 0, subCatCount = 0, serviceCount = 0;

        DATA_ARRAY.forEach((item, index) => {
            const tr = document.createElement('tr');
            tr.onclick = () => editItem(index);
            tr.className = "cursor-pointer group transition-all duration-200 hover:bg-blue-50/40";
            
            if(item.tipo_fila === 'categoria'){
                catCount++; subCatCount = 0; serviceCount = 0;
                tr.innerHTML = `
                    <td class="text-center font-black text-blue-900 bg-blue-50/50 p-2 text-[11px]">${getLetter(catCount, true)}</td>
                    <td colspan="6" class="italic font-black text-blue-900 bg-blue-50/50 p-2 text-[10px] uppercase tracking-widest">${item.descripcion_especifica}</td>
                    <td class="text-center bg-blue-50/50" onclick="event.stopPropagation()">
                        <button type="button" class="text-red-400 font-black hover:text-red-600" onclick="remove(${index})">×</button>
                    </td>`;
            } 
            else if(item.tipo_fila === 'subcategoria'){
                subCatCount++; serviceCount = 0;
                tr.innerHTML = `
                    <td class="text-center font-bold text-slate-600 bg-slate-50 p-2 text-[9px]">${getLetter(subCatCount, false)}</td>
                    <td colspan="6" class="font-bold text-slate-600 bg-slate-50 p-2 underline decoration-slate-300 text-[9px] uppercase">${item.descripcion_especifica}</td>
                    <td class="text-center bg-slate-50" onclick="event.stopPropagation()">
                        <button type="button" class="text-red-400 font-black hover:text-red-600" onclick="remove(${index})">×</button>
                    </td>`;
            } 
            else {
                serviceCount++; 
                const parcial = item.cantidad * item.precio_unitario;
                subtotal += parcial;
                tr.innerHTML = `
                    <td class="text-center font-bold text-[10px] text-slate-400 pl-4">${serviceCount}</td>
                    <td class="font-bold text-slate-700 p-3 text-[10px]">${item.descripcion_especifica}</td>
                    <td class="text-center text-[10px] font-semibold text-slate-500">${item.norma_nombre || '--'}</td>
                    <td class="text-center font-bold text-slate-600 text-[10px]">${item.cantidad}</td>
                    <td class="text-center text-[9px] font-bold text-slate-400 uppercase">${item.unidad_medida || 'UND'}</td>
                    <td class="text-right font-mono text-slate-500 text-xs">S/ ${parseFloat(item.precio_unitario).toFixed(2)}</td>
                    <td class="text-right font-bold text-blue-600 font-mono pr-4 text-[11px]">S/ ${parcial.toFixed(2)}</td>
                    <td class="text-center" onclick="event.stopPropagation()">
                        <button type="button" class="text-red-400 font-black hover:text-red-600" onclick="remove(${index})">×</button>
                    </td>`;
            }
            body.appendChild(tr);
        });

        // Actualización de inputs ocultos para el POST de Django
        document.getElementById('detalles_json').value = JSON.stringify(DATA_ARRAY);
        
        // Cálculos Finales
        const igv = subtotal * 0.18;
        const total = subtotal + igv;

        document.getElementById('subtotal_cotizacion').textContent = subtotal.toLocaleString('en-US', { minimumFractionDigits: 2 });
        document.getElementById('igv_cotizacion').textContent = igv.toLocaleString('en-US', { minimumFractionDigits: 2 });
        document.getElementById('total_final_cotizacion').textContent = total.toLocaleString('en-US', { minimumFractionDigits: 2 });
        
        const mi = document.getElementById('id_monto_total');
        if (mi) mi.value = total.toFixed(2);
    };

    // --- FORMULARIOS AJAX (CLIENTES, CATEGORÍAS, SUBCATEGORÍAS) ---
    const handleAjaxForm = (formId, url, successCallback) => {
        document.getElementById(formId)?.addEventListener('submit', function(e) {
            e.preventDefault();
            fetch(url, {
                method: 'POST',
                body: new FormData(this),
                headers: { 'X-Requested-With': 'XMLHttpRequest' }
            })
            .then(r => r.json())
            .then(data => {
                if (data.status === 'success') {
                    successCallback(data);
                    this.reset();
                    if (typeof lucide !== 'undefined') lucide.createIcons();
                } else { 
                    alert('Error: ' + (data.message || 'Error desconocido')); 
                }
            }).catch(() => alert('Error de conexión con el servidor'));
        });
    };

    // Callbacks de éxito para formularios rápidos
    handleAjaxForm('formNuevoClienteAjax', config.urlCrearCliente, (data) => {
        tsCliente?.addOption({ 
            value: data.id, 
            text: `${data.ruc} - ${data.razon_social}`, 
            razonSocial: data.razon_social, 
            contacto: data.persona_contacto, 
            correo: data.correo_contacto, 
            telefono: data.celular_contacto 
        });
        tsCliente?.setValue(data.id);
        loadClientData({ dataset: { 
            razonSocial: data.razon_social, 
            contacto: data.persona_contacto, 
            correo: data.correo_contacto, 
            telefono: data.celular_contacto 
        }});
        closeClienteModal();
    });

    handleAjaxForm('formNuevaCategoriaAjax', config.urlCrearCategoria, (data) => {
        const name = data.nombre.toUpperCase();
        tsRegCategoria?.addOption({ value: name, text: name });
        tsRegCategoria?.setValue(name);
        closeCategoriaModal();
    });

    handleAjaxForm('formNuevaSubcategoriaAjax', config.urlCrearSubcategoria, (data) => {
        const name = data.nombre.toUpperCase();
        tsRegSubcategoria?.addOption({ value: name, text: name });
        tsRegSubcategoria?.setValue(name);
        closeSubcategoriaModal();
    });

    // Render inicial
    renderTable();
});