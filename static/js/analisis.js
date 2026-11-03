/* analisis.js — pantalla Análisis del LIMS (VCF-LIMS, HU-LIMS-06 a 10).
 *
 * Tabla dinámica con PivotTable.js 2.23 (jQuery + jQuery UI), gráficos con
 * Chart.js 4.4.1 y exportación .xlsx con SheetJS 0.18.5, todo servido desde
 * static/vendor y cargado con defer antes que este archivo.
 *
 * El servidor entrega filas planas con la lista blanca de cada conjunto
 * (analisis/conjuntos.py); aquí no se calcula nada que el servidor no haya
 * autorizado. La configuración de la tabla viaja en el hash de la URL para
 * que el enlace se pueda compartir (CA-08.3).
 */
(function () {
    'use strict';

    // Paleta categórica validada (specs/VCF-LIMS/design.md, skill dataviz), orden fijo.
    var SERIES = ['#2a78d6', '#eb6834', '#1baf7a', '#eda100', '#e87ba4', '#008300', '#6250d6', '#e34948'];
    var GRIS_OTROS = '#8a8984';
    var MAX_CATEGORIAS = 20;   // CA-07.3
    var MAX_SERIES = SERIES.length;
    var CLAVES_CONFIG = ['rows', 'cols', 'vals', 'aggregatorName', 'rendererName',
        'exclusions', 'inclusions', 'rowOrder', 'colOrder'];

    var $ = window.jQuery;
    var cfg = JSON.parse(document.getElementById('analisis-config').textContent);
    var estado = {
        conjunto: null,       // resumen del conjunto activo
        desde: '',
        hasta: '',
        datos: null,          // {encabezado, numericos, filas}
        config: {},           // disposición actual de la tabla
        pivotData: null,      // último resultado calculado (para exportar y graficar)
        grafico: null,
        misVistas: []
    };

    function el(id) { return document.getElementById(id); }

    // ------------------------------------------------------------------
    // Formatos
    // ------------------------------------------------------------------
    var utils = $.pivotUtilities;
    var fmtMonto = utils.numberFormat({ thousandsSep: ',', decimalSep: '.', digitsAfterDecimal: 2 });
    var fmtEntero = utils.numberFormat({ thousandsSep: ',', decimalSep: '.', digitsAfterDecimal: 0 });
    var tpl = utils.aggregatorTemplates;
    var AGREGADORES = {
        'Cantidad': tpl.count(fmtEntero),
        'Suma': tpl.sum(fmtMonto),
        'Promedio': tpl.average(fmtMonto),
        'Mínimo': tpl.min(fmtMonto),
        'Máximo': tpl.max(fmtMonto)
    };
    var formatoExcel = function (nombreAgregador) {
        return nombreAgregador === 'Cantidad' ? '#,##0' : '#,##0.00';
    };

    // ------------------------------------------------------------------
    // Fechas
    // ------------------------------------------------------------------
    function iso(d) {
        var m = String(d.getMonth() + 1).padStart(2, '0');
        var dia = String(d.getDate()).padStart(2, '0');
        return d.getFullYear() + '-' + m + '-' + dia;
    }

    function rangoPeriodo(clave) {
        var hoy = new Date();
        if (clave === 'mes') {
            return [iso(new Date(hoy.getFullYear(), hoy.getMonth(), 1)), iso(new Date(hoy.getFullYear(), hoy.getMonth() + 1, 0))];
        }
        if (clave === 'anio') {
            return [hoy.getFullYear() + '-01-01', hoy.getFullYear() + '-12-31'];
        }
        if (clave === '12m') {
            return [iso(new Date(hoy.getFullYear(), hoy.getMonth() - 11, 1)), iso(hoy)];
        }
        return ['', ''];
    }

    function textoRango() {
        if (!estado.desde && !estado.hasta) return 'Todo el historial';
        return 'Del ' + (estado.desde || 'inicio') + ' al ' + (estado.hasta || 'hoy');
    }

    // ------------------------------------------------------------------
    // Avisos
    // ------------------------------------------------------------------
    function aviso(texto, tipo) {
        var nodo = el('an-aviso');
        if (!texto) {
            nodo.className = 'hidden';
            nodo.textContent = '';
            return;
        }
        var clases = tipo === 'error'
            ? 'rounded-lg border px-3 py-2 text-sm border-red-200 bg-red-50 text-red-800'
            : 'rounded-lg border px-3 py-2 text-sm border-slate-200 bg-slate-50 text-slate-700';
        nodo.className = clases;
        nodo.setAttribute('data-tipo', tipo || 'info');
        nodo.textContent = texto;
    }

    // ------------------------------------------------------------------
    // Estado en la URL (CA-06.2, CA-08.3)
    // ------------------------------------------------------------------
    function soloDisposicion(config) {
        var limpia = {};
        CLAVES_CONFIG.forEach(function (k) {
            if (config[k] !== undefined) limpia[k] = config[k];
        });
        return limpia;
    }

    function escribirUrl() {
        var params = new URLSearchParams();
        params.set('conjunto', estado.conjunto.clave);
        params.set('desde', estado.desde);
        params.set('hasta', estado.hasta);
        var hash = '#c=' + encodeURIComponent(JSON.stringify(estado.config));
        history.replaceState(null, '', location.pathname + '?' + params.toString() + hash);
    }

    function leerUrl() {
        var params = new URLSearchParams(location.search);
        var config = null;
        var m = location.hash.match(/^#c=(.*)$/);
        if (m) {
            try { config = JSON.parse(decodeURIComponent(m[1])); } catch (e) { config = null; }
        }
        return {
            conjunto: params.get('conjunto'),
            tieneRango: params.has('desde') || params.has('hasta'),
            desde: params.get('desde') || '',
            hasta: params.get('hasta') || '',
            config: config && typeof config === 'object' ? config : null
        };
    }

    // ------------------------------------------------------------------
    // Gráficos (HU-LIMS-07)
    // ------------------------------------------------------------------
    function valor(agg) {
        var v = agg.value();
        return (v === null || v === undefined || isNaN(v)) ? 0 : v;
    }

    function serieDatos(pivotData) {
        var rowKeys = pivotData.getRowKeys();
        var colKeys = pivotData.getColKeys();
        if (!rowKeys.length) rowKeys = [[]];
        var avisos = [];

        // Columnas → series (máximo 8; el resto a "Otros").
        var series;
        if (!colKeys.length) {
            series = [{ nombre: pivotData.aggregatorName + (pivotData.valAttrs.length ? ' de ' + pivotData.valAttrs.join(', ') : ''),
                claves: [[]] }];
        } else {
            var porTotal = colKeys.map(function (c) { return { c: c, t: valor(pivotData.getAggregator([], c)) }; })
                .sort(function (a, b) { return b.t - a.t; });
            var principales = porTotal.slice(0, colKeys.length > MAX_SERIES ? MAX_SERIES - 1 : MAX_SERIES)
                .map(function (x) { return x.c; });
            var conjuntoPrincipal = principales.map(function (c) { return JSON.stringify(c); });
            series = colKeys.filter(function (c) { return conjuntoPrincipal.indexOf(JSON.stringify(c)) >= 0; })
                .map(function (c) { return { nombre: c.join(' · '), claves: [c] }; });
            if (colKeys.length > principales.length) {
                series.push({ nombre: 'Otros', claves: colKeys.filter(function (c) { return conjuntoPrincipal.indexOf(JSON.stringify(c)) < 0; }), otros: true });
                avisos.push('Se muestran las ' + (MAX_SERIES - 1) + ' series mayores; el resto se suma en "Otros".');
            }
        }

        // Filas → categorías (máximo 20; el resto a "Otros").
        var categorias = rowKeys;
        var otrasFilas = [];
        if (rowKeys.length > MAX_CATEGORIAS) {
            var totales = rowKeys.map(function (r, i) { return { i: i, t: valor(pivotData.getAggregator(r, [])) }; })
                .sort(function (a, b) { return b.t - a.t; });
            var elegidos = totales.slice(0, MAX_CATEGORIAS).map(function (x) { return x.i; }).sort(function (a, b) { return a - b; });
            categorias = elegidos.map(function (i) { return rowKeys[i]; });
            otrasFilas = rowKeys.filter(function (r, i) { return elegidos.indexOf(i) < 0; });
            avisos.push('Hay ' + rowKeys.length + ' categorías: se muestran las ' + MAX_CATEGORIAS + ' mayores y el resto se agrupa en "Otros".');
        }

        function celda(filas, claveSerie) {
            var suma = 0;
            filas.forEach(function (r) {
                claveSerie.claves.forEach(function (c) { suma += valor(pivotData.getAggregator(r, c)); });
            });
            return suma;
        }

        var etiquetas = categorias.map(function (r) { return r.length ? r.join(' · ') : 'Total'; });
        if (otrasFilas.length) etiquetas.push('Otros');
        var datasets = series.map(function (s) {
            var datos = categorias.map(function (r) { return celda([r], s); });
            if (otrasFilas.length) datos.push(celda(otrasFilas, s));
            return { nombre: s.nombre, datos: datos, otros: !!s.otros };
        });
        var totalesFila = categorias.map(function (r) { return valor(pivotData.getAggregator(r, [])); });
        if (otrasFilas.length) {
            totalesFila.push(otrasFilas.reduce(function (acc, r) { return acc + valor(pivotData.getAggregator(r, [])); }, 0));
        }
        return { etiquetas: etiquetas, datasets: datasets, totalesFila: totalesFila, avisos: avisos, conColumnas: colKeys.length > 0 };
    }

    function rendererGrafico(tipo) {
        return function (pivotData) {
            estado.pivotData = pivotData;
            var contenedor = $('<div class="an-grafico" data-grafico></div>').attr('data-tipo', tipo);
            var datos = serieDatos(pivotData);
            var avisos = datos.avisos.slice();
            var esCantidad = pivotData.aggregatorName === 'Cantidad';
            var formato = esCantidad ? fmtEntero : fmtMonto;

            var dsChart;
            if (tipo === 'dona') {
                if (datos.conColumnas) avisos.push('La dona usa solo el total por fila; las columnas no se muestran.');
                dsChart = [{
                    label: 'Total',
                    data: datos.totalesFila,
                    backgroundColor: datos.etiquetas.map(function (e, i) {
                        return e === 'Otros' ? GRIS_OTROS : SERIES[i % SERIES.length];
                    }),
                    borderColor: '#ffffff',
                    borderWidth: 2
                }];
                if (datos.etiquetas.length > SERIES.length) {
                    avisos.push('La dona se lee mal con más de ' + SERIES.length + ' partes: prueba con barras.');
                }
            } else {
                dsChart = datos.datasets.map(function (d, i) {
                    var color = d.otros ? GRIS_OTROS : SERIES[i % SERIES.length];
                    var base = { label: d.nombre, data: d.datos, backgroundColor: color, borderColor: color };
                    if (tipo === 'lineas') {
                        base.borderWidth = 2;
                        base.pointRadius = 4;
                        base.pointHoverRadius = 6;
                        base.tension = 0;
                        base.fill = false;
                    } else {
                        // 2px de superficie entre segmentos apilados (skill dataviz).
                        base.borderWidth = tipo === 'apiladas' ? { top: 2, right: 0, bottom: 0, left: 0 } : 0;
                        base.borderColor = '#ffffff';
                        base.borderRadius = 4;
                        base.maxBarThickness = 36;
                    }
                    return base;
                });
            }

            avisos.forEach(function (t) { contenedor.append($('<p class="an-grafico-aviso" data-aviso-grafico></p>').text(t)); });
            var lienzo = $('<div class="an-grafico-lienzo"><canvas role="img"></canvas></div>');
            lienzo.find('canvas').attr('aria-label', 'Gráfico: ' + pivotData.aggregatorName + ' por ' + (pivotData.rowAttrs.join(', ') || 'total'));
            contenedor.append(lienzo);

            var multiSerie = dsChart.length > 1 || tipo === 'dona';
            setTimeout(function () {
                var canvas = lienzo.find('canvas')[0];
                if (!canvas || !document.body.contains(canvas)) return;
                if (estado.grafico) { estado.grafico.destroy(); estado.grafico = null; }
                var tipoChart = tipo === 'dona' ? 'doughnut' : (tipo === 'lineas' ? 'line' : 'bar');
                var apilado = tipo === 'apiladas';
                estado.grafico = new window.Chart(canvas, {
                    type: tipoChart,
                    data: { labels: datos.etiquetas, datasets: dsChart },
                    options: {
                        responsive: true,
                        maintainAspectRatio: false,
                        animation: false,
                        interaction: { mode: tipo === 'lineas' ? 'index' : 'nearest', intersect: tipo !== 'lineas' },
                        plugins: {
                            legend: { display: multiSerie, position: 'bottom', labels: { boxWidth: 12, boxHeight: 12 } },
                            tooltip: {
                                backgroundColor: '#0f172a',
                                padding: 10,
                                cornerRadius: 8,
                                callbacks: {
                                    label: function (ctx) {
                                        var v = tipo === 'dona' ? ctx.parsed : (ctx.parsed.y !== undefined ? ctx.parsed.y : ctx.parsed);
                                        return ' ' + ctx.dataset.label + ': ' + formato(v);
                                    }
                                }
                            }
                        },
                        scales: tipo === 'dona' ? {} : {
                            x: { stacked: apilado, grid: { display: false }, ticks: { color: '#6b6a65', autoSkip: true, maxRotation: 45 } },
                            y: { stacked: apilado, beginAtZero: true, grid: { color: '#e1e0d9' }, border: { display: false },
                                ticks: { color: '#6b6a65', precision: esCantidad ? 0 : undefined,
                                    callback: function (v) { return formato(v); } } }
                        }
                    }
                });
                canvas.setAttribute('data-listo', '1');
            }, 0);
            return contenedor;
        };
    }

    var tablaBase = utils.renderers['Table'];
    var RENDERERS = {
        'Tabla': function (pivotData, opts) {
            estado.pivotData = pivotData;
            if (estado.grafico) { estado.grafico.destroy(); estado.grafico = null; }
            return tablaBase(pivotData, opts);
        },
        'Barras': rendererGrafico('barras'),
        'Barras apiladas': rendererGrafico('apiladas'),
        'Líneas': rendererGrafico('lineas'),
        'Dona': rendererGrafico('dona')
    };

    // ------------------------------------------------------------------
    // Tabla dinámica (HU-LIMS-06)
    // ------------------------------------------------------------------
    function configValida(config) {
        var atributos = estado.datos.encabezado;
        var numericos = estado.datos.numericos;
        var limpia = soloDisposicion(config || {});
        ['rows', 'cols'].forEach(function (k) {
            limpia[k] = (limpia[k] || []).filter(function (a) { return atributos.indexOf(a) >= 0; });
        });
        limpia.vals = (limpia.vals || []).filter(function (a) { return numericos.indexOf(a) >= 0; });
        if (!AGREGADORES[limpia.aggregatorName]) limpia.aggregatorName = 'Cantidad';
        if (!RENDERERS[limpia.rendererName]) limpia.rendererName = 'Tabla';
        if (limpia.aggregatorName !== 'Cantidad' && !limpia.vals.length && numericos.length) {
            limpia.vals = [numericos[0]];
        }
        ['exclusions', 'inclusions'].forEach(function (k) {
            var filtrado = {};
            Object.keys(limpia[k] || {}).forEach(function (a) {
                if (atributos.indexOf(a) >= 0 && Array.isArray(limpia[k][a])) filtrado[a] = limpia[k][a];
            });
            limpia[k] = filtrado;
        });
        return limpia;
    }

    function pintarPivot(config) {
        var datos = estado.datos;
        var entrada = [datos.encabezado].concat(datos.filas);
        var disposicion = configValida(config);
        var textos = datos.encabezado.filter(function (a) { return datos.numericos.indexOf(a) < 0; });
        var opciones = $.extend({}, disposicion, {
            aggregators: AGREGADORES,
            renderers: RENDERERS,
            hiddenFromAggregators: textos,
            menuLimit: 1000,
            unusedAttrsVertical: false,
            onRefresh: function (actual) {
                var nueva = soloDisposicion(actual);
                // Al guardar, los filtros quedan como exclusiones: los valores
                // nuevos que aparezcan después se muestran por defecto.
                delete nueva.inclusions;
                estado.config = nueva;
                escribirUrl();
                el('an-estado').textContent = textoRango() + ' · ' + datos.filas.length.toLocaleString('es-PE') + ' registros de ' + estado.conjunto.nombre;
            }
        });
        $('#an-pivot').pivotUI(entrada, opciones, true, 'es');
    }

    function urlDatos() {
        var base = cfg.urls.datos.replace('__conjunto__', encodeURIComponent(estado.conjunto.clave));
        var params = new URLSearchParams({ desde: estado.desde, hasta: estado.hasta });
        return base + '?' + params.toString();
    }

    function cargar(configInicial) {
        aviso('');
        if (estado.desde && estado.hasta && estado.desde > estado.hasta) {
            aviso('La fecha "desde" es posterior a "hasta". Corrige el rango.', 'error');   // CA-06.6
            return Promise.resolve();
        }
        el('an-estado').textContent = 'Cargando…';
        return fetch(urlDatos(), { headers: { 'Accept': 'application/json' }, credentials: 'same-origin' })
            .then(function (r) { return r.json().then(function (j) { return { ok: r.ok, json: j }; }); })
            .then(function (res) {
                if (!res.ok) {
                    aviso(res.json.error || 'No se pudieron cargar los datos.', 'error');
                    el('an-estado').textContent = '';
                    return;
                }
                estado.datos = res.json;
                if (!res.json.filas.length) {
                    aviso('Sin datos para estos filtros. Cambia el rango de fechas o el conjunto.', 'info');
                }
                pintarPivot(configInicial || estado.config);
            })
            .catch(function () {
                aviso('No se pudieron cargar los datos. Revisa tu conexión e inténtalo de nuevo.', 'error');
                el('an-estado').textContent = '';
            });
    }

    // ------------------------------------------------------------------
    // Exportar (HU-LIMS-09)
    // ------------------------------------------------------------------
    function descripcionFiltros(config) {
        var partes = [];
        Object.keys(config.exclusions || {}).forEach(function (a) {
            var excluidos = config.exclusions[a];
            if (excluidos && excluidos.length) partes.push(a + ' sin: ' + excluidos.join(', '));
        });
        return partes.length ? partes.join(' | ') : 'Ninguno';
    }

    function cabeceraExcel(titulo) {
        var c = estado.config;
        return [
            [titulo],
            ['Conjunto', estado.conjunto.nombre],
            ['Rango', textoRango()],
            ['Filas', (c.rows || []).join(', ') || '—', 'Columnas', (c.cols || []).join(', ') || '—'],
            ['Cálculo', (c.aggregatorName || 'Cantidad') + ((c.vals || []).length ? ' de ' + c.vals.join(', ') : '')],
            ['Filtros', descripcionFiltros(c)],
            ['Generado', new Date().toLocaleString('es-PE')],
            []
        ];
    }

    function descargar(aoa, nombreHoja, archivo, filaInicioNumeros, columnaInicioNumeros, formato) {
        var XLSX = window.XLSX;
        var hoja = XLSX.utils.aoa_to_sheet(aoa);
        if (formato) {
            var rango = XLSX.utils.decode_range(hoja['!ref']);
            for (var r = filaInicioNumeros; r <= rango.e.r; r++) {
                for (var col = columnaInicioNumeros; col <= rango.e.c; col++) {
                    var celda = hoja[XLSX.utils.encode_cell({ r: r, c: col })];
                    if (celda && celda.t === 'n') celda.z = formato;
                }
            }
        }
        var libro = XLSX.utils.book_new();
        XLSX.utils.book_append_sheet(libro, hoja, nombreHoja);
        XLSX.writeFile(libro, archivo);
    }

    function nombreArchivo(sufijo) {
        return 'analisis-' + estado.conjunto.clave + '-' + sufijo + '-' + iso(new Date()) + '.xlsx';
    }

    function exportarTabla() {
        var pd = estado.pivotData;
        if (!pd) return;
        var rowKeys = pd.getRowKeys();
        var colKeys = pd.getColKeys();
        var filasAttr = pd.rowAttrs.length ? pd.rowAttrs : [''];
        var aoa = cabeceraExcel('Análisis VICAF · Tabla dinámica');
        var inicio = aoa.length;
        var encabezado = filasAttr.slice();
        colKeys.forEach(function (c) { encabezado.push(c.join(' · ')); });
        encabezado.push('Totales');
        aoa.push(encabezado);
        var num = function (agg) { var v = agg.value(); return (v === null || v === undefined || isNaN(v)) ? null : v; };
        (rowKeys.length ? rowKeys : [[]]).forEach(function (r) {
            var fila = filasAttr.map(function (_, i) { return r[i] !== undefined ? r[i] : 'Total'; });
            colKeys.forEach(function (c) { fila.push(num(pd.getAggregator(r, c))); });
            fila.push(num(pd.getAggregator(r, [])));
            aoa.push(fila);
        });
        if (rowKeys.length) {
            var totales = filasAttr.map(function (_, i) { return i === 0 ? 'Totales' : ''; });
            colKeys.forEach(function (c) { totales.push(num(pd.getAggregator([], c))); });
            totales.push(num(pd.getAggregator([], [])));
            aoa.push(totales);
        }
        descargar(aoa, 'Tabla', nombreArchivo('tabla'), inicio + 1, filasAttr.length, formatoExcel(pd.aggregatorName));
    }

    function exportarDatos() {
        if (!estado.datos) return;
        var exclusiones = estado.config.exclusions || {};
        var encabezado = estado.datos.encabezado;
        var indices = Object.keys(exclusiones).map(function (a) { return [encabezado.indexOf(a), exclusiones[a]]; })
            .filter(function (x) { return x[0] >= 0; });
        var filas = estado.datos.filas.filter(function (f) {
            return indices.every(function (x) { return x[1].indexOf(String(f[x[0]])) < 0; });
        });
        var aoa = cabeceraExcel('Análisis VICAF · Datos');
        var inicio = aoa.length;
        aoa.push(encabezado);
        filas.forEach(function (f) { aoa.push(f); });
        descargar(aoa, 'Datos', nombreArchivo('datos'), inicio + 1, 0, '#,##0.00');
    }

    // ------------------------------------------------------------------
    // Vistas rápidas y guardadas (HU-LIMS-08)
    // ------------------------------------------------------------------
    function pintarVistasRapidas() {
        var cont = el('an-vistas-rapidas');
        cont.innerHTML = '';
        (estado.conjunto.vistas || []).forEach(function (v) {
            var b = document.createElement('button');
            b.type = 'button';
            b.className = 'an-chip';
            b.textContent = v.nombre;
            b.setAttribute('data-vista-rapida', v.nombre);
            b.addEventListener('click', function () { if (estado.datos) pintarPivot(v); });
            cont.appendChild(b);
        });
        if (!cont.children.length) cont.textContent = '—';
    }

    function csrf() {
        var input = document.querySelector('#an-csrf input[name="csrfmiddlewaretoken"]');
        return input ? input.value : '';
    }

    function pintarMisVistas() {
        var sel = el('an-mis-vistas');
        sel.innerHTML = '<option value="">—</option>';
        estado.misVistas.filter(function (v) { return v.conjunto === estado.conjunto.clave; }).forEach(function (v) {
            var o = document.createElement('option');
            o.value = v.id;
            o.textContent = v.nombre;
            sel.appendChild(o);
        });
        el('an-eliminar-vista').disabled = true;
    }

    function cargarMisVistas() {
        return fetch(cfg.urls.vistas, { credentials: 'same-origin' })
            .then(function (r) { return r.ok ? r.json() : { vistas: [] }; })
            .then(function (j) { estado.misVistas = j.vistas || []; pintarMisVistas(); })
            .catch(function () { estado.misVistas = []; pintarMisVistas(); });
    }

    function guardarVista() {
        var nombre = el('an-nombre-vista').value.trim();
        if (!nombre) {
            aviso('Escribe un nombre para la vista.', 'error');
            el('an-nombre-vista').focus();
            return;
        }
        fetch(cfg.urls.vistas, {
            method: 'POST',
            credentials: 'same-origin',
            headers: { 'Content-Type': 'application/json', 'X-CSRFToken': csrf() },
            body: JSON.stringify({ nombre: nombre, conjunto: estado.conjunto.clave, configuracion: estado.config })
        }).then(function (r) { return r.json().then(function (j) { return { ok: r.ok, json: j }; }); })
            .then(function (res) {
                if (!res.ok) { aviso(res.json.error || 'No se pudo guardar la vista.', 'error'); return; }
                aviso('Vista "' + res.json.vista.nombre + '" guardada.', 'info');
                el('an-nombre-vista').value = '';
                return cargarMisVistas().then(function () { el('an-mis-vistas').value = res.json.vista.id; el('an-eliminar-vista').disabled = false; });
            });
    }

    function eliminarVista() {
        var id = el('an-mis-vistas').value;
        if (!id) return;
        var vista = estado.misVistas.find(function (v) { return String(v.id) === id; });
        if (!vista || !window.confirm('¿Eliminar la vista "' + vista.nombre + '"?')) return;
        fetch(cfg.urls.eliminar.replace('/0/', '/' + encodeURIComponent(id) + '/'), {
            method: 'POST', credentials: 'same-origin', headers: { 'X-CSRFToken': csrf() }
        }).then(function () { aviso('Vista eliminada.', 'info'); return cargarMisVistas(); });
    }

    // ------------------------------------------------------------------
    // Inicio
    // ------------------------------------------------------------------
    function elegirConjunto(clave, usarRangoDefecto) {
        estado.conjunto = cfg.conjuntos.find(function (c) { return c.clave === clave; }) || cfg.conjuntos[0];
        el('an-conjunto').value = estado.conjunto.clave;
        el('an-descripcion').textContent = estado.conjunto.descripcion;
        if (usarRangoDefecto) {
            var rango = rangoPeriodo(estado.conjunto.rango_defecto);
            estado.desde = rango[0];
            estado.hasta = rango[1];
        }
        el('an-desde').value = estado.desde;
        el('an-hasta').value = estado.hasta;
        pintarVistasRapidas();
        pintarMisVistas();
    }

    function iniciar() {
        if (!cfg.conjuntos.length) return;
        var sel = el('an-conjunto');
        cfg.conjuntos.forEach(function (c) {
            var o = document.createElement('option');
            o.value = c.clave;
            o.textContent = c.modulo + ' · ' + c.nombre;
            sel.appendChild(o);
        });

        var url = leerUrl();
        if (url.tieneRango) { estado.desde = url.desde; estado.hasta = url.hasta; }
        elegirConjunto(url.conjunto, !url.tieneRango);
        var inicial = url.config || (estado.conjunto.vistas[0] || {});

        sel.addEventListener('change', function () {
            // CA-06.5: se conserva lo compatible de la disposición.
            var anterior = estado.config;
            elegirConjunto(sel.value, false);
            cargar(anterior);
        });
        el('an-aplicar').addEventListener('click', function () {
            estado.desde = el('an-desde').value;
            estado.hasta = el('an-hasta').value;
            cargar(estado.config);
        });
        document.querySelectorAll('[data-periodo]').forEach(function (b) {
            b.addEventListener('click', function () {
                var rango = rangoPeriodo(b.getAttribute('data-periodo'));
                estado.desde = rango[0];
                estado.hasta = rango[1];
                el('an-desde').value = estado.desde;
                el('an-hasta').value = estado.hasta;
                cargar(estado.config);
            });
        });
        el('an-exportar').addEventListener('click', exportarTabla);
        el('an-exportar-datos').addEventListener('click', exportarDatos);
        el('an-guardar-vista').addEventListener('click', guardarVista);
        el('an-eliminar-vista').addEventListener('click', eliminarVista);
        el('an-mis-vistas').addEventListener('change', function () {
            var id = this.value;
            el('an-eliminar-vista').disabled = !id;
            var vista = estado.misVistas.find(function (v) { return String(v.id) === id; });
            if (vista && estado.datos) pintarPivot(vista.configuracion);
        });
        el('an-copiar-enlace').addEventListener('click', function () {
            var hecho = function () { aviso('Enlace copiado: abre esta misma tabla con este rango.', 'info'); };
            if (navigator.clipboard) {
                navigator.clipboard.writeText(location.href).then(hecho, function () { window.prompt('Copia el enlace:', location.href); });
            } else {
                window.prompt('Copia el enlace:', location.href);
            }
        });

        cargarMisVistas();
        cargar(inicial);
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', iniciar);
    } else {
        iniciar();
    }
})();
