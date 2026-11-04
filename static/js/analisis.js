/* analisis.js — pantalla Análisis del LIMS (VCF-LIMS, HU-LIMS-06 a 10).
 *
 * Menú de conjuntos a la izquierda; sus campos se arrastran (o se tocan) hacia
 * cuatro zonas: Filas, Columnas, Valores y Filtros. El cálculo y el formato de
 * los números viven en analisis-motor.js; aquí solo hay pantalla. Gráficos con
 * Chart.js 4.4.1 y exportación .xlsx con SheetJS 0.18.5 (static/vendor).
 *
 * El servidor entrega filas planas con la lista blanca de cada conjunto
 * (analisis/conjuntos.py). La disposición viaja en el hash de la URL para que
 * el enlace se pueda compartir (CA-08.3).
 */
(function () {
    'use strict';

    var M = window.AnalisisMotor;
    // Paleta categórica validada (specs/VCF-LIMS/design.md, skill dataviz), orden fijo.
    var SERIES = ['#2a78d6', '#eb6834', '#1baf7a', '#eda100', '#e87ba4', '#008300', '#6250d6', '#e34948'];
    var GRIS_OTROS = '#8a8984';
    var MAX_CATEGORIAS = 20;   // CA-07.3
    var MAX_PORCIONES = 7;
    var MAX_VALORES = 4;
    var ICONOS = { texto: 'Aa', periodo: 'Aa', moneda: 'S/', conteo: 'N.º', cantidad: '#', dias: 'd', porcentaje: '%' };
    var ZONAS = ['filas', 'columnas', 'valores', 'filtros'];
    var PERIODOS = ['mes', 'anio', '12m', 'todo'];

    var cfg = JSON.parse(document.getElementById('analisis-config').textContent);
    var estado = {
        conjunto: null,       // resumen del conjunto activo (campos, conteo, vistas)
        desde: '',
        hasta: '',
        datos: null,          // {encabezado, numericos, filas}
        disp: null,           // disposición actual
        resultado: null,      // último cálculo (para exportar)
        grafico: null,
        misVistas: [],
        filtroAbierto: null,
        pregunta: null
    };

    function el(id) { return document.getElementById(id); }
    function esc(t) {
        return String(t).replace(/[&<>"']/g, function (c) {
            return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c];
        });
    }

    // ------------------------------------------------------------------
    // Campos del conjunto activo
    // ------------------------------------------------------------------
    function campos() { return estado.conjunto.campos; }
    function tipoDe(etiqueta) {
        if (etiqueta === estado.conjunto.conteo) return 'conteo';
        var c = campos().find(function (x) { return x.etiqueta === etiqueta; });
        return c ? c.tipo : null;
    }
    function medidas() {
        return [{ etiqueta: estado.conjunto.conteo, tipo: 'conteo' }].concat(
            campos().filter(function (c) { return !M.esDimension(c.tipo); }));
    }
    function usado(etiqueta) {
        var d = estado.disp;
        return d.filas.indexOf(etiqueta) >= 0 || d.columnas.indexOf(etiqueta) >= 0
            || d.valores.some(function (v) { return v[0] === etiqueta; })
            || etiqueta in d.solo || etiqueta in d.excluir;
    }

    // ------------------------------------------------------------------
    // Fechas
    // ------------------------------------------------------------------
    function iso(d) {
        return d.getFullYear() + '-' + String(d.getMonth() + 1).padStart(2, '0') + '-' + String(d.getDate()).padStart(2, '0');
    }
    function rangoPeriodo(clave) {
        var hoy = new Date();
        if (clave === 'mes') return [iso(new Date(hoy.getFullYear(), hoy.getMonth(), 1)), iso(new Date(hoy.getFullYear(), hoy.getMonth() + 1, 0))];
        if (clave === 'anio') return [hoy.getFullYear() + '-01-01', hoy.getFullYear() + '-12-31'];
        if (clave === '12m') return [iso(new Date(hoy.getFullYear(), hoy.getMonth() - 11, 1)), iso(hoy)];
        return ['', ''];
    }
    function periodoActual() {
        for (var i = 0; i < PERIODOS.length; i++) {
            var r = rangoPeriodo(PERIODOS[i]);
            if (r[0] === estado.desde && r[1] === estado.hasta) return PERIODOS[i];
        }
        return null;
    }
    function textoRango() {
        var p = periodoActual();
        if (p === 'todo') return 'todo el historial';
        if (p === 'mes') return M.etiquetaDimension('periodo', estado.desde.slice(0, 7));
        if (p === 'anio') return 'año ' + estado.desde.slice(0, 4);
        var f = function (t) { return M.etiquetaDimension('periodo', t); };
        if (estado.desde && estado.hasta) return 'del ' + f(estado.desde) + ' al ' + f(estado.hasta);
        if (estado.desde) return 'desde el ' + f(estado.desde);
        return 'hasta el ' + f(estado.hasta);
    }

    // ------------------------------------------------------------------
    // Avisos
    // ------------------------------------------------------------------
    function aviso(texto, tipo) {
        var nodo = el('an-aviso');
        nodo.hidden = !texto;
        nodo.textContent = texto || '';
        nodo.setAttribute('data-tipo', tipo || 'info');
    }

    // ------------------------------------------------------------------
    // Estado en la URL (CA-06.2, CA-08.3)
    // ------------------------------------------------------------------
    function escribirUrl() {
        var params = new URLSearchParams();
        params.set('conjunto', estado.conjunto.clave);
        params.set('desde', estado.desde);
        params.set('hasta', estado.hasta);
        history.replaceState(null, '', location.pathname + '?' + params.toString() + '#c=' + encodeURIComponent(JSON.stringify(estado.disp)));
    }
    function leerUrl() {
        var params = new URLSearchParams(location.search);
        var disp = null;
        var m = location.hash.match(/^#c=(.*)$/);
        if (m) { try { disp = JSON.parse(decodeURIComponent(m[1])); } catch (e) { disp = null; } }
        return {
            conjunto: params.get('conjunto'),
            tieneRango: params.has('desde') || params.has('hasta'),
            desde: params.get('desde') || '',
            hasta: params.get('hasta') || '',
            disp: disp && typeof disp === 'object' ? disp : null
        };
    }

    // ------------------------------------------------------------------
    // Menú de conjuntos
    // ------------------------------------------------------------------
    function ficha(campo, origen, extra, claseExtra) {
        var t = campo.tipo;
        var clases = 'an-ficha an-t-' + t + (claseExtra ? ' ' + claseExtra : '') + (origen === 'menu' && usado(campo.etiqueta) ? ' an-usada' : '');
        return '<span class="' + clases + '" draggable="true" data-campo="' + esc(campo.etiqueta) + '" data-tipo="' + t + '" data-origen="' + origen + '"'
            + (origen === 'menu' ? ' tabindex="0" role="button" title="Arrastra al centro o toca para agregar"' : '') + '>'
            + '<span class="an-icono" aria-hidden="true">' + ICONOS[t] + '</span>'
            + '<span class="an-ficha-texto">' + esc(campo.etiqueta) + '</span>' + (extra || '') + '</span>';
    }

    function pintarMenu() {
        var grupos = [];
        cfg.conjuntos.forEach(function (c) {
            var g = grupos.find(function (x) { return x.modulo === c.modulo; });
            if (!g) grupos.push(g = { modulo: c.modulo, conjuntos: [] });
            g.conjuntos.push(c);
        });
        var html = '<p class="an-menu-titulo">Datos</p>';
        grupos.forEach(function (g) {
            html += '<div class="an-modulo"><div class="an-modulo-titulo">' + esc(g.modulo) + '</div>';
            g.conjuntos.forEach(function (c) {
                var activo = c.clave === estado.conjunto.clave;
                html += '<button type="button" class="an-conjunto" data-conjunto="' + esc(c.clave) + '" aria-expanded="' + activo + '">'
                    + '<span>' + esc(c.nombre) + '</span><span class="an-flecha" aria-hidden="true">' + (activo ? '▾' : '▸') + '</span></button>';
                if (activo) {
                    var dims = c.campos.filter(function (x) { return M.esDimension(x.tipo); });
                    html += '<div class="an-campos" data-campos-de="' + esc(c.clave) + '">'
                        + '<p class="an-desc">' + esc(c.descripcion) + '</p>'
                        + '<div><h3>Agrupar por</h3><div class="an-fichas">' + dims.map(function (x) { return ficha(x, 'menu'); }).join('') + '</div></div>'
                        + '<div><h3>Medir</h3><div class="an-fichas">' + medidas().map(function (x) { return ficha(x, 'menu'); }).join('') + '</div></div>'
                        + '<p class="an-ayuda">Arrastra un campo al centro o tócalo para agregarlo.</p></div>';
                }
            });
            html += '</div>';
        });
        el('an-menu').innerHTML = html;
    }

    // ------------------------------------------------------------------
    // Zonas
    // ------------------------------------------------------------------
    var VACIAS = {
        filas: 'Suelta aquí cómo agrupar, por ejemplo Cliente.',
        columnas: 'Opcional. Por ejemplo Estado o Mes.',
        valores: 'Suelta un monto, días o N.º de …',
        filtros: 'Opcional. Suelta un campo para elegir valores.'
    };

    function valoresDe(etiqueta) {
        if (!estado.datos) return [];
        var i = estado.datos.encabezado.indexOf(etiqueta);
        if (i < 0) return [];
        var vistos = {};
        estado.datos.filas.forEach(function (f) { vistos[f[i] === null || f[i] === undefined ? '' : String(f[i])] = true; });
        var tipo = tipoDe(etiqueta);
        return Object.keys(vistos).sort(function (a, b) {
            return a.localeCompare(b, 'es', { numeric: true, sensitivity: 'base' });
        }).map(function (v) { return { valor: v, texto: M.etiquetaDimension(tipo, v) }; });
    }
    function marcados(etiqueta) {
        var todos = valoresDe(etiqueta).map(function (x) { return x.valor; });
        var d = estado.disp;
        if (d.solo[etiqueta]) return todos.filter(function (v) { return d.solo[etiqueta].indexOf(v) >= 0; });
        if (d.excluir[etiqueta]) return todos.filter(function (v) { return d.excluir[etiqueta].indexOf(v) < 0; });
        return todos;
    }

    function botonQuitar(e) {
        return '<button type="button" class="an-quitar" data-quitar="' + esc(e) + '" aria-label="Quitar ' + esc(e) + '">×</button>';
    }

    function fichaFiltro(etiqueta) {
        var todos = valoresDe(etiqueta);
        var elegidos = marcados(etiqueta);
        var tipo = tipoDe(etiqueta);
        var resumen = elegidos.length === todos.length ? 'todos'
            : elegidos.length === 1 ? M.etiquetaDimension(tipo, elegidos[0])
                : elegidos.length + ' de ' + todos.length;
        var abierto = estado.filtroAbierto === etiqueta;
        var extra = '<button type="button" class="an-filtro-boton" data-abrir-filtro="' + esc(etiqueta) + '" aria-expanded="' + abierto + '">' + esc(resumen) + ' ▾</button>'
            + botonQuitar(etiqueta);
        if (abierto) {
            extra += '<div class="an-emergente" data-emergente="' + esc(etiqueta) + '">'
                + '<div class="an-emergente-acciones"><button type="button" data-filtro-todos="' + esc(etiqueta) + '">Todos</button>'
                + '<button type="button" data-filtro-ninguno="' + esc(etiqueta) + '">Ninguno</button></div>'
                + '<div class="an-emergente-lista">' + todos.map(function (x) {
                    return '<label><input type="checkbox" data-filtro="' + esc(etiqueta) + '" value="' + esc(x.valor) + '"'
                        + (elegidos.indexOf(x.valor) >= 0 ? ' checked' : '') + '> ' + esc(x.texto) + '</label>';
                }).join('') + '</div></div>';
        }
        return ficha({ etiqueta: etiqueta, tipo: tipo }, 'filtros', extra, 'an-ficha-filtro');
    }

    function pintarZonas() {
        var d = estado.disp;
        ZONAS.forEach(function (z) {
            var html = '';
            if (z === 'filas' || z === 'columnas') {
                html = d[z].map(function (e) { return ficha({ etiqueta: e, tipo: tipoDe(e) }, z, botonQuitar(e)); }).join('');
            } else if (z === 'valores') {
                html = d.valores.map(function (v, i) {
                    var tipo = tipoDe(v[0]);
                    var sel = tipo === 'conteo' ? '' : '<select class="an-calculo" data-calculo="' + i + '" aria-label="Cálculo de ' + esc(v[0]) + '">'
                        + ['suma', 'promedio', 'max', 'min'].map(function (c) {
                            return '<option value="' + c + '"' + (c === v[1] ? ' selected' : '') + '>' + M.nombreCalculo[c] + '</option>';
                        }).join('') + '</select>';
                    return ficha({ etiqueta: v[0], tipo: tipo }, 'valores', sel + botonQuitar(v[0]));
                }).join('');
            } else {
                var filtrados = Object.keys(d.solo).concat(Object.keys(d.excluir).filter(function (e) { return !(e in d.solo); }));
                html = filtrados.map(fichaFiltro).join('');
            }
            var cuerpo = document.querySelector('[data-zona="' + z + '"] .an-zona-cuerpo');
            cuerpo.innerHTML = html || '<span class="an-zona-vacia">' + VACIAS[z] + '</span>';
        });
    }

    function quitarCampo(etiqueta) {
        var d = estado.disp;
        d.filas = d.filas.filter(function (e) { return e !== etiqueta; });
        d.columnas = d.columnas.filter(function (e) { return e !== etiqueta; });
        d.valores = d.valores.filter(function (v) { return v[0] !== etiqueta; });
        delete d.solo[etiqueta];
        delete d.excluir[etiqueta];
        if (estado.filtroAbierto === etiqueta) estado.filtroAbierto = null;
    }

    /** Pone un campo en una zona. Devuelve false si no tiene sentido ahí. */
    function soltar(etiqueta, zona) {
        var tipo = tipoDe(etiqueta);
        if (!tipo || ZONAS.indexOf(zona) < 0) return false;
        var esDim = M.esDimension(tipo);
        if (!esDim && zona === 'filtros') {
            aviso('"' + etiqueta + '" es un número: va en Valores. Para filtrar usa un campo de "Agrupar por".', 'info');
            return false;
        }
        if (!esDim) zona = 'valores';
        if (esDim && zona === 'valores') {
            aviso('"' + etiqueta + '" sirve para agrupar. En Valores va un monto, días o ' + estado.conjunto.conteo + '.', 'info');
            return false;
        }
        var d = estado.disp;
        var previo = d.valores.find(function (v) { return v[0] === etiqueta; });
        if (zona === 'valores' && !previo && d.valores.length >= MAX_VALORES) {
            aviso('Se pueden medir hasta ' + MAX_VALORES + ' valores a la vez.', 'info');
            return false;
        }
        aviso('');
        var solo = d.solo[etiqueta];
        var excluir = d.excluir[etiqueta];
        quitarCampo(etiqueta);
        if (zona === 'valores') {
            d.valores.push([etiqueta, previo ? previo[1] : M.calculoPorDefecto(tipo)]);
        } else if (zona === 'filtros') {
            if (solo) d.solo[etiqueta] = solo;
            else d.excluir[etiqueta] = excluir || [];
            estado.filtroAbierto = etiqueta;
        } else {
            d[zona].push(etiqueta);
        }
        return true;
    }

    /** Tocar un campo del menú: lo agrega donde más sentido tiene. */
    function agregarConToque(etiqueta) {
        if (usado(etiqueta)) return;
        var d = estado.disp;
        var zona = !M.esDimension(tipoDe(etiqueta)) ? 'valores' : (!d.filas.length ? 'filas' : (!d.columnas.length ? 'columnas' : 'filas'));
        if (soltar(etiqueta, zona)) cambio();
    }

    // ------------------------------------------------------------------
    // Resultado
    // ------------------------------------------------------------------
    function nombreValor(v) { return M.nombreValor(v); }
    function etiquetaClave(lista, clave) {
        return clave.map(function (x, i) { return M.etiquetaDimension(tipoDe(lista[i]), x); }).join(' · ');
    }
    function fmt(v, valor, corto) { return M.formatear(tipoDe(v[0]), v[1], valor, corto); }

    function frase() {
        var d = estado.disp;
        var t = d.valores.map(nombreValor).join(' y ');
        if (d.filas.length) t += ' por ' + d.filas.join(' y ');
        if (d.columnas.length) t += (d.filas.length ? ', separado por ' : ' por ') + d.columnas.join(' y ');
        return t;
    }

    function pintarResultado() {
        var d = estado.disp;
        var caja = el('an-resultado');
        destruirGrafico();
        estado.resultado = null;
        if (!estado.datos) { caja.innerHTML = '<p class="an-nota">Cargando datos…</p>'; return; }
        if (!d.valores.length) {
            caja.innerHTML = '<p class="an-frase">Falta qué medir</p><p class="an-nota">Arrastra a <b>Valores</b> un monto, días o ' + esc(estado.conjunto.conteo) + '.</p>';
            return;
        }
        var r = M.calcular(estado.datos, d, campos());
        estado.resultado = r;
        var kpis = d.valores.map(function (v, i) {
            return '<div class="an-kpi" data-kpi="' + esc(v[0]) + '"><div class="an-kpi-nombre">' + esc(nombreValor(v)) + '</div>'
                + '<div class="an-kpi-valor">' + esc(fmt(v, r.celda(null, null, i))) + '</div>'
                + '<div class="an-kpi-nota">' + (M.esAditivo(v[1]) ? 'total' : 'en todo el periodo') + '</div></div>';
        }).join('');
        if (!d.valores.some(function (v) { return v[1] === 'conteo'; })) {
            kpis += '<div class="an-kpi" data-kpi="registros"><div class="an-kpi-nombre">' + esc(estado.conjunto.conteo) + '</div>'
                + '<div class="an-kpi-valor">' + M.formatear('conteo', 'conteo', r.registros) + '</div><div class="an-kpi-nota">incluidos</div></div>';
        }
        var html = '<p class="an-frase" data-frase>' + esc(frase()) + ' <span>· ' + esc(textoRango()) + '</span></p><div class="an-kpis">' + kpis + '</div>';
        if (!r.registros) {
            caja.innerHTML = html + '<p class="an-nota">No hay registros con estas fechas y filtros. Prueba con “Todo” arriba.</p>';
            return;
        }
        if (!d.filas.length && !d.columnas.length) {
            caja.innerHTML = html + '<p class="an-nota">Arrastra a <b>Filas</b> cómo quieres agrupar, por ejemplo por cliente o por mes.</p>';
            return;
        }
        if (d.vista === 'tabla') {
            caja.innerHTML = html + tablaHtml(r);
            return;
        }
        caja.innerHTML = html + '<div class="an-grafico" data-grafico data-tipo="' + d.vista + '"><p class="an-nota" data-aviso-grafico hidden></p>'
            + '<div class="an-grafico-lienzo"><canvas role="img" aria-label="' + esc(frase()) + '"></canvas></div></div>';
        pintarGrafico(r);
    }

    function tablaHtml(r) {
        var d = estado.disp;
        var conCols = d.columnas.length > 0;
        var cols = conCols ? r.columnas : [];
        var nV = d.valores.length;
        var filasClave = d.filas.length ? r.filas : [[]];
        var kf = function (f) { return d.filas.length ? f : null; };
        // Barra de fondo para comparar de un vistazo, relativa al mayor de cada valor.
        var maximos = d.valores.map(function (v, i) {
            var m = 0;
            filasClave.forEach(function (f) {
                (conCols ? cols : [null]).forEach(function (c) { m = Math.max(m, r.celda(kf(f), c, i) || 0); });
            });
            return m;
        });
        var celda = function (valor, v, i, total) {
            if (valor === null || valor === 0) {
                return '<td class="an-num an-cero' + (total ? ' an-total-col' : '') + '"><span>' + (valor === 0 ? esc(fmt(v, 0)) : '—') + '</span></td>';
            }
            var barra = !total && maximos[i] > 0 && valor > 0 ? '<i style="width:' + Math.max(2, Math.round(valor / maximos[i] * 100)) + '%"></i>' : '';
            return '<td class="an-num' + (total ? ' an-total-col' : '') + '">' + barra + '<span>' + esc(fmt(v, valor)) + '</span></td>';
        };
        var cab = '';
        if (conCols) {
            cab += '<tr class="an-grupo"><th>' + esc(d.columnas.join(' · ')) + '</th>'
                + cols.map(function (c) { return '<th class="an-num" colspan="' + nV + '">' + esc(etiquetaClave(d.columnas, c)) + '</th>'; }).join('')
                + '<th class="an-num" colspan="' + nV + '">Total</th></tr>';
        }
        var encabezadoValor = function (v) { return '<th class="an-num">' + esc(nV > 1 || !conCols ? nombreValor(v) : M.nombreCalculo[v[1]]) + '</th>'; };
        cab += '<tr><th>' + esc(d.filas.join(' · ')) + '</th>' + (conCols ? cols.concat([null]) : [null]).map(function () {
            return d.valores.map(encabezadoValor).join('');
        }).join('') + '</tr>';
        var cuerpo = filasClave.map(function (f) {
            var html = '<tr><td class="an-fila">' + esc(d.filas.length ? etiquetaClave(d.filas, f) : 'Total') + '</td>';
            cols.forEach(function (c) { d.valores.forEach(function (v, i) { html += celda(r.celda(kf(f), c, i), v, i, false); }); });
            d.valores.forEach(function (v, i) { html += celda(r.celda(kf(f), null, i), v, i, conCols); });
            return html + '</tr>';
        }).join('');
        if (d.filas.length) {
            cuerpo += '<tr class="an-total"><td>Total</td>';
            cols.forEach(function (c) { d.valores.forEach(function (v, i) { cuerpo += '<td class="an-num">' + esc(fmt(v, r.celda(null, c, i))) + '</td>'; }); });
            d.valores.forEach(function (v, i) {
                cuerpo += '<td class="an-num"' + (i === 0 ? ' data-total-general' : '') + '>' + esc(fmt(v, r.celda(null, null, i))) + '</td>';
            });
            cuerpo += '</tr>';
        }
        return '<div class="an-tabla-caja"><table class="an-tabla"><thead>' + cab + '</thead><tbody>' + cuerpo + '</tbody></table></div>';
    }

    // ------------------------------------------------------------------
    // Gráficos (HU-LIMS-07)
    // ------------------------------------------------------------------
    function destruirGrafico() {
        if (estado.grafico) { estado.grafico.destroy(); estado.grafico = null; }
    }

    function pintarGrafico(r) {
        var d = estado.disp;
        var v = d.valores[0];
        var aditivo = M.esAditivo(v[1]);
        var avisos = [];
        if (d.valores.length > 1) avisos.push('El gráfico muestra solo "' + nombreValor(v) + '"; la tabla tiene todos los valores.');
        var contenedor = document.querySelector('[data-grafico]');
        var lienzo = contenedor.querySelector('canvas');
        var porTiempo = d.filas.some(function (e) { return tipoDe(e) === 'periodo'; });
        var kf = function (f) { return d.filas.length ? f : null; };
        var filas = d.filas.length ? r.filas.slice() : [[]];
        var nombreFila = function (f) { return d.filas.length ? etiquetaClave(d.filas, f) : 'Total'; };

        if (d.vista === 'dona') {
            if (!aditivo) {
                contenedor.innerHTML = '<p class="an-nota" data-aviso-grafico>Un ' + M.nombreCalculo[v[1]].toLowerCase()
                    + ' no se reparte en porciones. Para la dona usa Suma o ' + esc(estado.conjunto.conteo) + '.</p>';
                return;
            }
            if (d.columnas.length) avisos.push('La dona usa el total por fila; las columnas no se dibujan.');
            var porValor = filas.map(function (f) { return { f: f, t: r.celda(kf(f), null, 0) || 0 }; })
                .filter(function (x) { return x.t > 0; }).sort(function (a, b) { return b.t - a.t; });
            var trozos = porValor.slice(0, MAX_PORCIONES);
            var resto = porValor.slice(MAX_PORCIONES).reduce(function (s, x) { return s + x.t; }, 0);
            var etiquetasDona = trozos.map(function (x) { return nombreFila(x.f); });
            var datosDona = trozos.map(function (x) { return x.t; });
            var colores = trozos.map(function (x, i) { return SERIES[i]; });
            if (resto > 0) { etiquetasDona.push('Otros'); datosDona.push(resto); colores.push(GRIS_OTROS); }
            dibujar(lienzo, contenedor, avisos, {
                type: 'doughnut',
                data: { labels: etiquetasDona, datasets: [{ data: datosDona, backgroundColor: colores, borderColor: '#fff', borderWidth: 2 }] },
                options: opciones(v, true, { cutout: '58%', plugins: { legend: { position: 'right' } } })
            });
            return;
        }

        // CA-07.3: como máximo 20 categorías; el resto va en "Otros" si se puede sumar.
        var otrasFilas = [];
        if (filas.length > MAX_CATEGORIAS) {
            var orden = filas.map(function (f, i) { return { i: i, t: r.celda(kf(f), null, 0) || 0 }; }).sort(function (a, b) { return b.t - a.t; });
            var elegidos = orden.slice(0, MAX_CATEGORIAS).map(function (x) { return x.i; }).sort(function (a, b) { return a - b; });
            otrasFilas = filas.filter(function (f, i) { return elegidos.indexOf(i) < 0; });
            filas = elegidos.map(function (i) { return filas[i]; });
            avisos.push('Se muestran las ' + MAX_CATEGORIAS + ' filas mayores de ' + r.filas.length + (aditivo ? '; el resto va en "Otros".' : '; la tabla tiene todas.'));
        }
        var series;
        if (d.columnas.length) {
            var cols = r.columnas;
            if (cols.length > SERIES.length) {
                var porTotal = cols.map(function (c) { return { c: c, t: r.celda(null, c, 0) || 0 }; }).sort(function (a, b) { return b.t - a.t; });
                var principales = porTotal.slice(0, SERIES.length - 1).map(function (x) { return x.c; });
                series = principales.map(function (c) { return { nombre: etiquetaClave(d.columnas, c), claves: [c] }; });
                if (aditivo) series.push({ nombre: 'Otros', claves: porTotal.slice(SERIES.length - 1).map(function (x) { return x.c; }), otros: true });
                avisos.push('Hay ' + cols.length + ' columnas: se dibujan las ' + principales.length + ' mayores' + (aditivo ? ' y "Otros".' : '.'));
            } else {
                series = cols.map(function (c) { return { nombre: etiquetaClave(d.columnas, c), claves: [c] }; });
            }
        } else {
            series = [{ nombre: nombreValor(v), claves: [null] }];
        }
        var valorEn = function (listaFilas, claves) {
            var suma = 0;
            var alguno = false;
            listaFilas.forEach(function (f) {
                claves.forEach(function (c) {
                    var x = r.celda(kf(f), c, 0);
                    if (x !== null) { suma += x; alguno = true; }
                });
            });
            return alguno ? suma : null;
        };
        var etiquetas = filas.map(nombreFila);
        var conOtros = otrasFilas.length && aditivo;
        if (conOtros) etiquetas.push('Otros');
        var lineas = d.vista === 'lineas';
        var apilar = !lineas && aditivo && series.length > 1;
        var datasets = series.map(function (s, i) {
            var color = s.otros ? GRIS_OTROS : SERIES[i];
            var datos = filas.map(function (f) { return valorEn([f], s.claves); });
            if (conOtros) datos.push(valorEn(otrasFilas, s.claves));
            return lineas
                ? { label: s.nombre, data: datos, borderColor: color, backgroundColor: color, borderWidth: 2, pointRadius: 3, tension: 0, spanGaps: true }
                : { label: s.nombre, data: datos, backgroundColor: color, borderColor: '#fff', borderWidth: apilar ? { top: 2 } : 0, borderRadius: 3, maxBarThickness: 46 };
        });
        var horizontal = !lineas && !porTiempo;
        var entero = v[1] === 'conteo' || (aditivo && tipoDe(v[0]) === 'cantidad');
        var ejeValor = {
            stacked: apilar, beginAtZero: true, grid: { color: '#eef2f6' },
            ticks: { precision: entero ? 0 : undefined, callback: function (x) { return fmt(v, x, true); } }
        };
        var ejeCategoria = { stacked: apilar, grid: { display: false }, ticks: { autoSkip: !horizontal } };
        if (horizontal) {
            var alto = 56 + etiquetas.length * (apilar || series.length === 1 ? 30 : 14 * series.length + 10);
            contenedor.querySelector('.an-grafico-lienzo').style.height = Math.max(240, Math.min(760, alto)) + 'px';
        }
        dibujar(lienzo, contenedor, avisos, {
            type: lineas ? 'line' : 'bar',
            data: { labels: etiquetas, datasets: datasets },
            options: opciones(v, false, {
                indexAxis: horizontal ? 'y' : 'x',
                scales: horizontal ? { x: ejeValor, y: ejeCategoria } : { x: ejeCategoria, y: ejeValor },
                plugins: { legend: { display: series.length > 1, position: 'bottom' } }
            })
        });
    }

    function opciones(v, dona, extra) {
        var base = {
            responsive: true, maintainAspectRatio: false, animation: false,
            plugins: {
                legend: { labels: { boxWidth: 12, boxHeight: 12, color: '#334155' } },
                tooltip: {
                    callbacks: {
                        label: function (ctx) {
                            var x = dona ? ctx.parsed : (ctx.chart.options.indexAxis === 'y' ? ctx.parsed.x : ctx.parsed.y);
                            var texto = (dona ? ctx.label : ctx.dataset.label) + ': ' + fmt(v, x);
                            if (dona) {
                                var total = ctx.dataset.data.reduce(function (s, n) { return s + n; }, 0);
                                texto += ' (' + Math.round(x / total * 100) + ' %)';
                            }
                            return texto;
                        }
                    }
                }
            }
        };
        Object.keys(extra).forEach(function (k) {
            if (k !== 'plugins') { base[k] = extra[k]; return; }
            Object.keys(extra.plugins).forEach(function (p) { base.plugins[p] = Object.assign(base.plugins[p] || {}, extra.plugins[p]); });
        });
        return base;
    }

    function dibujar(lienzo, contenedor, avisos, config) {
        var nota = contenedor.querySelector('[data-aviso-grafico]');
        if (nota && avisos.length) { nota.textContent = avisos.join(' '); nota.hidden = false; }
        if (!window.Chart) return;
        estado.grafico = new window.Chart(lienzo, config);
        lienzo.setAttribute('data-listo', '');
    }

    // ------------------------------------------------------------------
    // Pintar todo tras un cambio
    // ------------------------------------------------------------------
    function marcarBotones() {
        var p = periodoActual();
        var marcar = function (selector, atributo, valor) {
            document.querySelectorAll(selector).forEach(function (b) { b.setAttribute('aria-pressed', String(b.getAttribute(atributo) === valor)); });
        };
        marcar('[data-periodo]', 'data-periodo', p);
        marcar('[data-vista]', 'data-vista', estado.disp.vista);
        marcar('[data-orden]', 'data-orden', estado.disp.orden);
        marcar('[data-vista-rapida]', 'data-vista-rapida', estado.pregunta);
    }

    function cambio(conservarPregunta) {
        if (!conservarPregunta) estado.pregunta = null;
        pintarMenu();
        pintarZonas();
        pintarResultado();
        marcarBotones();
        escribirUrl();
        if (estado.datos) el('an-estado').textContent = estado.datos.filas.length + ' registros en el rango · ' + textoRango();
    }

    function aplicarDisposicion(disp, nombrePregunta) {
        estado.disp = M.disposicionValida(disp, campos(), estado.conjunto.conteo);
        estado.filtroAbierto = null;
        estado.pregunta = nombrePregunta || null;
        aviso('');
        cambio(true);
    }

    // ------------------------------------------------------------------
    // Datos
    // ------------------------------------------------------------------
    function urlDatos() {
        var base = cfg.urls.datos.replace('__conjunto__', encodeURIComponent(estado.conjunto.clave));
        return base + '?' + new URLSearchParams({ desde: estado.desde, hasta: estado.hasta }).toString();
    }

    function cargar() {
        aviso('');
        el('an-desde').value = estado.desde;
        el('an-hasta').value = estado.hasta;
        if (estado.desde && estado.hasta && estado.desde > estado.hasta) {
            aviso('La fecha "desde" es posterior a "hasta". Corrige el rango.', 'error');   // CA-06.6
            return Promise.resolve();
        }
        el('an-estado').textContent = 'Cargando…';
        var clave = estado.conjunto.clave;
        return fetch(urlDatos(), { headers: { 'Accept': 'application/json' }, credentials: 'same-origin' })
            .then(function (r) { return r.json().then(function (j) { return { ok: r.ok, json: j }; }); })
            .then(function (res) {
                if (clave !== estado.conjunto.clave) return;   // llegó tarde: ya se eligió otro conjunto
                if (!res.ok) {
                    aviso(res.json.error || 'No se pudieron cargar los datos.', 'error');
                    el('an-estado').textContent = '';
                    return;
                }
                estado.datos = res.json;
                cambio(true);
                if (!res.json.filas.length) aviso('Sin datos para estos filtros. Cambia el rango de fechas o el conjunto.', 'info');
            })
            .catch(function () {
                aviso('No se pudieron cargar los datos. Revisa tu conexión e inténtalo de nuevo.', 'error');
                el('an-estado').textContent = '';
            });
    }

    // ------------------------------------------------------------------
    // Exportar (HU-LIMS-09)
    // ------------------------------------------------------------------
    function descripcionFiltros() {
        var d = estado.disp;
        var partes = [];
        Object.keys(d.solo).forEach(function (e) { partes.push(e + ': solo ' + d.solo[e].join(', ')); });
        Object.keys(d.excluir).forEach(function (e) { if (d.excluir[e].length) partes.push(e + ': sin ' + d.excluir[e].join(', ')); });
        return partes.length ? partes.join(' | ') : 'Ninguno';
    }
    function cabeceraExcel(titulo) {
        var d = estado.disp;
        return [
            [titulo],
            ['Conjunto', estado.conjunto.nombre],
            ['Rango', textoRango()],
            ['Filas', d.filas.join(', ') || '—', 'Columnas', d.columnas.join(', ') || '—'],
            ['Valores', d.valores.map(nombreValor).join(', ') || '—'],
            ['Filtros', descripcionFiltros()],
            ['Generado', new Date().toLocaleString('es-PE')],
            []
        ];
    }
    /** formatos: por columna, el formato de número de Excel (o null). */
    function descargar(aoa, nombreHoja, archivo, filaInicio, formatos) {
        var XLSX = window.XLSX;
        var hoja = XLSX.utils.aoa_to_sheet(aoa);
        var rango = XLSX.utils.decode_range(hoja['!ref']);
        for (var r = filaInicio; r <= rango.e.r; r++) {
            for (var c = 0; c <= rango.e.c; c++) {
                var celda = hoja[XLSX.utils.encode_cell({ r: r, c: c })];
                if (celda && celda.t === 'n' && formatos[c]) celda.z = formatos[c];
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
        var r = estado.resultado;
        var d = estado.disp;
        if (!r) { aviso('Arma primero una tabla con al menos un valor.', 'info'); return; }
        var cols = d.columnas.length ? r.columnas.concat([null]) : [null];
        var kf = function (f) { return d.filas.length ? f : null; };
        var aoa = cabeceraExcel('Análisis VICAF · Tabla');
        var inicio = aoa.length;
        var formatos = [null];
        var encabezado = [d.filas.join(' · ')];
        cols.forEach(function (c) {
            d.valores.forEach(function (v) {
                var partes = [];
                if (d.columnas.length) partes.push(c === null ? 'Total' : etiquetaClave(d.columnas, c));
                if (d.valores.length > 1 || !d.columnas.length) partes.push(nombreValor(v));
                encabezado.push(partes.join(' · '));
                formatos.push(M.formatoExcel(tipoDe(v[0]), v[1]));
            });
        });
        aoa.push(encabezado);
        (d.filas.length ? r.filas : [[]]).forEach(function (f) {
            var fila = [d.filas.length ? etiquetaClave(d.filas, f) : 'Total'];
            cols.forEach(function (c) { d.valores.forEach(function (v, i) { fila.push(r.celda(kf(f), c, i)); }); });
            aoa.push(fila);
        });
        if (d.filas.length) {
            var total = ['Total'];
            cols.forEach(function (c) { d.valores.forEach(function (v, i) { total.push(r.celda(null, c, i)); }); });
            aoa.push(total);
        }
        descargar(aoa, 'Tabla', nombreArchivo('tabla'), inicio + 1, formatos);
    }

    function exportarDatos() {
        if (!estado.datos) return;
        var d = estado.disp;
        var encabezado = estado.datos.encabezado;
        var indice = {};
        encabezado.forEach(function (e, i) { indice[e] = i; });
        var pasa = function (f) {
            return Object.keys(d.solo).every(function (e) { return indice[e] === undefined || d.solo[e].indexOf(String(f[indice[e]])) >= 0; })
                && Object.keys(d.excluir).every(function (e) { return indice[e] === undefined || d.excluir[e].indexOf(String(f[indice[e]])) < 0; });
        };
        var aoa = cabeceraExcel('Análisis VICAF · Datos');
        var inicio = aoa.length;
        aoa.push(encabezado);
        estado.datos.filas.filter(pasa).forEach(function (f) { aoa.push(f); });
        var formatos = encabezado.map(function (e) {
            var t = tipoDe(e);
            return t && !M.esDimension(t) ? M.formatoExcel(t, 'suma') : null;
        });
        descargar(aoa, 'Datos', nombreArchivo('datos'), inicio + 1, formatos);
    }

    // ------------------------------------------------------------------
    // Preguntas frecuentes y vistas guardadas (HU-LIMS-08)
    // ------------------------------------------------------------------
    function pintarPreguntas() {
        el('an-vistas-rapidas').innerHTML = (estado.conjunto.vistas || []).map(function (v) {
            return '<button type="button" class="an-pregunta" data-vista-rapida="' + esc(v.nombre) + '">' + esc(v.nombre) + '</button>';
        }).join('') || '<span class="an-nota">—</span>';
    }

    function csrf() {
        var input = document.querySelector('#an-csrf input[name="csrfmiddlewaretoken"]');
        return input ? input.value : '';
    }
    function pintarMisVistas() {
        el('an-mis-vistas').innerHTML = '<option value="">—</option>' + estado.misVistas
            .filter(function (v) { return v.conjunto === estado.conjunto.clave; })
            .map(function (v) { return '<option value="' + v.id + '">' + esc(v.nombre) + '</option>'; }).join('');
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
        if (!nombre) { aviso('Escribe un nombre para la vista.', 'error'); el('an-nombre-vista').focus(); return; }
        fetch(cfg.urls.vistas, {
            method: 'POST', credentials: 'same-origin',
            headers: { 'Content-Type': 'application/json', 'X-CSRFToken': csrf() },
            body: JSON.stringify({ nombre: nombre, conjunto: estado.conjunto.clave, configuracion: estado.disp })
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
        var vista = estado.misVistas.find(function (v) { return String(v.id) === id; });
        if (!vista || !window.confirm('¿Eliminar la vista "' + vista.nombre + '"?')) return;
        fetch(cfg.urls.eliminar.replace('/0/', '/' + encodeURIComponent(id) + '/'), {
            method: 'POST', credentials: 'same-origin', headers: { 'X-CSRFToken': csrf() }
        }).then(function () { aviso('Vista eliminada.', 'info'); return cargarMisVistas(); });
    }

    // ------------------------------------------------------------------
    // Conjunto activo
    // ------------------------------------------------------------------
    function elegirConjunto(clave, usarRangoDefecto) {
        estado.conjunto = cfg.conjuntos.find(function (c) { return c.clave === clave; }) || cfg.conjuntos[0];
        estado.datos = null;
        if (usarRangoDefecto) {
            var rango = rangoPeriodo(estado.conjunto.rango_defecto);
            estado.desde = rango[0];
            estado.hasta = rango[1];
        }
        pintarPreguntas();
        pintarMisVistas();
    }

    // ------------------------------------------------------------------
    // Eventos
    // ------------------------------------------------------------------
    function enlazarArrastre() {
        var arrastrado = null;
        var raiz = document.querySelector('.analisis');
        raiz.addEventListener('dragstart', function (e) {
            var f = e.target.closest && e.target.closest('.an-ficha[data-campo]');
            if (!f) return;
            arrastrado = f.getAttribute('data-campo');
            e.dataTransfer.setData('text/plain', arrastrado);
            e.dataTransfer.effectAllowed = 'move';
            f.classList.add('an-arrastrando');
        });
        raiz.addEventListener('dragend', function (e) {
            var f = e.target.closest && e.target.closest('.an-ficha');
            if (f) f.classList.remove('an-arrastrando');
            document.querySelectorAll('.an-zona.an-encima').forEach(function (z) { z.classList.remove('an-encima'); });
        });
        var recibido = function (e) {
            var campo = e.dataTransfer.getData('text/plain') || arrastrado;
            arrastrado = null;
            return campo;
        };
        document.querySelectorAll('.an-zona').forEach(function (zona) {
            zona.addEventListener('dragover', function (e) { e.preventDefault(); e.dataTransfer.dropEffect = 'move'; zona.classList.add('an-encima'); });
            zona.addEventListener('dragleave', function (e) { if (!zona.contains(e.relatedTarget)) zona.classList.remove('an-encima'); });
            zona.addEventListener('drop', function (e) {
                e.preventDefault();
                zona.classList.remove('an-encima');
                var campo = recibido(e);
                if (campo && soltar(campo, zona.getAttribute('data-zona'))) cambio();
            });
        });
        // Soltar en el menú quita el campo de la tabla.
        var menu = el('an-menu');
        menu.addEventListener('dragover', function (e) { e.preventDefault(); });
        menu.addEventListener('drop', function (e) {
            e.preventDefault();
            var campo = recibido(e);
            if (campo && usado(campo)) { quitarCampo(campo); cambio(); }
        });
    }

    function preguntaPorNombre(nombre) {
        return (estado.conjunto.vistas || []).find(function (x) { return x.nombre === nombre; });
    }

    function enlazarClics() {
        var raiz = document.querySelector('.analisis');
        raiz.addEventListener('click', function (e) {
            var t = e.target;
            var b;
            if ((b = t.closest('[data-conjunto]'))) {
                var clave = b.getAttribute('data-conjunto');
                if (clave === estado.conjunto.clave) return;
                // CA-06.5: se conserva lo compatible de la disposición.
                var anterior = estado.disp;
                elegirConjunto(clave, false);
                estado.disp = M.disposicionValida(anterior, campos(), estado.conjunto.conteo);
                if (!estado.disp.valores.length) estado.disp.valores = [[estado.conjunto.conteo, 'conteo']];
                estado.filtroAbierto = null;
                cambio();
                cargar();
                return;
            }
            if ((b = t.closest('[data-quitar]'))) { quitarCampo(b.getAttribute('data-quitar')); cambio(); return; }
            if ((b = t.closest('[data-abrir-filtro]'))) {
                var nombre = b.getAttribute('data-abrir-filtro');
                estado.filtroAbierto = estado.filtroAbierto === nombre ? null : nombre;
                pintarZonas();
                return;
            }
            if ((b = t.closest('[data-filtro-todos], [data-filtro-ninguno]'))) {
                var campo = b.getAttribute('data-filtro-todos') || b.getAttribute('data-filtro-ninguno');
                delete estado.disp.solo[campo];
                estado.disp.excluir[campo] = b.hasAttribute('data-filtro-todos') ? [] : valoresDe(campo).map(function (x) { return x.valor; });
                estado.filtroAbierto = campo;
                cambio();
                return;
            }
            if (t.closest('.an-emergente')) return;
            if (estado.filtroAbierto && !t.closest('[data-zona="filtros"]')) { estado.filtroAbierto = null; pintarZonas(); }
            if ((b = t.closest('.an-ficha[data-origen="menu"]'))) { agregarConToque(b.getAttribute('data-campo')); return; }
            if ((b = t.closest('[data-vista-rapida]'))) {
                var p = preguntaPorNombre(b.getAttribute('data-vista-rapida'));
                if (p) aplicarDisposicion(p, p.nombre);
                return;
            }
            if ((b = t.closest('[data-vista]'))) { estado.disp.vista = b.getAttribute('data-vista'); cambio(true); return; }
            if ((b = t.closest('[data-orden]'))) { estado.disp.orden = b.getAttribute('data-orden'); cambio(true); return; }
            if ((b = t.closest('[data-periodo]'))) {
                var rango = rangoPeriodo(b.getAttribute('data-periodo'));
                estado.desde = rango[0];
                estado.hasta = rango[1];
                cargar();
            }
        });
        document.addEventListener('keydown', function (e) {
            var f = e.target.closest && e.target.closest('.an-ficha[data-origen="menu"]');
            if (f && (e.key === 'Enter' || e.key === ' ')) { e.preventDefault(); agregarConToque(f.getAttribute('data-campo')); }
            if (e.key === 'Escape' && estado.filtroAbierto) { estado.filtroAbierto = null; pintarZonas(); }
        });
        raiz.addEventListener('change', function (e) {
            var t = e.target;
            if (t.matches('select[data-calculo]')) {
                estado.disp.valores[Number(t.getAttribute('data-calculo'))][1] = t.value;
                cambio();
            } else if (t.matches('input[data-filtro]')) {
                var campo = t.getAttribute('data-filtro');
                var elegidos = Array.prototype.map.call(
                    raiz.querySelectorAll('input[data-filtro]:checked'), function (x) { return x; })
                    .filter(function (x) { return x.getAttribute('data-filtro') === campo; })
                    .map(function (x) { return x.value; });
                if (campo in estado.disp.solo) {
                    estado.disp.solo[campo] = elegidos;
                } else {
                    estado.disp.excluir[campo] = valoresDe(campo).map(function (x) { return x.valor; })
                        .filter(function (v) { return elegidos.indexOf(v) < 0; });
                }
                estado.filtroAbierto = campo;
                cambio();
            }
        });
    }

    function iniciar() {
        if (!cfg.conjuntos.length || !M) return;
        var url = leerUrl();
        if (url.tieneRango) { estado.desde = url.desde; estado.hasta = url.hasta; }
        elegirConjunto(url.conjunto, !url.tieneRango);
        var primera = (estado.conjunto.vistas || [])[0];
        if (url.disp) {
            estado.disp = M.disposicionValida(url.disp, campos(), estado.conjunto.conteo);
        } else if (primera) {
            estado.disp = M.disposicionValida(primera, campos(), estado.conjunto.conteo);
            estado.pregunta = primera.nombre;
        } else {
            estado.disp = M.disposicionValida({ valores: [[estado.conjunto.conteo, 'conteo']] }, campos(), estado.conjunto.conteo);
        }
        cambio(true);

        enlazarArrastre();
        enlazarClics();
        el('an-aplicar').addEventListener('click', function () {
            estado.desde = el('an-desde').value;
            estado.hasta = el('an-hasta').value;
            cargar();
        });
        el('an-exportar').addEventListener('click', exportarTabla);
        el('an-exportar-datos').addEventListener('click', exportarDatos);
        el('an-guardar-vista').addEventListener('click', guardarVista);
        el('an-eliminar-vista').addEventListener('click', eliminarVista);
        el('an-mis-vistas').addEventListener('change', function () {
            var id = this.value;
            el('an-eliminar-vista').disabled = !id;
            var vista = estado.misVistas.find(function (v) { return String(v.id) === id; });
            if (vista) aplicarDisposicion(vista.configuracion);
        });
        el('an-copiar-enlace').addEventListener('click', function () {
            var hecho = function () { aviso('Enlace copiado: abre esta misma tabla con este rango.', 'info'); };
            var manual = function () { window.prompt('Copia el enlace:', location.href); };
            if (navigator.clipboard) navigator.clipboard.writeText(location.href).then(hecho, manual);
            else manual();
        });

        cargarMisVistas();
        cargar();
    }

    if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', iniciar);
    else iniciar();
})();
