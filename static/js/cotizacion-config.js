document.addEventListener('DOMContentLoaded', () => {
    if (typeof lucide !== 'undefined') lucide.createIcons();
    document.getElementById('id_forma_pago')?.addEventListener('change', function() {
        const customContainer = document.getElementById('pago_personalizado_container');
        if (this.value === 'Personalizado') {
            customContainer.classList.remove('hidden');
        } else {
            customContainer.classList.add('hidden');
        }
    });
    const config = window.CotizacionConfig || {};
    const ALL_SERVICES = JSON.parse(document.getElementById('all-services-data')?.textContent || '[]');
    const INITIAL_DATA = JSON.parse(document.getElementById('initial-detalles-json')?.textContent || '[]');
    let DATA_ARRAY = INITIAL_DATA;

    // --- CARGA DE DATOS DE CLIENTE (INTACTO) ---
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

    const categoriaSelect = document.getElementById('id_servicio_general');
    let tsCategoria = null;
    if (categoriaSelect) {
        tsCategoria = new TomSelect('#id_servicio_general', {
            onInitialize: function() {
                this.wrapper.classList.add('vicaf-search');
            }
        });
    }

    // --- NUEVOS BUSCADORES PARA CABECERA Y SUB-CATEGORÍA ---
    // Se inicializan como TomSelect para que funcionen como buscadores y agreguen al seleccionar
    const tsRegCategoria = new TomSelect('#reg_categoria', {
        onInitialize: function() { this.wrapper.classList.add('vicaf-search'); },
        onChange: function(val) {
            if (val) {
                window.addHeader('categoria', val);
                this.clear(true); // Limpia el buscador después de agregar
            }
        }
    });

    const tsRegSubcategoria = new TomSelect('#reg_subcategoria', {
        onInitialize: function() { this.wrapper.classList.add('vicaf-search'); },
        onChange: function(val) {
            if (val) {
                window.addHeader('subcategoria', val);
                this.clear(true);
            }
        }
    });

    // --- GESTIÓN DE MODALES (INTACTO) ---
    window.openClienteModal = () => {
        const m = document.getElementById('modalCliente');
        if (m) { m.classList.remove('hidden'); document.body.style.overflow = 'hidden'; }
    };
    window.closeClienteModal = () => {
        const m = document.getElementById('modalCliente');
        if (m) { m.classList.add('hidden'); document.body.style.overflow = 'auto'; }
    };
    window.openCategoriaModal = () => {
        const m = document.getElementById('modalCategoria');
        if (m) { m.classList.remove('hidden'); document.body.style.overflow = 'hidden'; }
    };
    window.closeCategoriaModal = () => {
        const m = document.getElementById('modalCategoria');
        if (m) { m.classList.add('hidden'); document.body.style.overflow = 'auto'; }
    };
    window.openSubcategoriaModal = () => {
        const m = document.getElementById('modalSubcategoria');
        if (m) { m.classList.remove('hidden'); document.body.style.overflow = 'hidden'; }
    };
    window.closeSubcategoriaModal = () => {
        const m = document.getElementById('modalSubcategoria');
        if (m) { m.classList.add('hidden'); document.body.style.overflow = 'auto'; }
    };

    // --- FORMULARIOS AJAX (INTACTO) ---
    document.getElementById('formNuevoClienteAjax')?.addEventListener('submit', function(e) {
        e.preventDefault();
        fetch(config.urlCrearCliente, {
            method: 'POST',
            body: new FormData(this),
            headers: { 'X-Requested-With': 'XMLHttpRequest' }
        })
        .then(r => r.json())
        .then(data => {
            if (data.status === 'success') {
                tsCliente?.addOption({
                    value: data.id, text: `${data.ruc} - ${data.razon_social}`,
                    razonSocial: data.razon_social, contacto: data.persona_contacto,
                    correo: data.correo_contacto, telefono: data.celular_contacto
                });
                tsCliente?.setValue(data.id);
                document.getElementById('id_razon_social').value = data.razon_social;
                document.getElementById('id_persona_contacto').value = data.persona_contacto || '';
                document.getElementById('id_correo_contacto').value = data.correo_contacto || '';
                document.getElementById('id_telefono_contacto').value = data.celular_contacto || '';
                closeClienteModal();
                this.reset();
                if (typeof lucide !== 'undefined') lucide.createIcons();
            } else { alert('Error: ' + data.message); }
        }).catch(() => alert('Error de conexión'));
    });

    document.getElementById('formNuevaCategoriaAjax')?.addEventListener('submit', function(e) {
        e.preventDefault();
        fetch(config.urlCrearCategoria, {
            method: 'POST',
            body: new FormData(this),
            headers: { 'X-Requested-With': 'XMLHttpRequest' }
        })
        .then(r => r.json())
        .then(data => {
            if(data.status === 'success') {
                const nombreUpper = data.nombre.toUpperCase();
                tsCategoria?.addOption({ value: data.id, text: nombreUpper });
                tsCategoria?.setValue(data.id);
                // También agregamos al buscador de la tabla
                tsRegCategoria?.addOption({ value: nombreUpper, text: nombreUpper });
                closeCategoriaModal();
                this.reset();
            } else { alert(data.message); }
        });
    });

    // --- FORMULARIO AJAX PARA SUBCATEGORÍA ---
    document.getElementById('formNuevaSubcategoriaAjax')?.addEventListener('submit', function(e) {
        e.preventDefault();
        
        // Usamos la URL configurada en window.CotizacionConfig
        const url = window.CotizacionConfig.urlCrearSubcategoria;

        fetch(url, {
            method: 'POST',
            body: new FormData(this),
            headers: { 'X-Requested-With': 'XMLHttpRequest' }
        })
        .then(r => r.json())
        .then(data => {
            if(data.status === 'success') {
                const nombreUpper = data.nombre.toUpperCase();
                
                // 1. Agregamos al buscador de la tabla (TomSelect de Subcategoría)
                // Asegúrate que 'tsRegSubcategoria' sea el nombre de tu instancia de TomSelect
                if (typeof tsRegSubcategoria !== 'undefined' && tsRegSubcategoria) {
                    tsRegSubcategoria.addOption({ value: nombreUpper, text: nombreUpper });
                    tsRegSubcategoria.setValue(nombreUpper);
                }

                // 2. Cerramos el modal y limpiamos
                closeSubcategoriaModal();
                this.reset();
                
                // Refrescamos iconos de Lucide si es necesario
                if (typeof lucide !== 'undefined') lucide.createIcons();
                
            } else { 
                alert("Error: " + data.message); 
            }
        })
        .catch(err => {
            console.error("Error en la petición:", err);
            alert("Error de conexión al guardar la subcategoría");
        });
    });

    // --- SELECT DE SERVICIO (INTACTO) ---
    const tsServicio = new TomSelect('#reg_servicio', {
        options: ALL_SERVICES.map(s => ({ value: s.pk, text: s.nombre })),
        placeholder: 'BUSCAR SERVICIO...',
        onInitialize: function() { this.wrapper.classList.add('vicaf-search'); },
        onChange: (val) => {
            const s = ALL_SERVICES.find(x => String(x.pk) === String(val));
            if (s) {
                const normaDiv = document.getElementById('reg_norma_txt');
                const metodoDiv = document.getElementById('reg_metodo_txt');
                normaDiv.textContent = s.norma_codigo; 
                metodoDiv.textContent = s.metodo_codigo;
                document.getElementById('reg_precio').value = s.precio_base;
                const elServicio = document.getElementById('reg_servicio');
                elServicio.dataset.normaId = s.norma_pk;
                elServicio.dataset.metodoId = s.metodo_pk;
                elServicio.dataset.und = s.unidad_base || 'UND';
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

    // --- FUNCIONES DE TABLA CON REINICIO DE NUMERACIÓN ---

    const getLetter = (num, upper = true) => {
        const char = String.fromCharCode((upper ? 65 : 97) + (num - 1));
        return char;
    };

    window.addHeader = (tipo, valOverride = null) => {
        // Soporta tanto el valor directo de TomSelect como el valor del select nativo
        let val = valOverride;
        if (!val) {
            const select = document.getElementById(tipo === 'categoria' ? 'reg_categoria' : 'reg_subcategoria');
            val = select?.value;
        }
        
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

        DATA_ARRAY.push({
            tipo_fila: 'servicio', 
            servicio_id: sId,
            descripcion_especifica: sBase.nombre,
            cantidad: parseFloat(document.getElementById('reg_cantidad').value) || 1,
            precio_unitario: parseFloat(document.getElementById('reg_precio').value) || 0,
            norma_id: sBase.norma_pk, 
            metodo_id: sBase.metodo_pk,
            norma_nombre: sBase.norma_codigo + (sBase.metodo_codigo ? ' / ' + sBase.metodo_codigo : ''),
            unidad_medida: sBase.unidad_base || 'UND'
        });
        tsServicio.clear();
        renderTable();
    };

    window.remove = (idx) => { 
        DATA_ARRAY.splice(idx, 1); 
        renderTable(); 
    };

    window.renderTable = () => {
        const body = document.getElementById('cotizacion-detalles');
        if (!body) return;
        body.innerHTML = '';
        
        let subtotal = 0;
        let catCount = 0;      
        let subCatCount = 0;   
        let serviceCount = 0;  

        DATA_ARRAY.forEach((item, index) => {
            const tr = document.createElement('tr');
            
            if(item.tipo_fila === 'categoria'){
                catCount++;
                subCatCount = 0; 
                serviceCount = 0; 
                
                tr.innerHTML = `
                    <td class="text-center font-black text-blue-900 bg-blue-50/50 p-2 rounded-l-lg text-[11px]">${getLetter(catCount, true)}</td>
                    <td colspan="6" class="italic font-black text-blue-900 bg-blue-50/50 p-2 text-[10px] uppercase tracking-widest">
                        ${item.descripcion_especifica}
                    </td>
                    <td class="text-center bg-blue-50/50 rounded-r-lg">
                        <button type="button" class="text-red-400 font-black hover:scale-125 transition-transform" onclick="remove(${index})">×</button>
                    </td>`;
            } 
            else if(item.tipo_fila === 'subcategoria'){
                subCatCount++;
                serviceCount = 0; 
                
                tr.innerHTML = `
                    <td class="text-center font-bold text-slate-600 bg-slate-50 p-2 rounded-l-lg text-[9px]">${getLetter(subCatCount, false)}</td>
                    <td colspan="6" class="font-bold text-slate-600 bg-slate-50 p-2 underline decoration-slate-300 text-[9px] uppercase">
                        ${item.descripcion_especifica}
                    </td>
                    <td class="text-center bg-slate-50 rounded-r-lg">
                        <button type="button" class="text-red-400 font-black hover:scale-125 transition-transform" onclick="remove(${index})">×</button>
                    </td>`;
            } 
            else {
                serviceCount++; 
                const parcial = item.cantidad * item.precio_unitario;
                subtotal += parcial;
                
                tr.className = "bg-white border-b border-slate-100 hover:bg-blue-50/30 transition-colors";
                tr.innerHTML = `
                    <td class="text-center font-bold text-[10px] text-slate-400 pl-4">${serviceCount.toFixed(2)}</td>
                    <td class="font-bold text-slate-700 p-3 text-[10px]">${item.descripcion_especifica}</td>
                    <td class="text-center text-[10px] font-semibold text-slate-500">${item.norma_nombre || '--'}</td>
                    <td class="text-center font-bold text-slate-600 text-[10px]">${item.cantidad}</td>
                    <td class="text-center text-[9px] font-bold text-slate-400 uppercase">${item.unidad_medida || 'UND'}</td>
                    <td class="text-right font-mono text-slate-500 text-xs">S/ ${parseFloat(item.precio_unitario).toFixed(2)}</td>
                    <td class="text-right font-bold text-blue-600 font-mono pr-4 text-[11px]">S/ ${parcial.toFixed(2)}</td>
                    <td class="text-center">
                        <button type="button" class="text-red-400 font-black hover:scale-125 transition-transform" onclick="remove(${index})">×</button>
                    </td>`;
            }
            body.appendChild(tr);
        });

        document.getElementById('detalles_json').value = JSON.stringify(DATA_ARRAY);
        
        const igv = subtotal * 0.18;
        const total = subtotal + igv;

        document.getElementById('subtotal_cotizacion').textContent = subtotal.toLocaleString('en-US', { minimumFractionDigits: 2 });
        document.getElementById('igv_cotizacion').textContent = igv.toLocaleString('en-US', { minimumFractionDigits: 2 });
        document.getElementById('total_final_cotizacion').textContent = total.toLocaleString('en-US', { minimumFractionDigits: 2 });
        
        const mi = document.getElementById('id_monto_total');
        if (mi) mi.value = total.toFixed(2);
    };

    renderTable();
});