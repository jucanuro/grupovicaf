/*
 * Registro de muestras de la recepción (HU-LIMS-31).
 *
 * Un modal a pantalla completa (como el detalle de la cotización): a la
 * izquierda el formulario, a la derecha lo ya agregado. Se agrega con Enter y
 * el tipo, la unidad y la cantidad quedan listos para la siguiente muestra.
 *
 * La tabla de la página es la fuente de verdad: cada muestra nueva es una fila
 * `tr[data-nueva]` con campos ocultos (los mismos nombres que recibe el
 * servidor: tipo_muestra_id[], cantidad[], unidad_medida_id[], masa[],
 * descripcion[], observaciones[]). Así el borrador local (HTML de la tabla)
 * sigue funcionando. Las muestras ya guardadas (`tr[data-existente]`) son solo
 * de lectura y no se reenvían.
 */
(function () {
    'use strict';

    var $ = function (id) { return document.getElementById(id); };
    var leer = function (id) { try { return JSON.parse($(id).textContent || '[]'); } catch (e) { return []; } };

    var tipos = leer('data-tipos');
    var unidades = leer('data-unidades');
    var existentes = leer('muestras-existentes');
    var tbody = $('tbody-muestras');
    var modal = $('modalMuestras');
    if (!tbody || !modal) return;

    var enEdicion = null;      // <tr> que se está corrigiendo
    var filtroTipo = '';

    function el(tag, clase, texto) {
        var n = document.createElement(tag);
        if (clase) n.className = clase;
        if (texto != null) n.textContent = texto;
        return n;
    }
    function tipoPorId(id) { return tipos.find(function (t) { return String(t.id) === String(id); }); }
    function unidadPorId(id) { return unidades.find(function (u) { return String(u.id) === String(id); }); }
    function unidadPorDefecto() {
        var u = unidades.find(function (x) { return (x.codigo || '').toUpperCase() === 'UND'; }) || unidades[0];
        return u ? u.id : '';
    }
    function icono() { if (window.lucide) window.lucide.createIcons(); }

    /* ---------- Tabla de la página ---------- */

    function celda(clase, texto) { return el('td', 'px-3 py-3 align-top text-xs ' + (clase || ''), texto); }

    function oculto(nombre, valor) {
        var i = document.createElement('input');
        i.type = 'hidden'; i.name = nombre; i.value = valor == null ? '' : valor;
        return i;
    }

    function boton(titulo, nombreIcono, clase, alClick) {
        var b = el('button', 'p-1.5 rounded-lg transition-colors ' + clase);
        b.type = 'button'; b.title = titulo; b.setAttribute('aria-label', titulo);
        var ic = document.createElement('i'); ic.setAttribute('data-lucide', nombreIcono); ic.className = 'w-4 h-4';
        b.appendChild(ic);
        b.addEventListener('click', alClick);
        return b;
    }

    function datosDe(tr) {
        var g = function (n) { var i = tr.querySelector('input[name="' + n + '"]'); return i ? i.value : ''; };
        return {
            tipo: g('tipo_muestra_id[]'), cantidad: g('cantidad[]'), unidad: g('unidad_medida_id[]'),
            masa: g('masa[]'), descripcion: g('descripcion[]'), observaciones: g('observaciones[]'),
        };
    }

    function textoCantidad(d) {
        var u = unidadPorId(d.unidad);
        return d.cantidad + (u ? ' ' + u.codigo : '');
    }

    function llenarFila(tr, d, existente, idLab) {
        tr.textContent = '';
        var t = tipoPorId(d.tipo);
        tr.appendChild(celda('text-center font-mono text-slate-400 nro', ''));
        var tdId = el('td', 'px-3 py-3 align-top whitespace-nowrap');
        if (existente) {
            tdId.appendChild(el('span', 'font-mono text-[11px] font-black text-blue-700', idLab || ''));
        } else {
            var chip = el('span', 'idlab font-mono text-[11px] font-black text-blue-700 bg-blue-50 border border-blue-100 rounded px-2 py-0.5', '');
            chip.title = 'Se confirma al guardar la recepción';
            tdId.appendChild(chip);
        }
        tr.appendChild(tdId);
        var tdTipo = el('td', 'px-3 py-3 align-top');
        tdTipo.appendChild(el('span', 'text-xs font-black text-slate-800 uppercase', d.tipoNombre || (t ? t.nombre : 'Tipo no encontrado')));
        if (t) tdTipo.appendChild(el('span', 'ml-2 text-[10px] font-mono text-slate-400', t.prefijo));
        tr.appendChild(tdTipo);
        tr.appendChild(celda('text-center font-bold text-slate-700 whitespace-nowrap', textoCantidad(d)));
        tr.appendChild(celda('text-right font-mono text-slate-600 whitespace-nowrap', d.masa === '' || d.masa == null ? '—' : d.masa));
        tr.appendChild(celda('text-slate-700 min-w-[180px] break-words', d.descripcion || '—'));
        tr.appendChild(celda('text-slate-500 min-w-[160px] break-words', d.observaciones || '—'));
        var acc = el('td', 'px-3 py-3 align-top text-center whitespace-nowrap');
        if (existente) {
            acc.appendChild(el('span', 'text-[10px] font-black text-emerald-700 bg-emerald-50 rounded px-2 py-0.5', 'Registrada'));
        } else {
            acc.appendChild(boton('Editar', 'pencil', 'text-slate-400 hover:text-blue-600 hover:bg-blue-50', function () { abrir(tr); }));
            acc.appendChild(boton('Duplicar', 'copy', 'text-slate-400 hover:text-blue-600 hover:bg-blue-50', function () { duplicar(tr); }));
            acc.appendChild(boton('Quitar', 'trash-2', 'text-slate-400 hover:text-rose-600 hover:bg-rose-50', function () { quitar(tr); }));
            [['tipo_muestra_id[]', d.tipo], ['cantidad[]', d.cantidad], ['unidad_medida_id[]', d.unidad],
             ['masa[]', d.masa], ['descripcion[]', d.descripcion], ['observaciones[]', d.observaciones]]
                .forEach(function (p) { acc.appendChild(oculto(p[0], p[1])); });
        }
        tr.appendChild(acc);
    }

    function agregarExistente(m) {
        var tr = el('tr', 'bg-slate-50/50');
        tr.dataset.existente = '1';
        llenarFila(tr, {
            tipo: m.tipo_muestra_id, tipoNombre: m.tipo_muestra_nombre, cantidad: m.cantidad,
            unidad: m.unidad_medida_id, masa: m.masa, descripcion: m.descripcion, observaciones: m.observaciones,
        }, true, m.codigo_laboratorio);
        tbody.appendChild(tr);
    }

    function agregarNueva(d) {
        var tr = el('tr', 'hover:bg-blue-50/40 transition-colors');
        tr.dataset.nueva = '1';
        llenarFila(tr, d, false);
        tbody.appendChild(tr);
        return tr;
    }

    function refrescar() {
        var filas = Array.prototype.slice.call(tbody.children);
        filas.forEach(function (tr, i) {
            var n = tr.querySelector('.nro');
            if (n) n.textContent = String(i + 1).padStart(2, '0');
        });
        asignarCodigos();
        var nuevas = tbody.querySelectorAll('tr[data-nueva]').length;
        var guardadas = tbody.querySelectorAll('tr[data-existente]').length;
        var partes = [];
        if (guardadas) partes.push(guardadas + ' ya registrada' + (guardadas === 1 ? '' : 's'));
        partes.push(nuevas + ' nueva' + (nuevas === 1 ? '' : 's') + ' por guardar');
        $('rm-resumen').textContent = filas.length ? partes.join(' · ') : 'Aún no hay muestras';
        $('rm-vacio').classList.toggle('hidden', filas.length > 0);
        $('tabla-muestras').classList.toggle('hidden', filas.length === 0);
        $('rm-contador').textContent = nuevas + ' en la lista';
        renderLista();
        icono();
    }

    /* ID de laboratorio: V-M-año-SIGLA-NNNN, igual que lo asigna el servidor al guardar. */
    function codigoDe(t, n) { return t.codigo_prefijo + String(n).padStart(4, '0'); }
    function asignarCodigos() {
        var usados = {};
        tbody.querySelectorAll('tr[data-nueva]').forEach(function (tr) {
            var t = tipoPorId(datosDe(tr).tipo);
            var chip = tr.querySelector('.idlab');
            if (!t || !chip) return;
            var n = (usados[t.id] = (usados[t.id] == null ? (t.siguiente || 1) : usados[t.id] + 1));
            chip.textContent = codigoDe(t, n);
        });
    }

    function quitar(tr) {
        tr.remove();
        if (enEdicion === tr) cancelarEdicion();
        refrescar();
    }

    function duplicar(tr) {
        var copia = agregarNueva(datosDe(tr));
        tr.after(copia);
        refrescar();
    }

    /* ---------- Modal ---------- */

    /* Combobox de tipos: plegado, con búsqueda al escribir y teclado (↑ ↓ Enter Esc). */
    var abierto = false;
    var resaltado = -1;

    function etiquetaTipo(t) { return t.nombre + ' (' + t.prefijo + ')'; }

    function listaFiltrada() {
        var q = filtroTipo.toLowerCase();
        return tipos.filter(function (t) { return !q || t.nombre.toLowerCase().indexOf(q) >= 0 || t.prefijo.toLowerCase().indexOf(q) >= 0; });
    }

    function renderTipos() {
        var cont = $('rm-tipos');
        var entrada = $('rm-tipo-buscar');
        cont.textContent = '';
        var lista = listaFiltrada();
        var actual = String($('rm-tipo-id').value);
        lista.forEach(function (t, i) {
            var activo = actual === String(t.id);
            var b = el('div', 'rm-tipo flex items-center justify-between gap-3 px-3 py-2 cursor-pointer text-xs ' +
                (i === resaltado ? 'bg-blue-100 ' : '') + (activo ? 'font-black text-blue-700' : 'text-slate-700 hover:bg-blue-50'));
            b.setAttribute('role', 'option'); b.setAttribute('aria-selected', activo ? 'true' : 'false');
            b.dataset.tipo = t.id;
            b.appendChild(el('span', 'font-bold uppercase truncate', t.nombre));
            b.appendChild(el('span', 'font-mono text-[10px] text-slate-400', t.prefijo));
            b.addEventListener('mousedown', function (e) { e.preventDefault(); elegirTipo(t.id); });
            cont.appendChild(b);
        });
        if (!lista.length) cont.appendChild(el('p', 'px-3 py-3 text-xs text-slate-400', 'Ningún tipo coincide. Crea uno con «Nuevo tipo».'));
        cont.classList.toggle('hidden', !abierto);
        entrada.setAttribute('aria-expanded', abierto ? 'true' : 'false');
        var hl = cont.children[resaltado] || cont.querySelector('[aria-selected="true"]');
        if (abierto && hl && hl.scrollIntoView) hl.scrollIntoView({ block: 'nearest' });
    }

    function mostrarElegido() {
        var t = tipoPorId($('rm-tipo-id').value);
        $('rm-tipo-buscar').value = t ? etiquetaTipo(t) : '';
    }

    function abrirCombo() { abierto = true; resaltado = -1; renderTipos(); }
    function cerrarCombo() { abierto = false; filtroTipo = ''; mostrarElegido(); renderTipos(); }

    function elegirTipo(id) {
        $('rm-tipo-id').value = id;
        abierto = false; filtroTipo = '';
        mostrarElegido();
        renderTipos();
        refrescar();
        $('rm-cantidad').focus();
        $('rm-cantidad').select();
    }

    function llenarUnidades() {
        var s = $('rm-unidad');
        s.textContent = '';
        unidades.forEach(function (u) {
            var o = el('option', '', u.codigo); o.value = u.id; s.appendChild(o);
        });
        s.value = unidadPorDefecto();
    }

    function error(texto) {
        var e = $('rm-error');
        e.textContent = texto || '';
        e.classList.toggle('hidden', !texto);
    }

    function renderLista() {
        var cont = $('rm-lista');
        cont.textContent = '';
        var nuevas = Array.prototype.slice.call(tbody.querySelectorAll('tr[data-nueva]'));
        if (!nuevas.length) {
            cont.appendChild(el('p', 'p-6 text-center text-xs font-semibold text-slate-400',
                'Lo que agregues aparece aquí. Cierra con «Listo» cuando termines.'));
            return;
        }
        nuevas.forEach(function (tr, i) {
            var d = datosDe(tr);
            var t = tipoPorId(d.tipo);
            var fila = el('div', 'flex items-start gap-3 px-4 py-3 hover:bg-slate-50' + (tr === enEdicion ? ' bg-amber-50' : ''));
            fila.appendChild(el('span', 'text-[10px] font-mono text-slate-400 w-6 pt-0.5', String(i + 1).padStart(2, '0')));
            var cuerpo = el('div', 'flex-1 min-w-0');
            var chipTr = tr.querySelector('.idlab');
            var cab = el('div', 'flex items-center gap-2 flex-wrap');
            if (chipTr) cab.appendChild(el('span', 'font-mono text-[11px] font-black text-blue-700 bg-blue-50 border border-blue-100 rounded px-2 py-0.5', chipTr.textContent));
            cab.appendChild(el('span', 'text-xs font-black text-slate-800 uppercase', (t ? t.nombre : '') + ' · ' + textoCantidad(d)));
            cuerpo.appendChild(cab);
            var detalle = [d.masa ? d.masa + ' kg' : '', d.descripcion, d.observaciones].filter(Boolean).join(' · ');
            if (detalle) cuerpo.appendChild(el('div', 'text-[11px] font-semibold text-slate-500 break-words', detalle));
            fila.appendChild(cuerpo);
            fila.appendChild(boton('Editar', 'pencil', 'text-slate-400 hover:text-blue-600', function () { cargarEnFormulario(tr); }));
            fila.appendChild(boton('Duplicar', 'copy', 'text-slate-400 hover:text-blue-600', function () { duplicar(tr); }));
            fila.appendChild(boton('Quitar', 'trash-2', 'text-slate-400 hover:text-rose-600', function () { quitar(tr); }));
            cont.appendChild(fila);
        });
        cont.scrollTop = cont.scrollHeight;
    }

    function cargarEnFormulario(tr) {
        var d = datosDe(tr);
        enEdicion = tr;
        $('rm-tipo-id').value = d.tipo;
        $('rm-cantidad').value = d.cantidad;
        $('rm-unidad').value = d.unidad || unidadPorDefecto();
        $('rm-masa').value = d.masa;
        $('rm-descripcion').value = d.descripcion;
        $('rm-observaciones').value = d.observaciones;
        $('rm-agregar-texto').textContent = 'Guardar cambios';
        $('rm-cancelar-edicion').classList.remove('hidden');
        error('');
        mostrarElegido(); renderTipos(); renderLista(); icono();
        $('rm-descripcion').focus();
    }

    function cancelarEdicion() {
        enEdicion = null;
        $('rm-agregar-texto').textContent = 'Agregar a la lista';
        $('rm-cancelar-edicion').classList.add('hidden');
        limpiarCamposVariables();
        renderLista(); icono();
    }

    function limpiarCamposVariables() {
        $('rm-masa').value = '';
        $('rm-descripcion').value = '';
        $('rm-observaciones').value = '';
    }

    function abrir(trParaEditar) {
        modal.classList.remove('hidden');
        modal.classList.add('flex');
        document.body.classList.add('overflow-hidden');
        mostrarElegido(); renderTipos(); renderLista(); icono();
        if (trParaEditar) { cargarEnFormulario(trParaEditar); return; }
        if (!$('rm-tipo-id').value && tipos.length === 1) { $('rm-tipo-id').value = tipos[0].id; mostrarElegido(); }
        setTimeout(function () { ($('rm-tipo-id').value ? $('rm-descripcion') : $('rm-tipo-buscar')).focus(); }, 60);
    }

    function cerrar() {
        if (enEdicion) cancelarEdicion();
        modal.classList.add('hidden');
        modal.classList.remove('flex');
        document.body.classList.remove('overflow-hidden');
        refrescar();
        if (window.BorradorLocal && window.BorradorLocal.marcarCambio) window.BorradorLocal.marcarCambio();
    }

    function agregar() {
        var tipo = $('rm-tipo-id').value;
        var cantidad = parseInt($('rm-cantidad').value, 10);
        var masa = $('rm-masa').value.trim();
        if (!tipo) { error('Elige el tipo de muestra.'); return; }
        if (!cantidad || cantidad < 1) { error('La cantidad debe ser 1 o más.'); $('rm-cantidad').focus(); return; }
        if (masa !== '' && (isNaN(Number(masa)) || Number(masa) < 0)) { error('La masa debe ser un número positivo.'); $('rm-masa').focus(); return; }
        error('');
        var d = {
            tipo: tipo, cantidad: String(cantidad), unidad: $('rm-unidad').value, masa: masa,
            descripcion: $('rm-descripcion').value.trim(), observaciones: $('rm-observaciones').value.trim(),
        };
        if (enEdicion) {
            llenarFila(enEdicion, d, false);
            cancelarEdicion();
        } else {
            agregarNueva(d);
            limpiarCamposVariables();
        }
        refrescar();
        if (window.BorradorLocal && window.BorradorLocal.marcarCambio) window.BorradorLocal.marcarCambio();
        $('rm-descripcion').focus();
    }

    /* El tipo nuevo se suma a la lista sin recargar la página. */
    function agregarTipo(data) {
        if (!tipoPorId(data.id)) {
            tipos.push({ id: data.id, nombre: data.nombre, prefijo: data.sigla,
                         codigo_prefijo: 'V-M-' + new Date().getFullYear() + '-' + String(data.sigla).toUpperCase() + '-',
                         siguiente: data.siguiente || 1 });
            tipos.sort(function (a, b) { return a.nombre.localeCompare(b.nombre); });
        }
        filtroTipo = '';
        elegirTipo(data.id);
    }

    var buscar = $('rm-tipo-buscar');
    buscar.addEventListener('focus', function () { buscar.select(); abrirCombo(); });
    buscar.addEventListener('click', function () { if (!abierto) abrirCombo(); });
    buscar.addEventListener('input', function () { filtroTipo = buscar.value.trim(); abierto = true; resaltado = 0; renderTipos(); });
    buscar.addEventListener('blur', function () { cerrarCombo(); });
    $('rm-combo-flecha').addEventListener('mousedown', function (e) {
        e.preventDefault();
        if (abierto) { cerrarCombo(); } else { buscar.focus(); abrirCombo(); }
    });
    buscar.addEventListener('keydown', function (e) {
        var n = listaFiltrada().length;
        if (e.key === 'ArrowDown') { e.preventDefault(); if (!abierto) { abrirCombo(); } resaltado = Math.min(resaltado + 1, n - 1); renderTipos(); }
        else if (e.key === 'ArrowUp') { e.preventDefault(); resaltado = Math.max(resaltado - 1, 0); renderTipos(); }
        else if (e.key === 'Enter') {
            e.preventDefault(); e.stopPropagation();
            var cont = $('rm-tipos');
            var op = abierto ? (cont.children[resaltado >= 0 ? resaltado : 0]) : null;
            if (op && op.dataset.tipo) elegirTipo(op.dataset.tipo);
            else if (!abierto) $('rm-cantidad').focus();
        }
        else if (e.key === 'Escape' && abierto) { e.preventDefault(); e.stopPropagation(); cerrarCombo(); }
    });
    $('btn-abrir-muestras').addEventListener('click', function () { abrir(); });
    $('btn-listo-muestras').addEventListener('click', cerrar);
    $('rm-agregar').addEventListener('click', agregar);
    $('rm-cancelar-edicion').addEventListener('click', cancelarEdicion);
    modal.addEventListener('keydown', function (e) {
        if (e.key === 'Enter' && e.target.tagName === 'INPUT' && e.target.type !== 'hidden') { e.preventDefault(); agregar(); }
        if (e.key === 'Escape' && !document.getElementById('tipoMuestraModal').classList.contains('flex')) { cerrar(); }
    });

    /* Tras restaurar un borrador el HTML vuelve sin sus botones: se redibujan las filas nuevas. */
    function reconstruir() {
        tbody.querySelectorAll('tr[data-nueva]').forEach(function (tr) { llenarFila(tr, datosDe(tr), false); });
        refrescar();
    }

    window.RecepcionMuestras = { agregarTipo: agregarTipo, abrir: abrir, refrescar: refrescar, reconstruir: reconstruir };

    document.addEventListener('DOMContentLoaded', function () {
        llenarUnidades();
        existentes.forEach(agregarExistente);
        // Filas que dejó el borrador local: se vuelven a dibujar con los datos guardados.
        refrescar();
    });
})();
