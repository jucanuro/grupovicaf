document.addEventListener('DOMContentLoaded', () => {
    if (typeof lucide !== 'undefined') lucide.createIcons();

    let EDIT_INDEX = null;
    const config = window.CotizacionConfig || {};

    const ALL_SERVICES = JSON.parse(document.getElementById('all-services-data')?.textContent || '[]');
    const INITIAL_DATA = JSON.parse(document.getElementById('initial-detalles-json')?.textContent || '[]');
    const INITIAL_CONDICIONES = JSON.parse(document.getElementById('initial-condiciones-json')?.textContent || '[]');

    let DATA_ARRAY = INITIAL_DATA;

    window.CondicionesCotizacionState = {
        secciones: [],
        draftSecciones: [],
        sectionUIState: [],
        puedeEditar: true,
        configurado: false,
    };

    const CONDICIONES_ENDPOINT = (() => {
        const cotizacionId = config.cotizacionId || null;
        if (!cotizacionId) return null;
        return `/servicios/cotizaciones/${cotizacionId}/condiciones/json/`;
    })();

    document.getElementById('id_forma_pago')?.addEventListener('change', function () {
        const customContainer = document.getElementById('pago_personalizado_container');
        if (!customContainer) return;

        if (this.value === 'Personalizado') {
            customContainer.classList.remove('hidden');
        } else {
            customContainer.classList.add('hidden');
        }
    });

    const loadClientData = (opt) => {
        const fields = {
            'id_razon_social': opt?.dataset?.razonSocial || '',
            'id_persona_contacto': opt?.dataset?.contacto || '',
            'id_correo_contacto': opt?.dataset?.correo || '',
            'id_telefono_contacto': opt?.dataset?.telefono || ''
        };

        for (const [id, value] of Object.entries(fields)) {
            const el = document.getElementById(id);
            if (el) el.value = value;
        }
    };

    const getLetter = (num, upper = true) => String.fromCharCode((upper ? 65 : 97) + (num - 1));
    const deepClone = (value) => JSON.parse(JSON.stringify(value || []));

    const clientesSelect = document.getElementById('id_cliente_ruc');
    let tsCliente = null;
    if (clientesSelect) {
        tsCliente = new TomSelect('#id_cliente_ruc', {
            onInitialize: function () {
                this.wrapper.classList.add('vicaf-search');
                if (this.getValue()) {
                    const selected = clientesSelect.options[clientesSelect.selectedIndex];
                    loadClientData(selected);
                }
            },
            onChange: function (value) {
                const selectedOption = Array.from(clientesSelect.options).find(opt => opt.value === value);
                loadClientData(selectedOption);
            }
        });
    }

    const servicioGeneralEl = document.getElementById('id_servicio_general');
    let tsServicioGeneral = null;
    if (servicioGeneralEl) {
        tsServicioGeneral = new TomSelect('#id_servicio_general', {
            onInitialize: function () {
                this.wrapper.classList.add('vicaf-search');
            },
            placeholder: 'BUSCAR CATEGORÍA PRINCIPAL...',
            create: false
        });
    }

    const regCategoriaEl = document.getElementById('reg_categoria');
    let tsRegCategoria = null;
    if (regCategoriaEl) {
        tsRegCategoria = new TomSelect('#reg_categoria', {
            onInitialize: function () {
                this.wrapper.classList.add('vicaf-search');
            },
            onChange: function (val) {
                if (!val || this.isUpdating) return;

                if (EDIT_INDEX !== null && DATA_ARRAY[EDIT_INDEX]?.tipo_fila === 'categoria') {
                    DATA_ARRAY[EDIT_INDEX].descripcion_especifica = val.toUpperCase();
                    window.resetEditor();
                    window.renderTable();
                } else if (EDIT_INDEX === null) {
                    window.addHeader('categoria', val);
                    this.clear(true);
                }
            }
        });
    }

    const regSubcategoriaEl = document.getElementById('reg_subcategoria');
    let tsRegSubcategoria = null;
    if (regSubcategoriaEl) {
        tsRegSubcategoria = new TomSelect('#reg_subcategoria', {
            onInitialize: function () {
                this.wrapper.classList.add('vicaf-search');
            },
            onChange: function (val) {
                if (!val || this.isUpdating) return;

                if (EDIT_INDEX !== null && DATA_ARRAY[EDIT_INDEX]?.tipo_fila === 'subcategoria') {
                    DATA_ARRAY[EDIT_INDEX].descripcion_especifica = val.toUpperCase();
                    window.resetEditor();
                    window.renderTable();
                } else if (EDIT_INDEX === null) {
                    window.addHeader('subcategoria', val);
                    this.clear(true);
                }
            }
        });
    }

    const regServicioEl = document.getElementById('reg_servicio');
    let tsServicio = null;
    if (regServicioEl) {
        tsServicio = new TomSelect('#reg_servicio', {
            options: ALL_SERVICES.map(s => ({ value: s.pk, text: s.nombre })),
            placeholder: 'BUSCAR SERVICIO...',
            onInitialize: function () {
                this.wrapper.classList.add('vicaf-search');
            },
            onChange: function (val) {
                if (this.isUpdating) return;

                const s = ALL_SERVICES.find(x => String(x.pk) === String(val));
                const normaDiv = document.getElementById('reg_norma_txt');
                const metodoDiv = document.getElementById('reg_metodo_txt');
                const precioEl = document.getElementById('reg_precio');

                if (s) {
                    if (normaDiv) {
                        normaDiv.textContent = s.norma_codigo || 'N/A';
                        normaDiv.classList.remove('text-slate-400', 'italic');
                        normaDiv.classList.add('text-slate-700', 'font-bold');
                    }
                    if (metodoDiv) {
                        metodoDiv.textContent = s.metodo_codigo || 'N/A';
                        metodoDiv.classList.remove('text-slate-400', 'italic');
                        metodoDiv.classList.add('text-slate-700', 'font-bold');
                    }
                    if (precioEl) precioEl.value = s.precio_base;
                } else {
                    if (normaDiv) {
                        normaDiv.textContent = 'Auto...';
                        normaDiv.classList.remove('text-slate-700', 'font-bold');
                        normaDiv.classList.add('text-slate-400', 'italic');
                    }
                    if (metodoDiv) {
                        metodoDiv.textContent = 'Auto...';
                        metodoDiv.classList.remove('text-slate-700', 'font-bold');
                        metodoDiv.classList.add('text-slate-400', 'italic');
                    }
                    if (precioEl) precioEl.value = '';
                }
            }
        });
    }

    window.openClienteModal = () => {
        document.getElementById('modalCliente')?.classList.remove('hidden');
        document.body.style.overflow = 'hidden';
    };

    window.closeClienteModal = () => {
        document.getElementById('modalCliente')?.classList.add('hidden');
        document.body.style.overflow = 'auto';
    };

    window.openCategoriaModal = () => {
        document.getElementById('modalCategoria')?.classList.remove('hidden');
        document.body.style.overflow = 'hidden';
    };

    window.closeCategoriaModal = () => {
        document.getElementById('modalCategoria')?.classList.add('hidden');
        document.body.style.overflow = 'auto';
    };

    window.openSubcategoriaModal = () => {
        const m = document.getElementById('modalSubcategoria');
        if (m) {
            m.classList.remove('hidden');
            m.style.display = 'flex';
        }
        document.body.style.overflow = 'hidden';
    };

    window.closeSubcategoriaModal = () => {
        const m = document.getElementById('modalSubcategoria');
        if (m) {
            m.classList.add('hidden');
            m.style.display = 'none';
        }
        document.body.style.overflow = 'auto';
    };

    window.editItem = (index) => {
        const item = DATA_ARRAY[index];
        if (!item) return;

        EDIT_INDEX = index;

        const content = document.getElementById('content-registro');
        if (content && content.classList.contains('hidden') && typeof toggleRegistroPanel === 'function') {
            toggleRegistroPanel();
        }

        if (tsRegCategoria) tsRegCategoria.isUpdating = true;
        if (tsRegSubcategoria) tsRegSubcategoria.isUpdating = true;
        if (tsServicio) tsServicio.isUpdating = true;

        tsRegCategoria?.clear(true);
        tsRegSubcategoria?.clear(true);
        tsServicio?.clear(true);

        if (item.tipo_fila === 'categoria' && tsRegCategoria) {
            if (!tsRegCategoria.options[item.descripcion_especifica]) {
                tsRegCategoria.addOption({ value: item.descripcion_especifica, text: item.descripcion_especifica });
            }
            tsRegCategoria.setValue(item.descripcion_especifica);
        } else if (item.tipo_fila === 'subcategoria' && tsRegSubcategoria) {
            if (!tsRegSubcategoria.options[item.descripcion_especifica]) {
                tsRegSubcategoria.addOption({ value: item.descripcion_especifica, text: item.descripcion_especifica });
            }
            tsRegSubcategoria.setValue(item.descripcion_especifica);
        } else {
            tsServicio?.setValue(item.servicio_id);
            const cantidadEl = document.getElementById('reg_cantidad');
            const precioEl = document.getElementById('reg_precio');
            if (cantidadEl) cantidadEl.value = item.cantidad;
            if (precioEl) precioEl.value = item.precio_unitario;
        }

        if (tsRegCategoria) tsRegCategoria.isUpdating = false;
        if (tsRegSubcategoria) tsRegSubcategoria.isUpdating = false;
        if (tsServicio) tsServicio.isUpdating = false;

        const btn = document.querySelector('button[onclick="addItem()"]');
        if (btn) {
            btn.innerHTML = `<i data-lucide="refresh-cw" class="w-4 h-4"></i> ACTUALIZAR ÍTEM`;
            btn.classList.replace('bg-slate-900', 'bg-orange-600');
            if (typeof lucide !== 'undefined') lucide.createIcons();
        }

        content?.scrollIntoView({ behavior: 'smooth', block: 'center' });
    };

    window.resetEditor = () => {
        EDIT_INDEX = null;

        if (tsRegCategoria) tsRegCategoria.isUpdating = true;
        if (tsRegSubcategoria) tsRegSubcategoria.isUpdating = true;
        if (tsServicio) tsServicio.isUpdating = true;

        tsRegCategoria?.clear(true);
        tsRegSubcategoria?.clear(true);
        tsServicio?.clear(true);

        if (tsRegCategoria) tsRegCategoria.isUpdating = false;
        if (tsRegSubcategoria) tsRegSubcategoria.isUpdating = false;
        if (tsServicio) tsServicio.isUpdating = false;

        const cantidadEl = document.getElementById('reg_cantidad');
        const precioEl = document.getElementById('reg_precio');
        if (cantidadEl) cantidadEl.value = '1';
        if (precioEl) precioEl.value = '';

        const btn = document.querySelector('button[onclick="addItem()"]');
        if (btn) {
            btn.innerHTML = `<i data-lucide="plus-circle" class="w-4 h-4"></i> Agregar Ítem al Detalle`;
            btn.classList.replace('bg-orange-600', 'bg-slate-900');
            if (typeof lucide !== 'undefined') lucide.createIcons();
        }
    };

    window.applyPlantillaDetalles = (detalles = []) => {
        if (!Array.isArray(detalles)) return;

        DATA_ARRAY.length = 0;

        detalles.forEach(item => {
            const sBase = ALL_SERVICES.find(x => String(x.pk) === String(item.servicio_id));

            if (item.tipo_fila === 'categoria' || item.tipo_fila === 'subcategoria') {
                DATA_ARRAY.push({
                    tipo_fila: item.tipo_fila,
                    descripcion_especifica: item.descripcion_especifica ? item.descripcion_especifica.toUpperCase() : ''
                });
            } else if (item.tipo_fila === 'servicio') {
                DATA_ARRAY.push({
                    tipo_fila: 'servicio',
                    servicio_id: item.servicio_id,
                    descripcion_especifica: item.descripcion_especifica || (sBase ? sBase.nombre : ''),
                    cantidad: parseFloat(item.cantidad) || 1,
                    precio_unitario: parseFloat(item.precio_unitario) || 0,
                    norma_nombre: sBase ? (sBase.norma_codigo + (sBase.metodo_codigo ? ' / ' + sBase.metodo_codigo : '')) : '',
                    unidad_medida: item.unidad_medida || (sBase ? sBase.unidad_base : 'UND')
                });
            }
        });

        window.renderTable();
    };

    window.addHeader = (tipo, valOverride = null) => {
        const val = valOverride || document.getElementById(tipo === 'categoria' ? 'reg_categoria' : 'reg_subcategoria')?.value;
        if (!val) return;

        DATA_ARRAY.push({
            tipo_fila: tipo,
            descripcion_especifica: val.toUpperCase()
        });

        window.renderTable();
    };

    window.addItem = () => {
        const sId = document.getElementById('reg_servicio')?.value;
        if (!sId) return;

        const sBase = ALL_SERVICES.find(x => String(x.pk) === String(sId));
        if (!sBase) return;

        const cantidadEl = document.getElementById('reg_cantidad');
        const precioEl = document.getElementById('reg_precio');

        const data = {
            tipo_fila: 'servicio',
            servicio_id: sId,
            descripcion_especifica: sBase.nombre,
            cantidad: parseFloat(cantidadEl?.value) || 1,
            precio_unitario: parseFloat(precioEl?.value) || 0,
            norma_id: sBase.norma_pk,
            metodo_id: sBase.metodo_pk,
            norma_nombre: sBase.norma_codigo + (sBase.metodo_codigo ? ' / ' + sBase.metodo_codigo : ''),
            unidad_medida: sBase.unidad_base || 'UND'
        };

        if (EDIT_INDEX !== null) {
            DATA_ARRAY[EDIT_INDEX] = data;
            window.resetEditor();
        } else {
            DATA_ARRAY.push(data);
            tsServicio?.clear();
        }

        window.renderTable();
    };

    window.remove = (idx) => {
        DATA_ARRAY.splice(idx, 1);
        if (EDIT_INDEX === idx) window.resetEditor();
        window.renderTable();
    };

    window.moveItemUp = (idx) => {
        if (idx > 0) {
            [DATA_ARRAY[idx - 1], DATA_ARRAY[idx]] = [DATA_ARRAY[idx], DATA_ARRAY[idx - 1]];
            window.renderTable();
        }
    };

    window.moveItemDown = (idx) => {
        if (idx < DATA_ARRAY.length - 1) {
            [DATA_ARRAY[idx + 1], DATA_ARRAY[idx]] = [DATA_ARRAY[idx], DATA_ARRAY[idx + 1]];
            window.renderTable();
        }
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
            tr.onclick = () => window.editItem(index);
            tr.className = 'cursor-pointer group transition-all duration-200 hover:bg-blue-50/40';

            const controls = `
                <div class="flex gap-1" onclick="event.stopPropagation()">
                    <button type="button" class="text-slate-400 hover:text-blue-600" onclick="moveItemUp(${index})">▲</button>
                    <button type="button" class="text-slate-400 hover:text-blue-600" onclick="moveItemDown(${index})">▼</button>
                    <button type="button" class="text-red-400 font-black hover:text-red-600 ml-2" onclick="remove(${index})">×</button>
                </div>`;

            if (item.tipo_fila === 'categoria') {
                catCount++;
                subCatCount = 0;
                serviceCount = 0;

                tr.innerHTML = `
                    <td class="text-center font-black text-blue-900 bg-blue-50/50 p-2 text-[11px]">${getLetter(catCount, true)}</td>
                    <td colspan="6" class="italic font-black text-blue-900 bg-blue-50/50 p-2 text-[10px] uppercase tracking-widest">${item.descripcion_especifica}</td>
                    <td class="text-center bg-blue-50/50">${controls}</td>
                `;
            } else if (item.tipo_fila === 'subcategoria') {
                subCatCount++;
                serviceCount = 0;

                tr.innerHTML = `
                    <td class="text-center font-bold text-slate-600 bg-slate-50 p-2 text-[9px]">${getLetter(subCatCount, false)}</td>
                    <td colspan="6" class="font-bold text-slate-600 bg-slate-50 p-2 underline decoration-slate-300 text-[9px] uppercase">${item.descripcion_especifica}</td>
                    <td class="text-center bg-slate-50">${controls}</td>
                `;
            } else {
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
                    <td class="text-center">${controls}</td>
                `;
            }

            body.appendChild(tr);
        });

        const detallesInput = document.getElementById('detalles_json');
        if (detallesInput) detallesInput.value = JSON.stringify(DATA_ARRAY);

        const igv = subtotal * 0.18;
        const total = subtotal + igv;

        const subtotalEl = document.getElementById('subtotal_cotizacion');
        const igvEl = document.getElementById('igv_cotizacion');
        const totalEl = document.getElementById('total_final_cotizacion');
        const montoInput = document.getElementById('id_monto_total');

        if (subtotalEl) subtotalEl.textContent = subtotal.toLocaleString('en-US', { minimumFractionDigits: 2 });
        if (igvEl) igvEl.textContent = igv.toLocaleString('en-US', { minimumFractionDigits: 2 });
        if (totalEl) totalEl.textContent = total.toLocaleString('en-US', { minimumFractionDigits: 2 });
        if (montoInput) montoInput.value = total.toFixed(2);
    };

    const handleAjaxForm = (formId, url, successCallback) => {
        document.getElementById(formId)?.addEventListener('submit', function (e) {
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
                })
                .catch(() => alert('Error de conexión con el servidor'));
        });
    };

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

        loadClientData({
            dataset: {
                razonSocial: data.razon_social,
                contacto: data.persona_contacto,
                correo: data.correo_contacto,
                telefono: data.celular_contacto
            }
        });

        window.closeClienteModal();
    });

    handleAjaxForm('formNuevaCategoriaAjax', config.urlCrearCategoria, () => {
        window.closeCategoriaModal();
        window.location.reload();
    });

    handleAjaxForm('formNuevaSubcategoriaAjax', config.urlCrearSubcategoria, (data) => {
        const name = data.nombre.toUpperCase();
        tsRegSubcategoria?.addOption({ value: name, text: name });
        tsRegSubcategoria?.setValue(name);
        window.closeSubcategoriaModal();
    });

    window.cargarPlantillaAjax = async (plantillaId) => {
        if (!plantillaId) return;

        const select = document.getElementById('select-plantilla-modal');
        if (select) select.disabled = true;

        try {
            const baseUrl = window.CotizacionConfig?.urlPlantillaBase || '/servicios/api/plantilla/';
            const response = await fetch(`${baseUrl}${plantillaId}/`);
            const data = await response.json();

            if (!response.ok || !data.success) {
                alert('Error cargando plantilla');
                return;
            }

            if (Array.isArray(data.detalles)) {
                window.applyPlantillaDetalles?.(data.detalles);
            }

            if (Array.isArray(data.condiciones)) {
                const normalizadas = data.condiciones.map(normalizeCondicionSeccion);

                window.CondicionesCotizacionState.draftSecciones = deepClone(normalizadas);

                syncSeccionSeleccionState();

                window.CondicionesCotizacionState.secciones =
                    deepClone(window.CondicionesCotizacionState.draftSecciones);

                window.CondicionesCotizacionState.sectionUIState =
                    normalizadas.map(() => false);

                window.CondicionesCotizacionState.configurado =
                    hasAnySelection(window.CondicionesCotizacionState.secciones);

                currentSectionIndex = 0;

                refreshCondicionesBuilder();
            }

            if (data.plantilla) {
                const asuntoEl = document.getElementById('id_asunto_servicio');
                const formaPagoEl = document.getElementById('id_forma_pago');
                const tiempoEntregaEl = document.querySelector('input[name="tiempo_entrega"]');
                const servicioGeneralEl = document.getElementById('id_servicio_general');

                if (asuntoEl && data.plantilla.asunto_referencial) {
                    asuntoEl.value = data.plantilla.asunto_referencial;
                }

                if (formaPagoEl && data.plantilla.forma_pago_defecto) {
                    formaPagoEl.value = data.plantilla.forma_pago_defecto;
                    formaPagoEl.dispatchEvent(new Event('change'));
                }

                if (tiempoEntregaEl && data.plantilla.plazo_entrega_defecto) {
                    tiempoEntregaEl.value = data.plantilla.plazo_entrega_defecto;
                }

                if (servicioGeneralEl && data.plantilla.servicio_general_id) {
                    servicioGeneralEl.value = data.plantilla.servicio_general_id;

                    if (typeof tsServicioGeneral !== 'undefined' && tsServicioGeneral) {
                        tsServicioGeneral.setValue(String(data.plantilla.servicio_general_id));
                    }
                }
            }
        } catch (error) {
            console.error(error);
            alert('Error al cargar plantilla');
        } finally {
            if (select) select.disabled = false;
        }
    };

    window.applyPlantillaCondiciones = (condiciones = []) => {
        if (!Array.isArray(condiciones)) return;
        const normalizadas = condiciones.map(normalizeCondicionSeccion);
        window.CondicionesCotizacionState.draftSecciones = deepClone(normalizadas);
        syncSeccionSeleccionState();
        window.CondicionesCotizacionState.secciones =
            deepClone(window.CondicionesCotizacionState.draftSecciones);
        window.CondicionesCotizacionState.sectionUIState =
            normalizadas.map(() => false);
        window.CondicionesCotizacionState.configurado =
            hasAnySelection(window.CondicionesCotizacionState.secciones);
        currentSectionIndex = 0;
        refreshCondicionesBuilder();
    };

    window.seleccionarModo = (modo) => {
        if (modo === 'vacio') {
            if (confirm('¿Estás seguro de limpiar todo el detalle actual?')) {
                DATA_ARRAY = [];
                const select = document.getElementById('select-plantilla-modal');
                if (select) select.value = '';
                window.renderTable();
            }
        }
    };

    function escapeHtml(value) {
        return String(value || '')
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;')
            .replace(/'/g, '&#039;');
    }

    function escapeTextarea(value) {
        return String(value || '')
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;');
    }

    function getCondicionesInput() {
        return document.getElementById('condiciones_json');
    }

    function normalizeCondicionItem(item) {
        return {
            id: item?.id ?? null,
            catalogo_item_id: item?.catalogo_item_id ?? null,
            parent_id: item?.parent_id ?? null,
            tipo_nodo: item?.tipo_nodo || 'item',
            titulo: item?.titulo || '',
            texto: item?.texto || item?.texto_final || item?.texto_base || '',
            texto_base: item?.texto_base || item?.texto_final || item?.texto || '',
            texto_final: item?.texto_final || item?.texto_base || item?.texto || '',
            orden: item?.orden ?? 0,
            nivel: item?.nivel ?? 0,
            seleccionado: !!item?.seleccionado,
            es_obligatorio: !!item?.es_obligatorio,
            editable_en_cotizacion: item?.editable_en_cotizacion !== false,
            fue_editado: !!item?.fue_editado,
            children: Array.isArray(item?.children) ? item.children.map(normalizeCondicionItem) : []
        };
    }

    function normalizeCondicionSeccion(seccion) {
        const items = Array.isArray(seccion?.items)
            ? seccion.items.map(normalizeCondicionItem)
            : [];

        const yaEstaConfigurado = !!window.CondicionesCotizacionState?.configurado;

        return {
            id: seccion?.id ?? null,
            catalogo_seccion_id: seccion?.catalogo_seccion_id ?? null,
            codigo: seccion?.codigo || '',
            titulo: seccion?.titulo || '',
            tipo: seccion?.tipo || 'lista',
            orden: seccion?.orden ?? 0,
            seleccionada: yaEstaConfigurado ? !!seccion?.seleccionada : false,
            items: items
        };
    }

    function getCondicionesFromScript() {
        try {
            const raw = document.getElementById('initial-condiciones-json')?.textContent?.trim() || '[]';
            const parsed = JSON.parse(raw);
            if (!Array.isArray(parsed)) return [];
            return parsed.map(normalizeCondicionSeccion);
        } catch (error) {
            console.error('Error parseando initial-condiciones-json:', error);
            return [];
        }
    }

    async function fetchCondicionesFallback() {
        if (!CONDICIONES_ENDPOINT) return [];

        try {
            const response = await fetch(CONDICIONES_ENDPOINT, {
                headers: { 'X-Requested-With': 'XMLHttpRequest' }
            });
            const data = await response.json();

            if (!response.ok || !data.success || !Array.isArray(data.secciones)) {
                return [];
            }

            return data.secciones.map(normalizeCondicionSeccion);
        } catch (error) {
            console.error('Error cargando condiciones por endpoint:', error);
            return [];
        }
    }

    function getCondicionesIniciales() {
        const input = getCondicionesInput();

        if (input && input.value) {
            try {
                const parsed = JSON.parse(input.value);
                if (Array.isArray(parsed)) return deepClone(parsed);
            } catch (error) {
                console.error(error);
            }
        }

        if (Array.isArray(INITIAL_CONDICIONES) && INITIAL_CONDICIONES.length) {
            return deepClone(INITIAL_CONDICIONES.map(normalizeCondicionSeccion));
        }

        return [];
    }

    function syncCondicionesInput() {
        const input = getCondicionesInput();
        if (!input) return;
        input.value = JSON.stringify(window.CondicionesCotizacionState.secciones || []);
    }

    function countSelectedItems(items = []) {
        let total = 0;
        items.forEach(item => {
            if (item.seleccionado && item.tipo_nodo !== 'grupo') {
                total += 1;
            }
            if (item.children?.length) {
                total += countSelectedItems(item.children);
            }
        });
        return total;
    }

    function countAllRenderableItems(items = []) {
        let total = 0;
        items.forEach(item => {
            total += 1;
            if (item.children?.length) {
                total += countAllRenderableItems(item.children);
            }
        });
        return total;
    }

    function hasAnySelection(secciones = []) {
        return secciones.some(seccion =>
            seccion.seleccionada || countSelectedItems(seccion.items || []) > 0
        );
    }

    function getItemByPath(path) {
        const indexes = String(path).split('-').map(x => parseInt(x, 10));
        let item = window.CondicionesCotizacionState.draftSecciones[indexes[0]]?.items?.[indexes[1]];

        for (let i = 2; i < indexes.length; i++) {
            item = item?.children?.[indexes[i]];
        }

        return item;
    }

    function resetCondicionItemSeleccionManual(item) {
        return {
            ...item,
            seleccionado: false,
            children: (item.children || []).map(resetCondicionItemSeleccionManual)
        };
    }

    function resetCondicionesSeleccionManual(secciones = []) {
        return (secciones || []).map(seccion => ({
            ...seccion,
            seleccionada: false,
            items: (seccion.items || []).map(resetCondicionItemSeleccionManual)
        }));
    }

    function hasSelectedItemsInTree(items = []) {
        for (const item of items) {
            if (item.seleccionado) return true;
            if (item.children?.length && hasSelectedItemsInTree(item.children)) return true;
        }
        return false;
    }

    function syncSeccionSeleccionState() {
        window.CondicionesCotizacionState.draftSecciones.forEach(seccion => {
            seccion.seleccionada = hasSelectedItemsInTree(seccion.items || []);
        });
    }

    function marcarItemRecursivo(item, checked) {
        item.seleccionado = checked;
        (item.children || []).forEach(child => marcarItemRecursivo(child, checked));
    }

    function marcarChildrenRecursivo(item, checked) {
        (item.children || []).forEach(child => {
            child.seleccionado = checked;
            marcarChildrenRecursivo(child, checked);
        });
    }

    function marcarChildrenRecursivo(item, checked) {
        (item.children || []).forEach(child => {
            if (!child.es_obligatorio) child.seleccionado = checked;
            marcarChildrenRecursivo(child, checked);
        });
    }

    function marcarItemRecursivo(item, checked) {
        if (!item.es_obligatorio) item.seleccionado = checked;
        (item.children || []).forEach(child => marcarItemRecursivo(child, checked));
    }

    function autoResizeCondicionTextarea(textarea) {
        if (!textarea) return;

        textarea.style.height = 'auto';

        const minHeight = 52;
        const maxHeight = 180;
        const nextHeight = Math.min(Math.max(textarea.scrollHeight, minHeight), maxHeight);

        textarea.style.height = `${nextHeight}px`;
        textarea.style.overflowY = textarea.scrollHeight > maxHeight ? 'auto' : 'hidden';
    }

    function initializeCondicionesTextareas() {
        document.querySelectorAll('.condicion-textarea').forEach(textarea => {
            autoResizeCondicionTextarea(textarea);
        });
    }

    function renderCondicionItem(item, path) {
        const children = item.children || [];
        const hasChildren = children.length > 0;
        const readonly = !window.CondicionesCotizacionState.puedeEditar || item.es_obligatorio;
        const selectedClass = item.seleccionado
            ? 'border-emerald-300 bg-emerald-50/60 shadow-sm'
            : 'border-slate-200 bg-white';

        return `
            <div class="rounded-2xl border ${selectedClass} transition-all duration-200">
                <div class="p-4 md:p-5">
                    <div class="flex items-start gap-4">
                        <div class="pt-1">
                            <input type="checkbox"
                                class="w-5 h-5 rounded-md border-slate-300 text-emerald-600 focus:ring-emerald-500"
                                ${item.seleccionado ? 'checked' : ''}
                                ${readonly ? 'disabled' : ''}
                                onchange="toggleItemCondicion('${path}', this.checked)">
                        </div>

                        <div class="flex-1 min-w-0">
                            <div class="flex flex-col lg:flex-row lg:items-start lg:justify-between gap-3 mb-3">
                                <div class="min-w-0">
                                    ${item.titulo ? `
                                        <div class="text-[11px] font-black text-slate-500 uppercase tracking-[0.16em] mb-1">
                                            ${escapeHtml(item.titulo)}
                                        </div>
                                    ` : ''}
                                    <div class="text-[11px] font-bold text-slate-400 uppercase tracking-wider">
                                        ${item.seleccionado ? 'Seleccionado' : 'No seleccionado'}
                                    </div>
                                </div>
                            </div>

                            <div class="rounded-2xl border border-slate-200 bg-white overflow-hidden focus-within:border-emerald-400 focus-within:ring-4 focus-within:ring-emerald-500/10 transition-all">
                                <textarea
                                    class="condicion-textarea w-full px-4 py-3 bg-transparent border-none text-[13px] leading-6 font-medium text-slate-700 outline-none resize-none"
                                    data-path="${path}"
                                    rows="1"
                                    ${(!window.CondicionesCotizacionState.puedeEditar || !item.editable_en_cotizacion) ? 'readonly' : ''}
                                    oninput="editarTextoCondicion('${path}', this.value); autoResizeCondicionTextarea(this);"
                                >${escapeTextarea(item.texto_final || '')}</textarea>
                            </div>
                        </div>
                    </div>
                </div>

                ${hasChildren ? `
                    <div class="px-4 md:px-5 pb-4">
                        <div class="ml-3 pl-5 border-l-2 border-slate-200 space-y-3">
                            ${children.map((child, index) => renderCondicionItem(child, `${path}-${index}`)).join('')}
                        </div>
                    </div>
                ` : ''}
            </div>
        `;
    }

    function renderCondicionesModal() {
        const body = document.getElementById('condiciones-modal-body');
        const meta = document.getElementById('condiciones-modal-meta');
        const btnAplicar = document.getElementById('btnAplicarCondicionesModal');
        const state = window.CondicionesCotizacionState;

        if (!body) return;

        if (!Array.isArray(state.sectionUIState)) {
            state.sectionUIState = [];
        }

        if (meta) {
            const totalSecciones = state.draftSecciones.length;
            const seleccionadas = state.draftSecciones.filter(s => s.seleccionada).length;
            meta.innerHTML = `
                <span class="w-2 h-2 rounded-full ${seleccionadas ? 'bg-emerald-500' : 'bg-slate-400'}"></span>
                ${seleccionadas} de ${totalSecciones} secciones activas
            `;
        }

        if (btnAplicar) {
            btnAplicar.disabled = !state.puedeEditar;
            btnAplicar.classList.toggle('opacity-50', !state.puedeEditar);
            btnAplicar.classList.toggle('cursor-not-allowed', !state.puedeEditar);
        }

        if (!state.draftSecciones.length) {
            body.innerHTML = `
                <div class="rounded-2xl border border-slate-200 bg-white px-5 py-6 text-sm font-semibold text-slate-500">
                    No hay condiciones cargadas para configurar.
                </div>
            `;
            if (typeof lucide !== 'undefined') lucide.createIcons();
            return;
        }

        body.innerHTML = state.draftSecciones.map((seccion, sectionIndex) => {
            const isOpen = !!state.sectionUIState[sectionIndex];
            const selectedCount = countSelectedItems(seccion.items || []);
            const totalItems = countAllRenderableItems(seccion.items || []);
            const sectionIsSelected = selectedCount > 0;

            seccion.seleccionada = sectionIsSelected;

            const sectionSelectedClass = sectionIsSelected
                ? 'border-emerald-300 bg-emerald-50/40'
                : 'border-slate-200 bg-white';

            return `
                <div class="rounded-[1.5rem] border ${sectionSelectedClass} shadow-sm overflow-hidden transition-all duration-200">
                    <div class="flex items-center justify-between gap-4 px-5 py-4 bg-white border-b border-slate-100">
                        <div class="flex items-center gap-4 min-w-0">
                            <input type="checkbox"
                                class="w-5 h-5 rounded-md border-slate-300 text-emerald-600 focus:ring-emerald-500"
                                ${sectionIsSelected ? 'checked' : ''}
                                ${state.puedeEditar ? '' : 'disabled'}
                                onchange="toggleSeccionCondicion(${sectionIndex}, this.checked)">

                            <button type="button"
                                    class="min-w-0 text-left"
                                    onclick="toggleCondicionAccordion(${sectionIndex})">
                                <div class="text-sm font-black text-slate-900 uppercase tracking-tight truncate">
                                    ${escapeHtml(seccion.titulo || '')}
                                </div>
                                <div class="text-[10px] font-bold text-slate-400 uppercase tracking-[0.16em] mt-1">
                                    ${escapeHtml(seccion.codigo || '')}
                                </div>
                            </button>
                        </div>

                        <div class="flex items-center gap-3 shrink-0">
                            <div class="hidden md:flex items-center gap-2">
                                <span class="px-2.5 py-1 rounded-full bg-slate-100 text-slate-600 text-[10px] font-black uppercase">
                                    ${totalItems} texto(s)
                                </span>
                                <span class="px-2.5 py-1 rounded-full bg-emerald-100 text-emerald-700 text-[10px] font-black uppercase">
                                    ${selectedCount} seleccionado(s)
                                </span>
                            </div>

                            <button type="button"
                                    class="w-9 h-9 rounded-xl border border-slate-200 bg-white text-slate-500 hover:bg-slate-50 transition-all"
                                    onclick="toggleCondicionAccordion(${sectionIndex})">
                                <i data-lucide="${isOpen ? 'chevron-up' : 'chevron-down'}" class="w-4 h-4 mx-auto"></i>
                            </button>
                        </div>
                    </div>

                    <div class="${isOpen ? 'block' : 'hidden'} bg-slate-50/40">
                        <div class="p-4 md:p-5 space-y-3">
                            ${(seccion.items || []).map((item, itemIndex) =>
                                renderCondicionItem(item, `${sectionIndex}-${itemIndex}`)
                            ).join('') || '<div class="text-sm text-slate-400 font-semibold">Sin ítems</div>'}
                        </div>
                    </div>
                </div>
            `;
        }).join('');

        initializeCondicionesTextareas();

        if (typeof lucide !== 'undefined') lucide.createIcons();
    }

    function actualizarResumenCondicionesLocal() {
        const box = document.getElementById('condiciones-resumen-box');
        const badge = document.getElementById('condiciones-status-badge');
        const secciones = window.CondicionesCotizacionState.secciones || [];

        if (!box || !badge) return;

        if (!secciones.length || !hasAnySelection(secciones)) {
            box.innerHTML = `
                <div class="text-[11px] text-slate-500 font-semibold">
                    Sin contenido configurado
                </div>
            `;
            badge.textContent = 'Sin configurar';
            badge.className = 'px-3 py-1 rounded-full bg-slate-100 text-slate-600 text-[10px] font-black uppercase tracking-wider';
            return;
        }

        const resumen = secciones
            .map(seccion => ({
                titulo: seccion.titulo || '',
                items_seleccionados: countSelectedItems(seccion.items || [])
            }))
            .filter(item => item.items_seleccionados > 0);

        if (!resumen.length) {
            box.innerHTML = `
                <div class="text-[11px] text-slate-500 font-semibold">
                    Sin contenido configurado
                </div>
            `;
            badge.textContent = 'Sin configurar';
            badge.className = 'px-3 py-1 rounded-full bg-slate-100 text-slate-600 text-[10px] font-black uppercase tracking-wider';
            return;
        }

        box.innerHTML = `
            <div class="flex flex-wrap gap-2">
                ${resumen.map(item => `
                    <div class="inline-flex items-center gap-2 px-3 py-1.5 rounded-full bg-white border border-slate-200 text-[11px] font-semibold text-slate-700 shadow-sm">
                        <span class="truncate max-w-[150px]">${escapeHtml(item.titulo)}</span>
                        <span class="px-2 py-[2px] rounded-full bg-emerald-100 text-emerald-700 text-[10px] font-black">
                            ${item.items_seleccionados}
                        </span>
                    </div>
                `).join('')}
            </div>
        `;

        badge.textContent = 'Configurado';
        badge.className = 'px-3 py-1 rounded-full bg-emerald-100 text-emerald-700 text-[10px] font-black uppercase tracking-wider';
    }

    async function initializeCondicionesState() {
        let base = getCondicionesFromScript();

        if (!base.length) {
            base = await fetchCondicionesFallback();
        }

        if (!base.length) {
            base = getCondicionesIniciales();
        }

        window.CondicionesCotizacionState.secciones = deepClone(base);
        window.CondicionesCotizacionState.draftSecciones = deepClone(base);
        window.CondicionesCotizacionState.sectionUIState = (base || []).map(() => false);
        window.CondicionesCotizacionState.configurado = hasAnySelection(base);
        syncCondicionesInput();
        actualizarResumenCondicionesLocal();
    }

    window.toggleCondicionAccordion = (sectionIndex) => {
        if (!Array.isArray(window.CondicionesCotizacionState.sectionUIState)) {
            window.CondicionesCotizacionState.sectionUIState = [];
        }

        window.CondicionesCotizacionState.sectionUIState[sectionIndex] =
            !window.CondicionesCotizacionState.sectionUIState[sectionIndex];

        renderCondicionesModal();
    };

    window.abrirModalCondicionesCotizacion = async () => {
        if (!window.CondicionesCotizacionState.secciones.length) {
            await initializeCondicionesState();
        }

        const base = window.CondicionesCotizacionState.secciones.length
            ? deepClone(window.CondicionesCotizacionState.secciones)
            : getCondicionesIniciales();

        const yaHaySeleccion = hasAnySelection(base);

        window.CondicionesCotizacionState.draftSecciones = yaHaySeleccion
            ? deepClone(base)
            : resetCondicionesSeleccionManual(base);

        if (
            !Array.isArray(window.CondicionesCotizacionState.sectionUIState) ||
            window.CondicionesCotizacionState.sectionUIState.length !== window.CondicionesCotizacionState.draftSecciones.length
        ) {
            window.CondicionesCotizacionState.sectionUIState =
                window.CondicionesCotizacionState.draftSecciones.map(() => false);
        }

        renderCondicionesModal();
        syncCondicionesInput();
        actualizarResumenCondicionesLocal();
    };

    window.cerrarModalCondicionesCotizacion = () => {
        const modal = document.getElementById('modalCondicionesCotizacion');
        if (!modal) return;

        modal.classList.add('hidden');
        modal.classList.remove('block');

        document.documentElement.classList.remove('modal-open');
        document.body.classList.remove('modal-open');
    };

    window.cargarCondicionesDesdeDataLocal = () => {
        const base = window.CondicionesCotizacionState.secciones.length
            ? deepClone(window.CondicionesCotizacionState.secciones)
            : getCondicionesIniciales();

        const yaHaySeleccion = hasAnySelection(base);

        window.CondicionesCotizacionState.draftSecciones = yaHaySeleccion
            ? deepClone(base)
            : resetCondicionesSeleccionManual(base);

        if (
            !Array.isArray(window.CondicionesCotizacionState.sectionUIState) ||
            window.CondicionesCotizacionState.sectionUIState.length !== window.CondicionesCotizacionState.draftSecciones.length
        ) {
            window.CondicionesCotizacionState.sectionUIState =
                window.CondicionesCotizacionState.draftSecciones.map(() => false);
        }

        renderCondicionesModal();
    };

    function commitCondicionesDraft() {
        syncSeccionSeleccionState();

        window.CondicionesCotizacionState.secciones =
            deepClone(window.CondicionesCotizacionState.draftSecciones || []);

        window.CondicionesCotizacionState.configurado =
            hasAnySelection(window.CondicionesCotizacionState.secciones);

        syncCondicionesInput();
        actualizarResumenCondicionesLocal();
    }

    function refreshCondicionesBuilder() {
        syncSeccionSeleccionState();
        syncCondicionesInput();
        actualizarResumenCondicionesLocal();

        if (typeof renderSidebar === 'function') renderSidebar();
        if (typeof renderEditor === 'function') renderEditor();
    }

    window.toggleSeccionCondicion = (sectionIndex, checked) => {
        const seccion = window.CondicionesCotizacionState.draftSecciones[sectionIndex];
        if (!seccion) return;

        seccion.seleccionada = checked;
        (seccion.items || []).forEach(item => marcarItemRecursivo(item, checked));

        commitCondicionesDraft();
        refreshCondicionesBuilder();
    };


    window.toggleItemCondicion = (path, checked) => {
        const item = getItemByPath(path);
        if (!item) return;

        item.seleccionado = checked;
        (item.children || []).forEach(child => marcarItemRecursivo(child, checked));

        commitCondicionesDraft();
        refreshCondicionesBuilder();
    };

    window.editarTextoCondicion = (path, value) => {
        const item = getItemByPath(path);
        if (!item) return;

        item.texto_final = value;
        item.fue_editado = (item.texto_base || '').trim() !== (value || '').trim();

        commitCondicionesDraft();
    };

    window.autoResizeCondicionTextarea = autoResizeCondicionTextarea;

    window.seleccionarTodoCondiciones = () => {
        window.CondicionesCotizacionState.draftSecciones.forEach(seccion => {
            seccion.seleccionada = true;
            (seccion.items || []).forEach(item => marcarItemRecursivo(item, true));
        });

        commitCondicionesDraft();
        refreshCondicionesBuilder();
    };

    window.limpiarTodoCondiciones = () => {
        window.CondicionesCotizacionState.draftSecciones.forEach(seccion => {
            seccion.seleccionada = false;
            (seccion.items || []).forEach(item => marcarItemRecursivo(item, false));
        });

        commitCondicionesDraft();
        refreshCondicionesBuilder();
    };

    window.aplicarCondicionesAlFormulario = () => {
        syncSeccionSeleccionState();

        window.CondicionesCotizacionState.secciones =
            deepClone(window.CondicionesCotizacionState.draftSecciones || []);

        window.CondicionesCotizacionState.configurado =
            hasSelectedItemsInTree(window.CondicionesCotizacionState.secciones);

        syncCondicionesInput();
        actualizarResumenCondicionesLocal();
        window.cerrarModalCondicionesCotizacion();
    };

    document.getElementById('cotizacion-form')?.addEventListener('submit', () => {
        commitCondicionesDraft();
    });

    document.addEventListener('keydown', function (event) {
        if (event.key === 'Escape') {
            window.cerrarModalCondicionesCotizacion();
        }
    });

    let currentSectionIndex = null;

    function renderSidebar() {
        const container = document.getElementById('condiciones-sidebar-list');
        if (!container) return;

        const secciones = window.CondicionesCotizacionState.draftSecciones || [];

        if (currentSectionIndex === null && secciones.length) {
            currentSectionIndex = 0;
        }

        container.innerHTML = '';

        secciones.forEach((sec, index) => {
            const selectedCount = countSelectedItems(sec.items || []);
            const totalCount = countAllRenderableItems(sec.items || []);
            const isActive = currentSectionIndex === index;
            const isSelected = selectedCount > 0;

            const div = document.createElement('div');
            div.className = `
                cursor-pointer px-4 py-3 rounded-xl border text-xs font-bold transition-all
                ${isActive ? 'bg-slate-900 border-slate-900 text-white shadow-lg' :
                    isSelected ? 'bg-emerald-50 border-emerald-300 text-emerald-700' :
                    'bg-white border-slate-200 text-slate-600 hover:border-blue-300'}
            `;

            div.innerHTML = `
                <div class="flex items-center justify-between gap-3">
                    <span class="truncate">${escapeHtml(sec.titulo || 'Sin título')}</span>
                    <span class="text-[10px] shrink-0">${selectedCount}/${totalCount}</span>
                </div>
            `;

            div.onclick = () => {
                currentSectionIndex = index;
                renderSidebar();
                renderEditor();
            };

            container.appendChild(div);
        });
    }
    
    function renderEditor() {
        const secciones = window.CondicionesCotizacionState.draftSecciones || [];
        const sec = secciones[currentSectionIndex];

        const title = document.getElementById('editor-title');
        const badge = document.getElementById('editor-badge');
        const body = document.getElementById('condiciones-editor-body');

        if (!title || !badge || !body) return;

        if (!sec) {
            title.innerText = 'Selecciona una sección';
            badge.innerText = '0 seleccionados';
            body.innerHTML = `<div class="text-xs text-slate-400 font-semibold">No hay contenido disponible</div>`;
            return;
        }

        const selectedCount = countSelectedItems(sec.items || []);
        const totalCount = countAllRenderableItems(sec.items || []);
        const allChecked = totalCount > 0 && selectedCount === totalCount;

        sec.seleccionada = selectedCount > 0;

        title.innerText = sec.titulo || 'Sin título';
        badge.innerText = `${selectedCount} de ${totalCount} seleccionados`;

        body.innerHTML = `
            <div class="mb-4 rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3 flex items-center justify-between gap-4">
                <label class="flex items-center gap-3 cursor-pointer">
                    <input type="checkbox"
                        ${allChecked ? 'checked' : ''}
                        onchange="toggleSeccionCondicion(${currentSectionIndex}, this.checked)"
                        class="w-5 h-5 rounded-md border-slate-300 text-emerald-600 focus:ring-emerald-500">
                    <span class="text-xs font-black text-slate-700 uppercase tracking-wider">
                        Seleccionar toda la sección
                    </span>
                </label>

                <span class="text-[10px] font-black text-slate-500 uppercase">
                    ${selectedCount}/${totalCount}
                </span>
            </div>

            ${(sec.items || []).map((item, idx) => {
                const path = `${currentSectionIndex}-${idx}`;
                const checked = item.seleccionado ? 'checked' : '';

                return `
                    <div class="p-4 rounded-xl border ${item.seleccionado ? 'border-emerald-300 bg-emerald-50/60' : 'border-slate-200 bg-white'}">
                        <label class="flex items-start gap-3 cursor-pointer">
                            <input type="checkbox"
                                ${checked}
                                onchange="toggleItemCondicion('${path}', this.checked)"
                                class="mt-1 w-4 h-4 rounded border-slate-300 text-emerald-600 focus:ring-emerald-500">

                            <textarea
                                class="w-full text-xs border-0 focus:ring-0 resize-none bg-transparent font-semibold text-slate-700"
                                rows="2"
                                oninput="editarTextoCondicion('${path}', this.value)"
                            >${escapeTextarea(item.texto_final || '')}</textarea>
                        </label>
                    </div>
                `;
            }).join('')}
        `;
    }

    window.renderTable();

    initializeCondicionesState().then(() => {
        currentSectionIndex = 0;
        refreshCondicionesBuilder();
    });
});