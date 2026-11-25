/*
 * Solicitud de ensayo en una sola pantalla (HU-LIMS-32).
 *
 * Antes eran tres pasos y una fila por muestra y ensayo (10 probetas × 3 ensayos
 * = 30 filas que llenar). Ahora hay una fila por ENSAYO de la cotización: se
 * elige a qué muestras se aplica (varias a la vez), el técnico y la entrega, y
 * al guardar se arma una línea por muestra con los mismos arreglos que recibe el
 * servidor (muestra_id[], servicio_id[], norma[], metodo[], tecnico_id[],
 * entrega_detalle[], incidencia_*[]).
 */
(function () {
    'use strict';

    var $ = function (id) { return document.getElementById(id); };
    var cfg = window.SolicitudEnsayoConfig || {};
    var form = $('solicitud-form');
    if (!form) return;

    var tecnicos = leerJSON('se-tecnicos');
    var previas = leerJSON('se-incidencias-previas');
    var muestras = [];            // [{id, codigo, descripcion, tipo, sigla}]
    var filas = [];               // ensayos por asignar: {id, nombre, norma, metodo, sel:[ids], tecnico, fecha}
    var incidencias = [];         // nuevas: {detalle, fecha, cliente, responsable, autorizada}
    var tsCotizacion = null;
    var cargando = false;
    var cargadaId = '';
    var pendienteBorrador = null;

    function leerJSON(id) { try { return JSON.parse($(id).textContent || '[]'); } catch (e) { return []; } }
    function el(tag, clase, texto) { var n = document.createElement(tag); if (clase) n.className = clase; if (texto != null) n.textContent = texto; return n; }
    function icono() { if (window.lucide) window.lucide.createIcons(); }
    function ahoraLocal() { var d = new Date(); d.setMinutes(d.getMinutes() - d.getTimezoneOffset()); return d.toISOString().slice(0, 16); }
    function muestraPorId(id) { return muestras.find(function (m) { return String(m.id) === String(id); }); }

    /* ---------- Pantalla de asignación (modal) ---------- */

    function abrirModal() {
        var m = $('se-modal');
        m.classList.remove('hidden'); m.classList.add('flex');
        document.body.classList.add('overflow-hidden');
        var sel = $('id_cotizacion');
        var opt = sel.options[sel.selectedIndex];
        $('se-modal-sub').textContent = (opt && opt.text ? opt.text.trim() : '') + (muestras.length ? ' · ' + muestras.length + ' muestra' + (muestras.length === 1 ? '' : 's') : '');
        icono();
    }
    function cerrarModal() {
        cerrarSelector();
        var m = $('se-modal');
        m.classList.add('hidden'); m.classList.remove('flex');
        document.body.classList.remove('overflow-hidden');
        resumen();
    }

    /* ---------- Estado y borrador ---------- */

    function estado() {
        return {
            cotizacion: $('id_cotizacion').value,
            fecha: $('fecha_solicitud').value, plazo: $('dias_plazo').value, entrega: $('fecha_entrega_programada').value,
            filas: filas.map(function (f) { return { id: f.id, sel: f.sel, tecnico: f.tecnico, fecha: f.fecha }; }),
            incidencias: incidencias,
        };
    }

    function cambio() {
        $('estado_borrador').value = JSON.stringify(estado());
        resumen();
        if (window.BorradorLocal && window.BorradorLocal.marcarCambio) window.BorradorLocal.marcarCambio();
    }

    function aplicarEstado(e) {
        if (!e) return;
        (e.filas || []).forEach(function (g) {
            var f = filas.find(function (x) { return String(x.id) === String(g.id); });
            if (!f) return;
            f.sel = (g.sel || []).filter(function (id) { return muestraPorId(id); });
            f.tecnico = g.tecnico || ''; f.fecha = g.fecha || '';
        });
        if (e.incidencias && e.incidencias.length) { incidencias = e.incidencias; }
        pintarFilas(); pintarIncidencias(); resumen();
    }

    function restaurarBorrador() {
        var e = null;
        try { e = JSON.parse($('se-estado-borrador').textContent || 'null'); } catch (x) { e = null; }
        if (!e) return;
        pendienteBorrador = e;
        if (e.cotizacion && String(e.cotizacion) !== cargadaId) {
            if (tsCotizacion) tsCotizacion.setValue(e.cotizacion, true);
            else $('id_cotizacion').value = e.cotizacion;
            cargarCotizacion(e.cotizacion);
        } else if (filas.length) {
            aplicarEstado(pendienteBorrador); pendienteBorrador = null;
        }
    }

    /* ---------- Carga de la cotización ---------- */

    function cargarCotizacion(id) {
        if (!id) return Promise.resolve();
        cargando = true;
        cargadaId = String(id);
        $('se-vacio-texto').textContent = 'Cargando ensayos…';
        $('se-vacio').classList.remove('hidden');
        var url = cfg.detalleUrl.replace(/0\/$/, id + '/');
        return fetch(url, { credentials: 'same-origin', headers: { 'X-Requested-With': 'XMLHttpRequest' } })
            .then(function (r) { if (!r.ok) throw new Error('HTTP ' + r.status); return r.json(); })
            .then(function (d) {
                muestras = (d.muestras || []).map(function (m) {
                    return { id: m.id, codigo: m.codigo_laboratorio, descripcion: m.descripcion || '', tipo: m.tipo_muestra__nombre || '', sigla: m.tipo_muestra__sigla || '',
                             idCliente: m.codigo_cliente || '', estructura: m.elemento_estructural || '' };
                });
                filas = (d.servicios_pendientes || []).map(function (s) {
                    return { id: s.cotizacion_detalle_id, nombre: s.nombre_servicio, norma: s.norma || '', metodo: s.metodo || '',
                             sel: muestras.length === 1 ? [muestras[0].id] : [], tecnico: '', fecha: '' };
                });
                pintarAsignados(d.detalles_asignados || []);
                cargando = false;
                $('se-vacio-texto').textContent = (d.detalles_asignados || []).length
                    ? 'Todos los ensayos de esta cotización ya están asignados.' : 'Esta cotización no tiene ensayos.';
                pintarFilas(); resumen();
                if (pendienteBorrador) { aplicarEstado(pendienteBorrador); pendienteBorrador = null; }
            })
            .catch(function () {
                cargando = false;
                $('se-vacio-texto').textContent = 'No se pudieron cargar los ensayos. Intenta de nuevo.';
            });
    }

    function pintarAsignados(lista) {
        var caja = $('se-asignados-caja'), tb = $('se-asignados');
        tb.textContent = '';
        caja.classList.toggle('hidden', !lista.length);
        $('se-asignados-titulo').textContent = 'Ya asignados (' + lista.length + ' línea' + (lista.length === 1 ? '' : 's') + ')';
        lista.forEach(function (d) {
            var tr = el('tr', '');
            [d.muestra_codigo, d.nombre_servicio, d.norma, d.tecnico_nombre, d.fecha_entrega].forEach(function (t, i) {
                tr.appendChild(el('td', 'px-4 py-2 ' + (i === 0 ? 'font-mono font-black text-blue-700' : 'text-slate-600'), t || '—'));
            });
            tb.appendChild(tr);
        });
    }

    /* ---------- Filas de ensayos ---------- */

    function opcionesTecnico(select, valor, vacio) {
        select.textContent = '';
        var o0 = el('option', '', vacio || '— Técnico —'); o0.value = ''; select.appendChild(o0);
        tecnicos.forEach(function (t) { var o = el('option', '', t.nombre); o.value = t.id; select.appendChild(o); });
        select.value = valor || '';
    }

    function completa(f) { return f.sel.length > 0 && f.tecnico && f.fecha; }
    function parcial(f) { return !completa(f) && (f.sel.length > 0 || f.tecnico || f.fecha); }

    function pintarFilas() {
        var cont = $('se-filas');
        cont.textContent = '';
        var hay = filas.length > 0;
        $('se-vacio').classList.toggle('hidden', hay || cargando);
        $('se-cabecera').classList.toggle('hidden', !hay);
        if (hay) $('se-cabecera').classList.add('xl:grid'); else $('se-cabecera').classList.remove('xl:grid');
        $('se-masivo').classList.toggle('hidden', !hay);
        $('se-masivo').classList.toggle('flex', hay);
        filas.forEach(function (f) { cont.appendChild(crearFila(f)); });
        icono();
    }

    function estadoFila(tr, f) {
        tr.classList.remove('se-fila-lista', 'se-fila-parcial', 'se-fila-vacia');
        tr.classList.add(completa(f) ? 'se-fila-lista' : parcial(f) ? 'se-fila-parcial' : 'se-fila-vacia');
    }

    function crearFila(f) {
        var tr = el('div', 'px-4 py-3 grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-[minmax(0,2.2fr)_minmax(0,1.4fr)_minmax(0,1.3fr)_150px] gap-x-4 gap-y-2 items-center');
        tr.dataset.id = f.id;
        estadoFila(tr, f);

        var c1 = el('div', 'min-w-0');
        c1.appendChild(el('p', 'text-sm font-black text-slate-800 leading-tight', f.nombre));
        var sub = [f.norma, f.metodo].filter(Boolean).join(' · ');
        c1.appendChild(el('p', 'text-[11px] font-mono text-blue-600 mt-0.5 break-words', sub || 'Sin norma'));
        tr.appendChild(c1);

        var c2 = el('div', 'relative');
        var btn = el('button', 'w-full flex items-center justify-between gap-2 px-3 py-2.5 rounded-xl border border-slate-200 bg-white hover:border-blue-400 text-left text-xs font-bold text-slate-700');
        btn.type = 'button';
        var txt = el('span', 'truncate', ''); btn.appendChild(txt);
        var fl = document.createElement('i'); fl.setAttribute('data-lucide', 'chevron-down'); fl.className = 'w-4 h-4 text-slate-400 shrink-0'; btn.appendChild(fl);
        c2.appendChild(btn);
        function textoMuestras() {
            if (!muestras.length) return 'Sin muestras';
            if (!f.sel.length) return 'Elegir muestras…';
            if (f.sel.length === muestras.length) return 'Todas (' + muestras.length + ')';
            if (f.sel.length === 1) { var m = muestraPorId(f.sel[0]); return m ? m.codigo : '1 muestra'; }
            return f.sel.length + ' de ' + muestras.length + ' muestras';
        }
        txt.textContent = textoMuestras();
        btn.addEventListener('click', function (ev) { ev.stopPropagation(); abrirSelector(c2, f, function () { txt.textContent = textoMuestras(); estadoFila(tr, f); cambio(); }); });
        tr.appendChild(c2);

        var sel = el('select', 'se-campo'); opcionesTecnico(sel, f.tecnico);
        sel.addEventListener('change', function () { f.tecnico = sel.value; estadoFila(tr, f); cambio(); });
        tr.appendChild(sel);

        var fe = el('input', 'se-campo'); fe.type = 'date'; fe.value = f.fecha;
        fe.addEventListener('change', function () { f.fecha = fe.value; estadoFila(tr, f); cambio(); });
        tr.appendChild(fe);

        tr._refrescar = function () { sel.value = f.tecnico; fe.value = f.fecha; txt.textContent = textoMuestras(); estadoFila(tr, f); };
        return tr;
    }

    /* Selector de muestras: panel con casillas, por tipo y con «Todas / Ninguna». */
    var panelAbierto = null;
    function cerrarSelector() { if (panelAbierto) { panelAbierto.remove(); panelAbierto = null; } }
    document.addEventListener('click', function (e) { if (panelAbierto && !panelAbierto.contains(e.target)) cerrarSelector(); });
    document.addEventListener('keydown', function (e) { if (e.key === 'Escape') cerrarSelector(); });

    function abrirSelector(ancla, f, alCambiar) {
        if (panelAbierto) { cerrarSelector(); return; }
        if (!muestras.length) return;
        var p = el('div', 'absolute z-40 left-0 mt-1 w-[min(420px,90vw)] bg-white border border-slate-200 rounded-xl shadow-2xl');
        panelAbierto = p;
        var cab = el('div', 'flex flex-wrap items-center gap-2 p-2 border-b border-slate-100');
        function bt(t, fn) { var b = el('button', 'px-2.5 py-1 rounded-lg border border-slate-200 text-[10px] font-black uppercase text-slate-600 hover:border-blue-400', t); b.type = 'button'; b.addEventListener('click', fn); return b; }
        cab.appendChild(bt('Todas', function () { f.sel = muestras.map(function (m) { return m.id; }); redibujar(); alCambiar(); }));
        cab.appendChild(bt('Ninguna', function () { f.sel = []; redibujar(); alCambiar(); }));
        var tipos = {};
        muestras.forEach(function (m) { tipos[m.tipo || 'Sin tipo'] = true; });
        Object.keys(tipos).forEach(function (t) {
            if (Object.keys(tipos).length < 2) return;
            cab.appendChild(bt('Solo ' + t, function () { f.sel = muestras.filter(function (m) { return (m.tipo || 'Sin tipo') === t; }).map(function (m) { return m.id; }); redibujar(); alCambiar(); }));
        });
        p.appendChild(cab);
        var lista = el('div', 'max-h-64 overflow-y-auto divide-y divide-slate-50');
        p.appendChild(lista);
        function redibujar() {
            lista.textContent = '';
            muestras.forEach(function (m) {
                var l = el('label', 'flex items-start gap-3 px-3 py-2 cursor-pointer hover:bg-blue-50/60');
                var c = document.createElement('input'); c.type = 'checkbox'; c.className = 'mt-0.5';
                c.checked = f.sel.some(function (id) { return String(id) === String(m.id); });
                c.addEventListener('change', function () {
                    f.sel = c.checked ? f.sel.concat([m.id]) : f.sel.filter(function (id) { return String(id) !== String(m.id); });
                    alCambiar();
                });
                l.appendChild(c);
                var b = el('span', 'min-w-0');
                b.appendChild(el('span', 'block font-mono text-[11px] font-black text-blue-700', m.codigo));
                b.appendChild(el('span', 'block text-[11px] text-slate-500 break-words', [m.tipo, m.idCliente && ('ID cliente ' + m.idCliente), m.estructura, m.descripcion].filter(Boolean).join(' · ')));
                l.appendChild(b);
                lista.appendChild(l);
            });
        }
        redibujar();
        ancla.appendChild(p);
    }

    /* ---------- Acciones masivas ---------- */

    function refrescarFilas() { Array.prototype.forEach.call($('se-filas').children, function (tr) { if (tr._refrescar) tr._refrescar(); }); }

    $('se-aplicar-todos').addEventListener('click', function () {
        var t = $('se-tec-todos').value, d = $('se-fecha-todos').value || $('fecha_entrega_programada').value;
        filas.forEach(function (f) { if (t) f.tecnico = t; if (d) f.fecha = d; });
        refrescarFilas(); cambio();
    });
    $('se-todas-muestras').addEventListener('click', function () {
        filas.forEach(function (f) { f.sel = muestras.map(function (m) { return m.id; }); });
        refrescarFilas(); cambio();
    });

    /* La fecha de cada ensayo arranca en la entrega programada si aún está vacía. */
    function fechaPorDefecto() {
        var d = $('fecha_entrega_programada').value;
        if (!d) return;
        var cambiado = false;
        filas.forEach(function (f) { if (!f.fecha) { f.fecha = d; cambiado = true; } });
        if (cambiado) { refrescarFilas(); }
    }

    /* ---------- Resumen y envío ---------- */

    function resumen() {
        var listas = filas.filter(completa), parciales = filas.filter(parcial);
        var lineas = listas.reduce(function (n, f) { return n + f.sel.length; }, 0);
        $('se-resumen').textContent = filas.length
            ? filas.length + ' ensayo' + (filas.length === 1 ? '' : 's') + ' por asignar · ' + listas.length + ' listo' + (listas.length === 1 ? '' : 's') +
              (muestras.length ? ' · ' + muestras.length + ' muestra' + (muestras.length === 1 ? '' : 's') + ' en la recepción' : '')
            : 'Elige una cotización para ver sus ensayos.';
        var partes = [];
        if (lineas) partes.push(lineas + ' línea' + (lineas === 1 ? '' : 's') + ' de ensayo por guardar');
        if (parciales.length) partes.push(parciales.length + ' ensayo' + (parciales.length === 1 ? '' : 's') + ' incompleto' + (parciales.length === 1 ? '' : 's'));
        var inc = incidencias.filter(function (i) { return (i.detalle || '').trim(); }).length;
        if (inc) partes.push(inc + ' incidencia' + (inc === 1 ? '' : 's'));
        var e = $('se-estado');
        e.textContent = partes.length ? partes.join(' · ') : 'Sin cambios';
        e.className = 'text-xs font-bold ' + (parciales.length ? 'text-amber-700' : lineas ? 'text-emerald-700' : 'text-slate-500');
        var c = $('se-inc-contador');
        c.textContent = incidencias.length; c.classList.toggle('hidden', !incidencias.length);
        pintarPagina(listas, parciales, lineas, inc);
    }

    function pintarPagina(listas, parciales, lineas, inc) {
        var cont = $('se-pagina-lista');
        cont.textContent = '';
        var visibles = filas.filter(function (f) { return completa(f) || parcial(f); });
        $('se-pagina-vacio').classList.toggle('hidden', visibles.length > 0);
        $('se-abrir').disabled = !filas.length && !muestras.length;
        $('se-pagina-resumen').textContent = !$('id_cotizacion').value ? 'Elige una cotización para asignar sus ensayos.'
            : (lineas ? lineas + ' línea' + (lineas === 1 ? '' : 's') + ' de ensayo por guardar' : 'Aún no asignaste ensayos') +
              (inc ? ' · ' + inc + ' incidencia' + (inc === 1 ? '' : 's') : '');
        visibles.forEach(function (f) {
            var ok = completa(f);
            var fila = el('div', 'px-4 py-3 flex flex-wrap items-center gap-x-6 gap-y-1 ' + (ok ? 'se-fila-lista' : 'se-fila-parcial'));
            fila.appendChild(el('span', 'text-sm font-black text-slate-800 min-w-[220px] flex-1', f.nombre));
            var t = tecnicos.find(function (x) { return String(x.id) === String(f.tecnico); });
            [f.sel.length + ' muestra' + (f.sel.length === 1 ? '' : 's'), t ? t.nombre : 'Sin técnico', f.fecha || 'Sin fecha'].forEach(function (x, i) {
                fila.appendChild(el('span', 'text-xs font-semibold ' + (i === 1 && !t || i === 2 && !f.fecha || i === 0 && !f.sel.length ? 'text-amber-700' : 'text-slate-600'), x));
            });
            cont.appendChild(fila);
        });
    }

    function oculto(n, v) { var i = document.createElement('input'); i.type = 'hidden'; i.name = n; i.value = v == null ? '' : v; return i; }

    form.addEventListener('submit', function (ev) {
        var envio = $('se-envio');
        envio.textContent = '';
        if (!$('id_cotizacion').value) { ev.preventDefault(); cerrarModal(); $('se-estado').textContent = 'Elige una cotización.'; $('se-estado').className = 'text-xs font-bold text-rose-700'; return; }
        if (!$('fecha_entrega_programada').value) { ev.preventDefault(); cerrarModal(); $('fecha_entrega_programada').focus(); $('se-estado').textContent = 'Indica la entrega programada (o el plazo en días).'; $('se-estado').className = 'text-xs font-bold text-rose-700'; return; }
        var incompletos = filas.filter(parcial);
        if (incompletos.length) {
            ev.preventDefault();
            abrirModal();
            $('se-estado').textContent = 'Completa o vacía: ' + incompletos.map(function (f) { return f.nombre; }).join(' · ');
            $('se-estado').className = 'text-xs font-bold text-rose-700';
            var tr = $('se-filas').querySelector('[data-id="' + incompletos[0].id + '"]');
            if (tr && tr.scrollIntoView) tr.scrollIntoView({ block: 'center', behavior: 'smooth' });
            return;
        }
        filas.filter(completa).forEach(function (f) {
            f.sel.forEach(function (mid) {
                envio.appendChild(oculto('muestra_id[]', mid));
                envio.appendChild(oculto('servicio_id[]', f.id));
                envio.appendChild(oculto('norma[]', f.norma));
                envio.appendChild(oculto('metodo[]', f.metodo));
                envio.appendChild(oculto('tecnico_id[]', f.tecnico));
                envio.appendChild(oculto('entrega_detalle[]', f.fecha));
            });
        });
        incidencias.forEach(function (i) {
            if (!(i.detalle || '').trim()) return;
            envio.appendChild(oculto('incidencia_detalle[]', i.detalle));
            envio.appendChild(oculto('incidencia_fecha[]', i.fecha));
            envio.appendChild(oculto('incidencia_cliente[]', i.cliente));
            envio.appendChild(oculto('incidencia_responsable_id[]', i.responsable));
            envio.appendChild(oculto('incidencia_autorizado[]', i.autorizada ? 'true' : 'false'));
        });
        $('se-guardar').disabled = true;
    });

    /* ---------- Incidencias ---------- */

    function pintarPrevias() {
        var c = $('se-inc-previas'); c.textContent = '';
        previas.forEach(function (i) {
            var d = el('div', 'rounded-xl border border-slate-200 bg-slate-50 px-3 py-2 text-xs');
            d.appendChild(el('p', 'font-bold text-slate-700 whitespace-pre-line', i.detalle));
            d.appendChild(el('p', 'text-[11px] text-slate-500 mt-0.5', [i.fecha, i.cliente && ('Cliente: ' + i.cliente), i.responsable && ('Lab: ' + i.responsable), i.autorizada ? 'Autorizada' : 'Sin autorizar'].filter(Boolean).join(' · ')));
            c.appendChild(d);
        });
        vacioIncidencias();
    }

    function vacioIncidencias() {
        $('se-inc-vacio').classList.toggle('hidden', previas.length > 0 || incidencias.length > 0);
    }

    function campoInc(etiqueta, nodo) {
        var w = el('div', ''); w.appendChild(el('span', 'se-label', etiqueta)); w.appendChild(nodo); return w;
    }

    function pintarIncidencias() {
        var c = $('se-inc-lista'); c.textContent = '';
        incidencias.forEach(function (inc, idx) {
            var caja = el('div', 'rounded-xl border border-slate-200 p-3 space-y-2');
            var ta = el('textarea', 'se-campo'); ta.rows = 3; ta.placeholder = 'Detalle de la incidencia…'; ta.value = inc.detalle || '';
            ta.addEventListener('input', function () { inc.detalle = ta.value; cambio(); });
            var fe = el('input', 'se-campo'); fe.type = 'datetime-local'; fe.value = inc.fecha || ahoraLocal();
            inc.fecha = fe.value;
            fe.addEventListener('change', function () { inc.fecha = fe.value; cambio(); });
            var cl = el('input', 'se-campo'); cl.placeholder = 'Representante del cliente'; cl.value = inc.cliente || '';
            cl.addEventListener('input', function () { inc.cliente = cl.value; cambio(); });
            var rs = el('select', 'se-campo'); opcionesTecnico(rs, inc.responsable, '— Responsable lab (JL/SL) —');
            rs.addEventListener('change', function () { inc.responsable = rs.value; cambio(); });
            var pie = el('div', 'flex items-center justify-between');
            var au = el('label', 'flex items-center gap-2 text-[11px] font-black uppercase text-slate-600');
            var ck = document.createElement('input'); ck.type = 'checkbox'; ck.checked = !!inc.autorizada;
            ck.addEventListener('change', function () { inc.autorizada = ck.checked; cambio(); });
            au.appendChild(ck); au.appendChild(document.createTextNode('Autorizar'));
            var q = el('button', 'p-1.5 text-slate-400 hover:text-rose-600'); q.type = 'button'; q.setAttribute('aria-label', 'Quitar incidencia');
            var ic = document.createElement('i'); ic.setAttribute('data-lucide', 'trash-2'); ic.className = 'w-4 h-4'; q.appendChild(ic);
            q.addEventListener('click', function () { incidencias.splice(idx, 1); pintarIncidencias(); cambio(); });
            pie.appendChild(au); pie.appendChild(q);
            [ta, campoInc('Fecha y hora', fe), campoInc('Cliente', cl), campoInc('Responsable', rs), pie].forEach(function (n) { caja.appendChild(n); });
            c.appendChild(caja);
        });
        vacioIncidencias();
        icono();
    }

    $('se-inc-agregar').addEventListener('click', function () {
        incidencias.push({ detalle: '', fecha: ahoraLocal(), cliente: '', responsable: '', autorizada: false });
        pintarIncidencias(); cambio();
        var t = $('se-inc-lista').querySelector('textarea:last-of-type'); if (t) t.focus();
    });

    /* ---------- Cabecera: plazo → entrega, cotización ---------- */

    function calcularEntrega() {
        var base = $('fecha_solicitud').value, dias = parseInt($('dias_plazo').value, 10);
        if (base && !isNaN(dias)) {
            var d = new Date(base + 'T00:00:00'); d.setDate(d.getDate() + dias);
            $('fecha_entrega_programada').value = d.getFullYear() + '-' + String(d.getMonth() + 1).padStart(2, '0') + '-' + String(d.getDate()).padStart(2, '0');
            fechaPorDefecto(); cambio();
        }
    }
    $('fecha_solicitud').addEventListener('change', calcularEntrega);
    $('dias_plazo').addEventListener('input', calcularEntrega);
    $('fecha_entrega_programada').addEventListener('change', function () { fechaPorDefecto(); cambio(); });

    function iniciar() {
        $('se-abrir').addEventListener('click', abrirModal);
        $('se-cerrar').addEventListener('click', cerrarModal);
        $('se-listo').addEventListener('click', cerrarModal);
        opcionesTecnico($('se-tec-todos'), '', '— Elegir técnico —');
        pintarPrevias();
        var sel = $('id_cotizacion');
        var sinOpciones = sel.options.length === 1 && !sel.options[0].value;
        function alElegir(v) {
            if (!v) return;
            var hayTrabajo = filas.some(function (f) { return f.sel.length || f.tecnico; });
            if (hayTrabajo && !window.confirm('Cambiar de cotización descarta lo que ya asignaste en esta pantalla. ¿Continuar?')) {
                if (tsCotizacion) tsCotizacion.setValue(sel.dataset.anterior || '', true);
                return;
            }
            sel.dataset.anterior = v;
            cargarCotizacion(v).then(function () { fechaPorDefecto(); abrirModal(); });
        }
        if (sinOpciones) { sel.disabled = true; }
        else if (window.TomSelect) {
            tsCotizacion = new TomSelect(sel, {
                create: false, allowEmptyOption: false, maxOptions: 500, searchField: ['text'],
                placeholder: 'Buscar cotización, oferta o cliente…',
                onChange: alElegir,
            });
        } else { sel.addEventListener('change', function () { alElegir(sel.value); }); }
        if (sel.value && !sinOpciones) { sel.dataset.anterior = sel.value; cargarCotizacion(sel.value).then(function () { fechaPorDefecto(); cambio(); abrirModal(); }); }
        icono();
    }

    window.SolicitudEnsayo = { restaurarBorrador: restaurarBorrador };
    document.addEventListener('DOMContentLoaded', iniciar);
})();
