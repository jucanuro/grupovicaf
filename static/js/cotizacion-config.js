document.addEventListener('DOMContentLoaded', () => {
    if (typeof lucide !== 'undefined') lucide.createIcons();

    const config = window.CotizacionConfig || {};
    const ALL_SERVICES = JSON.parse(document.getElementById('all-services-data')?.textContent || '[]');
    const INITIAL_DATA = JSON.parse(document.getElementById('initial-detalles-json')?.textContent || '[]');
    let DATA_ARRAY = INITIAL_DATA;

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
                const regCat = document.getElementById('reg_categoria');
                if(regCat) {
                    const opt = new Option(nombreUpper, nombreUpper);
                    regCat.add(opt);
                }
                closeCategoriaModal();
                this.reset();
            } else { alert(data.message); }
        });
    });

    document.querySelectorAll('select:not(.vicaf-search-select)').forEach(el => {
        el.classList.add('w-full', 'px-3', 'py-2', 'bg-slate-50', 'border', 'border-slate-200', 'rounded-lg', 'text-xs', 'font-bold');
    });

    const tsServicio = new TomSelect('#reg_servicio', {
        options: ALL_SERVICES.map(s => ({ value: s.pk, text: s.nombre })),
        placeholder: 'BUSCAR SERVICIO...',
        onInitialize: function() { this.wrapper.classList.add('vicaf-search'); },
        onChange: (val) => {
            const s = ALL_SERVICES.find(x => String(x.pk) === String(val));
            
            if (s) {
                document.getElementById('reg_norma_txt').textContent = s.NORMA || '---';
                document.getElementById('reg_metodo_txt').textContent = s.METODO || '---';

                const precioBase = s["PRECIO BASE"] || s.PRECIO_BASE || s.precio_base || 0;
                document.getElementById('reg_precio').value = parseFloat(precioBase).toFixed(2);

                document.getElementById('reg_cantidad').value = 1;

                const normaDiv = document.getElementById('reg_norma_txt');
                const metodoDiv = document.getElementById('reg_metodo_txt');
                
                [normaDiv, metodoDiv].forEach(el => {
                    el.classList.remove('text-slate-400', 'italic');
                    el.classList.add('text-slate-700', 'font-bold');
                });

            } else {
                document.getElementById('reg_norma_txt').textContent = '---';
                document.getElementById('reg_metodo_txt').textContent = '---';
                document.getElementById('reg_precio').value = '';
            }
        }
    });

    window.addHeader = (tipo) => {
        const val = document.getElementById(tipo === 'categoria' ? 'reg_categoria' : 'reg_subcategoria')?.value;
        if(!val) return;
        DATA_ARRAY.push({ 
            tipo_fila: tipo, 
            descripcion_especifica: val.toUpperCase() 
        });
        const input = document.getElementById(tipo === 'categoria' ? 'reg_categoria' : 'reg_subcategoria');
        if (input.tagName === 'INPUT') input.value = '';
        renderTable();
    };

    window.addItem = () => {
        const sId = document.getElementById('reg_servicio')?.value;
        if(!sId) return;
        const sel = document.getElementById('reg_servicio');
        DATA_ARRAY.push({
            tipo_fila: 'servicio', 
            servicio_id: sId,
            descripcion_especifica: tsServicio.options[sId].text,
            cantidad: parseFloat(document.getElementById('reg_cantidad').value) || 1,
            precio_unitario: parseFloat(document.getElementById('reg_precio').value) || 0,
            norma_id: sel.dataset.normaId, 
            metodo_id: sel.dataset.metodoId,
            norma_nombre: document.getElementById('reg_norma_txt').textContent,
            unidad_medida: sel.dataset.und
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

        DATA_ARRAY.forEach((item, index) => {
            const tr = document.createElement('tr');
            if(item.tipo_fila === 'categoria'){
                tr.innerHTML = `<td colspan="7" class="pl-4 italic font-black text-blue-800 bg-blue-50/50 p-2 rounded-l-lg">${item.descripcion_especifica}</td><td class="text-center bg-blue-50/50 rounded-r-lg"><button type="button" class="text-red-400 font-black hover:scale-125 transition-transform" onclick="remove(${index})">×</button></td>`;
            } else if(item.tipo_fila === 'subcategoria'){
                tr.innerHTML = `<td></td><td colspan="6" class="font-bold text-slate-600 bg-slate-50 p-2 rounded-l-lg underline decoration-slate-300">${item.descripcion_especifica}</td><td class="text-center bg-slate-50 rounded-r-lg"><button type="button" class="text-red-400 font-black hover:scale-125 transition-transform" onclick="remove(${index})">×</button></td>`;
            } else {
                const parcial = item.cantidad * item.precio_unitario;
                subtotal += parcial;
                tr.className = "bg-white border-b border-slate-100 hover:bg-blue-50/30 transition-colors";
                tr.innerHTML = `
                    <td class="text-center font-mono-tech text-[10px] text-slate-400 pl-4">${index+1}</td>
                    <td class="font-bold text-slate-700 p-3">${item.descripcion_especifica}</td>
                    <td class="text-center text-[10px] font-semibold text-slate-500">${item.norma_nombre || '--'}</td>
                    <td class="text-center font-bold text-slate-600">${item.cantidad}</td>
                    <td class="text-center text-[9px] font-bold text-slate-400 uppercase">${item.unidad_medida}</td>
                    <td class="text-right font-mono-tech text-slate-500 text-xs">S/ ${parseFloat(item.precio_unitario).toFixed(2)}</td>
                    <td class="text-right font-bold text-blue-600 font-mono-tech pr-4">S/ ${parcial.toFixed(2)}</td>
                    <td class="text-center"><button type="button" class="text-red-400 font-black hover:scale-125 transition-transform" onclick="remove(${index})">×</button></td>`;
            }
            body.appendChild(tr);
        });

        document.getElementById('detalles_json').value = JSON.stringify(DATA_ARRAY);
        
        const igv = subtotal * 0.18;
        const total = subtotal + igv;

        document.getElementById('subtotal_cotizacion').textContent = subtotal.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
        document.getElementById('igv_cotizacion').textContent = igv.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
        document.getElementById('total_final_cotizacion').textContent = total.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
        
        const mi = document.getElementById('id_monto_total');
        if (mi) mi.value = total.toFixed(2);
    };

    renderTable();
});