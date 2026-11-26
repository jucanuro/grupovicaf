/* Hoja de resumen tipo FOR-009 del registro de ensayo (HU-LIMS-41).
   Se dibuja desde los campos de la página y de los datos fijos (#hoja-estatica);
   sirve tanto al registro editable como al ensayo terminado (solo lectura). */
(function () {
    'use strict';
    const raiz = document.querySelector('[data-registro-compresion]');
    if (!raiz) return;
    const esCompresion = raiz.dataset.esCompresion === '1';
    const resumenCuerpo = document.querySelector('[data-resumen-cuerpo]');
    const codigoClienteOficial = raiz.dataset.codigoCliente || '';
    function valorDe(nombre) {
        const e = document.querySelector('[name="' + nombre + '"]');
        if (!e) return '';
        if (e.tagName === 'SELECT') return e.value ? e.selectedOptions[0].text.trim() : '';
        return e.value.trim();
    }
    function fechaLegible(iso) {
        const m = /^(\d{4})-(\d{2})-(\d{2})/.exec(iso || '');
        return m ? m[3] + '/' + m[2] + '/' + m[1] : (iso || '');
    }
    const HOJA = (function () {
        try { return JSON.parse(document.getElementById('hoja-estatica').textContent) || {}; } catch (e) { return {}; }
    })();
    // Marcas del revisor (HU-LIMS-45): {clave: comentario}. El revisor las edita; el técnico las ve en rojo.
    const revision = raiz.dataset.modoRevision === '1';
    const marcas = (function () {
        try { return JSON.parse(document.getElementById('marcas-revision').textContent) || {}; } catch (e) { return {}; }
    })();
    const CLAVES = {
        'ID del cliente (muestra)': 'muestra-codigo_cliente', 'Elemento estructural': 'muestra-elemento_estructural',
        "f'c de diseño": 'muestra-fc_diseno', 'Fecha de fabricación': 'muestra-fecha_fabricacion',
        'Fecha de ensayo': 'fecha_ensayo', 'Edad (días)': 'muestra-edad_ensayo_dias',
        'Perpendicularidad': 'verif_perpendicularidad', 'Planitud': 'verif_planitud', 'Tipo de fractura': 'tipo_fractura',
    };
    let temporizador = null;
    function elemento(tag, clase, texto) {
        const e = document.createElement(tag);
        if (clase) e.className = clase;
        if (texto != null) e.textContent = texto;
        return e;
    }
    function marcadosEtiqueta(nombre) {
        return Array.from(document.querySelectorAll('[name="' + nombre + '"]:checked')).map(function (c) {
            return c.closest('label') ? c.closest('label').textContent.trim() : c.value;
        });
    }
    function textoR(k) {
        const e = document.querySelector('[data-r="' + k + '"]');
        const t = e ? e.textContent.trim() : '';
        return t === '—' ? '' : t;
    }
    // Lo que se ve de la hoja: [etiqueta, valor] por fila, en el orden del formato en papel.
    function filasHoja() {
        const fcUnidad = valorDe('muestra-fc_unidad');
        const fc = valorDe('muestra-fc_diseno');
        const filas = [
            ['Testigo / muestra N.º', HOJA.testigo != null ? String(HOJA.testigo) : ''],
            ['ID del laboratorio', raiz.dataset.codigoLab || ''],
            ['ID del cliente (muestra)', valorDe('muestra-codigo_cliente')],
            ['Elemento estructural', valorDe('muestra-elemento_estructural')],
            ["f'c de diseño", fc ? fc + ' ' + (fcUnidad || 'kg/cm²') : ''],
            ['Fecha de fabricación', fechaLegible(valorDe('muestra-fecha_fabricacion'))],
            ['Fecha de recepción', HOJA.recepcion || ''],
            ['Fecha de ensayo', fechaLegible(valorDe('fecha_ensayo'))],
            ['Edad (días)', valorDe('muestra-edad_ensayo_dias')],
        ];
        const vd = document.querySelector('[data-verif-diametro]');
        const vdTxt = vd && vd.textContent.trim() !== '—' ? vd.textContent.trim() : '';
        const perp = marcadosEtiqueta('verif_perpendicularidad').join(', ');
        const plan = marcadosEtiqueta('verif_planitud').join(', ');
        Array.from(document.querySelectorAll('[data-medida]')).forEach(function (i) {
            const lab = i.closest('label');
            const et = lab ? lab.querySelector('span').textContent.trim() : i.dataset.medida;
            const id = (i.dataset.medida || '').toLowerCase();
            if (/carga/.test(id)) {
                filas.push(['Perpendicularidad', perp]);
                filas.push(['Planitud', plan]);
            }
            filas.push([et, i.value.trim(), i.dataset.medida]);
            if (id === 'd2') filas.push(['Verificación del diámetro', vdTxt]);
        });
        filas.push(['Tipo de fractura', valorDe('tipo_fractura')]);
        return filas;
    }
    function estaMarcada(clave) { return !!clave && Object.prototype.hasOwnProperty.call(marcas, clave); }
    function notaMarca(clave) {
        // Revisor: caja para escribir qué está mal. Técnico: el comentario del revisor.
        if (revision) {
            const inp = elemento('input', 'hf__nota-in');
            inp.type = 'text'; inp.maxLength = 300; inp.placeholder = '¿Qué está mal? (opcional)'; inp.value = marcas[clave] || '';
            inp.addEventListener('click', function (e) { e.stopPropagation(); });
            inp.addEventListener('input', function () { marcas[clave] = inp.value; sincronizarMarcas(false); });
            return inp;
        }
        return elemento('span', 'hf__nota', marcas[clave] || 'Corregir este dato');
    }
    function alternarMarca(clave) {
        if (estaMarcada(clave)) delete marcas[clave]; else marcas[clave] = '';
        sincronizarMarcas(true);
    }
    // Marca visual (y clic del revisor) sobre un elemento de la hoja.
    function hacerMarcable(el, clave) {
        if (!clave) return;
        if (estaMarcada(clave)) el.classList.add('hf-mal');
        if (revision) {
            el.classList.add('hf-marcable');
            el.title = estaMarcada(clave) ? 'Quitar la marca' : 'Marcar como incorrecto';
            el.addEventListener('click', function () { alternarMarca(clave); });
        }
    }
    function filaTabla(tb, etiqueta, valor, clave, vacioOk) {
        const tr = elemento('tr'); tr.appendChild(elemento('th', '', etiqueta));
        const td = elemento('td', '', valor || '—'); if (!valor) td.setAttribute('data-vacio', ''); tr.appendChild(td);
        hacerMarcable(tr, clave); tb.appendChild(tr);
        if (clave && estaMarcada(clave)) {
            const n = elemento('tr', 'hf-nota'); const c = elemento('td'); c.colSpan = 2; c.appendChild(notaMarca(clave)); n.appendChild(c); tb.appendChild(n);
        }
    }
    function sincronizarMarcas(redibujar) {
        const n = Object.keys(marcas).length;
        document.querySelectorAll('[data-marcas-n]').forEach(function (e) { e.textContent = String(n); });
        document.querySelectorAll('[data-marcas-json]').forEach(function (e) { e.value = JSON.stringify(marcas); });
        document.querySelectorAll('[data-devolver-ensayo]').forEach(function (b) { b.disabled = false; });
        if (redibujar) pintarResumen();
        aplicarMarcasForm();
        if (revision) {
            clearTimeout(temporizador);
            temporizador = setTimeout(guardarMarcas, 600);
        }
    }
    function guardarMarcas() {
        const url = raiz.dataset.urlMarcas;
        const token = document.querySelector('[name="csrfmiddlewaretoken"]');
        if (!url || !token) return;
        const fd = new FormData(); fd.append('marcas', JSON.stringify(marcas)); fd.append('csrfmiddlewaretoken', token.value);
        fetch(url, { method: 'POST', body: fd, credentials: 'same-origin', headers: { 'X-Requested-With': 'XMLHttpRequest' } }).catch(function () {});
    }
    // Pinta en rojo, dentro del formulario y de las fotos, lo marcado (para el técnico y para el revisor).
    function aplicarMarcasForm() {
        document.querySelectorAll('.rg-mal').forEach(function (e) { e.classList.remove('rg-mal'); });
        document.querySelectorAll('[data-nota-mal]').forEach(function (e) { e.remove(); });
        Object.keys(marcas).forEach(function (clave) {
            let caja = null;
            if (clave.indexOf('foto:') === 0) {
                const slot = document.querySelector('[data-slot="' + clave.slice(5) + '"]');
                caja = slot ? slot.querySelector('[data-marco]') : null;
            } else if (clave === 'tipos_defecto') {
                caja = document.querySelector('[data-defectos]');
            } else if (clave === 'video') {
                caja = document.querySelector('[data-video]');
            } else {
                const campo = document.querySelector('[name="' + clave + '"]');
                caja = campo ? (campo.closest('fieldset') || campo.closest('label') || campo.parentElement) : null;
            }
            if (!caja) return;
            caja.classList.add('rg-mal');
            if (marcas[clave] && !revision) {
                const nota = elemento('p', 'rg-mal__nota', marcas[clave]); nota.setAttribute('data-nota-mal', '');
                caja.insertAdjacentElement('afterend', nota);
            }
        });
        // Menú lateral del formulario: avisa en rojo qué sección tiene datos marcados.
        document.querySelectorAll('[data-ir-sec]').forEach(function (b) {
            const sec = document.querySelector('.rg-sec[data-sec="' + b.dataset.irSec + '"]');
            const n = sec ? sec.querySelectorAll('.rg-mal').length : 0;
            b.classList.toggle('rg-rail__b--mal', n > 0);
            let ins = b.querySelector('.rg-rail__mal');
            if (n > 0) { if (!ins) { ins = elemento('i', 'rg-rail__mal'); b.appendChild(ins); } ins.textContent = n + ' por corregir'; }
            else if (ins) ins.remove();
        });
        document.querySelectorAll('[data-marcar-foto]').forEach(function (b) {
            const clave = 'foto:' + b.dataset.marcarFoto;
            b.classList.toggle('rg-marcar--on', estaMarcada(clave));
            b.textContent = estaMarcada(clave) ? 'Marcada: quitar' : 'Marcar como mal';
        });
    }
    document.querySelectorAll('[data-marcar-foto]').forEach(function (b) {
        b.addEventListener('click', function () { alternarMarca('foto:' + b.dataset.marcarFoto); });
    });
    function llenaFila(f) { return !!f[1]; }
    function sincronizarMarcasInicial() {
        document.querySelectorAll('[data-marcas-n]').forEach(function (e) { e.textContent = String(Object.keys(marcas).length); });
        document.querySelectorAll('[data-marcas-json]').forEach(function (e) { e.value = JSON.stringify(marcas); });
        aplicarMarcasForm();
    }
    function itemLista(texto, ok, valor, clave) {
        const li = elemento('div', 'hf__li');
        hacerMarcable(li, clave);
        if (ok) li.setAttribute('data-ok', '');
        li.appendChild(elemento('i', '', ok ? '☑' : '☐'));
        li.appendChild(elemento('span', '', texto));
        if (valor) li.appendChild(elemento('b', '', valor));
        return li;
    }
    function bloque(titulo) {
        const sec = elemento('section');
        sec.appendChild(elemento('div', 'hf__h', titulo));
        return sec;
    }
    function hayDatos() {
        return filasHoja().some(function (f) {
            return f[1] && f[0] !== 'Fecha de ensayo' && f[0] !== 'ID del laboratorio' && f[0] !== 'Fecha de recepción' && f[0] !== 'Testigo / muestra N.º';
        }) || Array.from(document.querySelectorAll('[data-dato], #resumen')).some(function (i) { return i.value && i.value.trim(); });
    }
    function celda(etq, valor) {
        const c = elemento('div', 'hf__celda'); c.appendChild(elemento('span', '', etq));
        const b = elemento('b', '', valor || '—'); if (!valor) b.setAttribute('data-vacio', ''); c.appendChild(b);
        return c;
    }
    function pintarResumen() {
        if (!resumenCuerpo) return;
        resumenCuerpo.textContent = '';
        const filas = filasHoja();
        const ses = HOJA.sesion || null;
        // Avance: filas propias del formato (sin las fijas) llenadas.
        const fijas = ['Testigo / muestra N.º', 'ID del laboratorio', 'Fecha de recepción'];
        const medibles = filas.filter(function (f) { return fijas.indexOf(f[0]) < 0; });
        const extra = Array.from(document.querySelectorAll('[data-dato]'));
        let total = medibles.length + extra.length, llenas = medibles.filter(llenaFila).length + extra.filter(function (i) { return i.value && i.value.trim(); }).length;
        const hoja = elemento('div', 'hf');
        // Cabecera
        const cab = elemento('div', 'hf__cab');
        const izq = elemento('div');
        izq.appendChild(elemento('div', 'hf__marca', 'Grupo VICAF · Laboratorio de ensayos'));
        izq.appendChild(elemento('div', 'hf__titulo', esCompresion ? 'Registro de ensayo de compresión de probetas' : 'Registro de ensayo · ' + (HOJA.ensayo || '')));
        izq.appendChild(elemento('div', 'hf__sub', (HOJA.norma || '') + (esCompresion ? ' · Formato FOR-009' : '')));
        const der = elemento('div', 'hf__reg'); der.appendChild(document.createTextNode('Registro N.º')); der.appendChild(elemento('b', '', HOJA.registro || '—'));
        cab.appendChild(izq); cab.appendChild(der);
        hoja.appendChild(cab);
        const prog = elemento('div', 'hf__prog'); const pi = elemento('i'); pi.style.width = (total ? Math.round(llenas / total * 100) : 0) + '%'; prog.appendChild(pi); prog.title = llenas + ' de ' + total + ' datos'; hoja.appendChild(prog);
        // Fila de datos del cliente y condiciones
        const fila = elemento('div', 'hf__fila');
        fila.appendChild(celda('Código de cliente', codigoClienteOficial));
        fila.appendChild(celda('Temperatura inicial / final', ses ? ((ses.t_ini || '—') + ' / ' + (ses.t_fin || '—') + ' °C') : ''));
        fila.appendChild(celda('Humedad rel. inicial / final', ses ? ((ses.hr_ini || '—') + ' / ' + (ses.hr_fin || '—') + ' %') : ''));
        fila.appendChild(celda('Técnico', HOJA.tecnico || ''));
        hoja.appendChild(fila);
        // Cuerpo
        const cuerpo = elemento('div', 'hf__cuerpo');
        const colI = elemento('div', 'hf__izq');
        colI.appendChild(elemento('div', 'hf__h', 'Resultados de ensayo'));
        const tabla = elemento('table', 'hf__t'); const tb = elemento('tbody');
        filas.forEach(function (f) {
            if (!esCompresion && !f[1] && fijas.indexOf(f[0]) < 0 && f[0] !== 'Fecha de ensayo') return;
            filaTabla(tb, f[0], f[1], f[2] || CLAVES[f[0]]);
        });
        // Datos propios del servicio
        extra.forEach(function (i) {
            const v = i.tagName === 'SELECT' ? (i.value ? i.selectedOptions[0].text.trim() : '') : i.value.trim();
            if (!v && !esCompresion) return;
            filaTabla(tb, i.dataset.etiqueta || '', v, i.name);
        });
        const notas = document.getElementById('resumen');
        if (notas && notas.value.trim()) filaTabla(tb, 'Resumen o notas', notas.value.trim(), 'resumen');
        const obs = valorDe('observaciones');
        if (obs) filaTabla(tb, 'Observaciones', obs, 'observaciones');
        tabla.appendChild(tb); colI.appendChild(tabla); cuerpo.appendChild(colI);
        const colD = elemento('div', 'hf__der');
        // Evidencia multimedia
        const ev = bloque('Evidencia multimedia'); const evl = elemento('div', 'hf__lista');
        [['antes', 'Fotos antes del ensayo'], ['durante', 'Fotos durante la carga'], ['despues', 'Fotos después (probeta rota)']].forEach(function (g) {
            const caja = document.querySelector('[data-grupo-fotos="' + g[0] + '"]');
            const marcos = caja ? caja.querySelectorAll('[data-marco]').length : 2;
            const hechas = caja ? caja.querySelectorAll('[data-marco][data-estado="ok"]').length : 0;
            const li = itemLista(g[1], hechas > 0 && hechas === marcos, hechas + '/' + marcos);
            if (Object.keys(marcas).some(function (k) { return k.indexOf('foto:' + g[0]) === 0; })) li.classList.add('hf-mal');
            evl.appendChild(li);
        });
        const hayVideo = !!document.querySelector('[data-video-estado] a');
        const marcaVideo = document.querySelector('[name="video_grabado"]:checked');
        evl.appendChild(itemLista('Video del ensayo', hayVideo || !!marcaVideo, hayVideo ? 'Subido' : (marcaVideo ? 'Sin archivo' : ''), 'video'));
        ev.appendChild(evl); colD.appendChild(ev);
        // Equipamiento
        const eq = bloque('Equipamiento empleado'); const eql = elemento('div', 'hf__lista');
        if (ses && ses.equipos && ses.equipos.length) ses.equipos.forEach(function (e) { eql.appendChild(itemLista(e.etiqueta, true, e.codigo)); });
        else eql.appendChild(elemento('div', 'hf__li', esCompresion ? 'Se completa al abrir la sesión.' : '—'));
        eq.appendChild(eql); colD.appendChild(eq);
        // Defectos
        const defs = Array.from(document.querySelectorAll('[name="tipos_defecto"]'));
        if (defs.length) {
            const df = bloque('Tipos de defecto'); hacerMarcable(df.firstChild, 'tipos_defecto'); const dfl = elemento('div', 'hf__lista');
            defs.forEach(function (c) { dfl.appendChild(itemLista(c.closest('label').textContent.trim(), c.checked)); });
            const otros = valorDe('defectos'); if (otros) dfl.appendChild(itemLista('Otros: ' + otros, true));
            df.appendChild(dfl); colD.appendChild(df);
        }
        // Comprobación funcional
        if (ses && ses.comprobacion && ses.comprobacion.length) {
            const cp = bloque('Comprobación funcional de equipos'); const cpl = elemento('div', 'hf__lista');
            const porEquipo = {};
            ses.comprobacion.forEach(function (c) { (porEquipo[c.equipo] = porEquipo[c.equipo] || []).push(c); });
            Object.keys(porEquipo).forEach(function (k) {
                const items = porEquipo[k]; const ok = items.every(function (c) { return c.conforme; });
                cpl.appendChild(itemLista(k, ok, ok ? 'Conforme' : 'Observado'));
            });
            cp.appendChild(cpl); colD.appendChild(cp);
        }
        // Resultado preliminar
        if (esCompresion) {
            const rp = bloque('Resultado preliminar'); const box = elemento('div', 'hf__res');
            const k = textoR('kgcm2');
            const a = elemento('div'); a.appendChild(elemento('small', '', 'Resistencia')); a.appendChild(document.createElement('br'));
            a.appendChild(elemento('b', '', k ? k : '—')); a.appendChild(elemento('small', '', k ? ' kg/cm² · ' + textoR('mpa') + ' MPa' : ''));
            const p = elemento('div'); p.appendChild(elemento('small', '', "% de f'c")); p.appendChild(document.createElement('br'));
            p.appendChild(elemento('b', '', textoR('porcentaje') ? textoR('porcentaje') + ' %' : '—'));
            box.appendChild(a); box.appendChild(p); rp.appendChild(box); colD.appendChild(rp);
        }
        // Firmas
        const fr = elemento('section'); const firmas = elemento('div', 'hf__firmas');
        [['Técnico', HOJA.tecnico || ''], ['Supervisor', ''], ['Jefe de laboratorio', '']].forEach(function (x) {
            const d = elemento('div'); if (x[1]) d.appendChild(elemento('b', '', x[1])); d.appendChild(document.createTextNode(x[0])); firmas.appendChild(d);
        });
        fr.appendChild(firmas); colD.appendChild(fr);
        cuerpo.appendChild(colD); hoja.appendChild(cuerpo);
        if (!hayDatos()) {
            resumenCuerpo.appendChild(elemento('p', 'rg-resumen__vacio', 'Aún no hay datos. Pulsa «Llenar formulario»: lo que llenes se ve aquí como en la hoja del laboratorio.'));
        }
        resumenCuerpo.appendChild(hoja);
        document.querySelectorAll('[data-texto-abrir-formulario]').forEach(function (e) { e.textContent = hayDatos() ? 'Editar formulario' : 'Llenar formulario'; });
        const est = document.querySelector('[data-resumen-estado]');
        if (est && revision) est.textContent = 'Toca un dato para marcarlo en rojo; vuelve a tocarlo para quitar la marca.';
        else if (est) est.textContent = hayDatos() ? 'Lo llenado hasta ahora. Pulsa «Editar formulario» para completar o corregir.' : 'Se agregan aquí cuando pulses «Listo» en el formulario.';
        aplicarMarcasForm();
    }
    sincronizarMarcasInicial();
    window.HojaResumen = { pintar: pintarResumen, hayDatos: hayDatos, hoja: HOJA };
})();
