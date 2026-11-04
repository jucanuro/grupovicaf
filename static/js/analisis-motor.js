/* analisis-motor.js — cálculo y formato de la pantalla Análisis (VCF-LIMS,
 * HU-LIMS-06 a 10). Funciones puras, sin DOM: el navegador las usa como
 * window.AnalisisMotor y las pruebas de Node con require().
 *
 * Una "disposición" describe la tabla que armó el usuario:
 *   { filas: [campo], columnas: [campo], valores: [[campo, cálculo]],
 *     solo: {campo: [valores]}, excluir: {campo: [valores]},
 *     vista: 'tabla'|'barras'|'lineas'|'dona', orden: 'valor'|'nombre' }
 * El campo de conteo ("N.º de cotizaciones") no existe en los datos: cuenta filas.
 */
(function (raiz, fabrica) {
    'use strict';
    var motor = fabrica();
    if (typeof module === 'object' && module.exports) module.exports = motor;
    else raiz.AnalisisMotor = motor;
})(typeof self !== 'undefined' ? self : this, function () {
    'use strict';

    var DIMENSIONES = ['texto', 'periodo'];
    var CALCULOS = ['suma', 'promedio', 'max', 'min'];
    var NOMBRE_CALCULO = { conteo: 'Conteo', suma: 'Suma', promedio: 'Promedio', max: 'Máximo', min: 'Mínimo' };
    var VISTAS = ['tabla', 'barras', 'lineas', 'dona'];
    var MESES = ['ene', 'feb', 'mar', 'abr', 'may', 'jun', 'jul', 'ago', 'set', 'oct', 'nov', 'dic'];
    var SEP = '\u0001';

    function esDimension(tipo) { return DIMENSIONES.indexOf(tipo) >= 0; }

    /** Al soltar un número se suma; días y porcentajes se promedian. */
    function calculoPorDefecto(tipo) {
        if (tipo === 'conteo') return 'conteo';
        return tipo === 'dias' || tipo === 'porcentaje' ? 'promedio' : 'suma';
    }

    /** Los promedios, máximos y mínimos no se pueden repartir en porciones ni apilar. */
    function esAditivo(calculo) { return calculo === 'suma' || calculo === 'conteo'; }

    // ------------------------------------------------------------------
    // Formato de números según lo que son (montos, cantidades, días, %)
    // ------------------------------------------------------------------
    var cacheFormatos = {};
    function formateador(min, max) {
        var clave = min + '-' + max;
        if (!cacheFormatos[clave]) {
            cacheFormatos[clave] = new Intl.NumberFormat('en-US', { minimumFractionDigits: min, maximumFractionDigits: max });
        }
        return cacheFormatos[clave];
    }

    function abreviado(valor, prefijo) {
        var abs = Math.abs(valor);
        if (abs >= 1e6) return prefijo + formateador(0, 1).format(valor / 1e6) + ' M';
        if (abs >= 1e3) return prefijo + formateador(0, 1).format(valor / 1e3) + ' mil';
        return prefijo + formateador(0, 0).format(valor);
    }

    /**
     * Texto de un número. `corto` es para ejes y etiquetas de gráficos.
     * Montos: S/ 1,770.00. Conteos y cantidades: 1,047 (o 2.5 si tiene
     * decimales). Días y %: un decimal cuando es promedio.
     */
    function formatear(tipo, calculo, valor, corto) {
        if (valor === null || valor === undefined || typeof valor !== 'number' || isNaN(valor)) return '—';
        var promedio = calculo === 'promedio';
        if (tipo === 'moneda') {
            if (corto) return abreviado(valor, 'S/ ');
            return 'S/ ' + formateador(2, 2).format(valor);
        }
        if (tipo === 'conteo') return corto ? abreviado(valor, '') : formateador(0, 0).format(valor);
        if (corto && Math.abs(valor) >= 1e4) return abreviado(valor, '') + (tipo === 'porcentaje' ? ' %' : '');
        if (tipo === 'porcentaje') return formateador(0, 1).format(valor) + ' %';
        if (tipo === 'dias') return formateador(0, promedio ? 1 : 0).format(valor);
        return formateador(0, promedio ? 1 : 2).format(valor);
    }

    /** Formato de número de Excel equivalente (las celdas quedan como números). */
    function formatoExcel(tipo, calculo) {
        if (tipo === 'moneda') return '"S/ "#,##0.00';
        if (tipo === 'conteo') return '#,##0';
        if (tipo === 'porcentaje') return '0.0" %"';
        if (calculo === 'promedio') return '#,##0.0';
        return '#,##0.##';
    }

    /** "2001-02" → "feb 2001"; el resto queda igual. */
    function etiquetaDimension(tipo, valor) {
        if (valor === null || valor === undefined || valor === '') return '(vacío)';
        var texto = String(valor);
        if (tipo === 'periodo') {
            var m = texto.match(/^(\d{4})-(\d{2})$/);
            if (m) return MESES[Number(m[2]) - 1] + ' ' + m[1];
            var d = texto.match(/^(\d{4})-(\d{2})-(\d{2})$/);
            if (d) return Number(d[3]) + ' ' + MESES[Number(d[2]) - 1] + ' ' + d[1];
        }
        return texto;
    }

    function nombreValor(valor, tipo) {
        var campo = valor[0];
        var calculo = valor[1];
        if (calculo === 'conteo' || calculo === 'suma') return campo;
        return NOMBRE_CALCULO[calculo] + ' de ' + campo.charAt(0).toLowerCase() + campo.slice(1);
    }

    // ------------------------------------------------------------------
    // Disposición
    // ------------------------------------------------------------------
    /**
     * Deja solo lo que el conjunto tiene (CA-06.5): al cambiar de conjunto
     * se conservan los campos que también existen en el nuevo.
     * `campos`: [{etiqueta, tipo}] del conjunto; `conteo`: su etiqueta de conteo.
     */
    function disposicionValida(disp, campos, conteo) {
        disp = disp || {};
        var tipos = {};
        campos.forEach(function (c) { tipos[c.etiqueta] = c.tipo; });
        var dim = function (e) { return typeof e === 'string' && esDimension(tipos[e]); };
        var usados = {};
        var unico = function (e) { if (usados[e]) return false; usados[e] = true; return true; };
        var filas = (Array.isArray(disp.filas) ? disp.filas : []).filter(dim).filter(unico);
        var columnas = (Array.isArray(disp.columnas) ? disp.columnas : []).filter(dim).filter(unico);
        var valores = [];
        (Array.isArray(disp.valores) ? disp.valores : []).forEach(function (v) {
            if (!Array.isArray(v) || v.length !== 2) return;
            var campo = v[0];
            var calculo = v[1];
            if (calculo === 'conteo' || (campo === conteo)) {
                // Un conteo de otro conjunto ("N.º de cotizaciones") pasa a ser el conteo de este.
                if (/^N\.º de /.test(campo) || campo === conteo) campo = conteo;
                else return;
                if (!valores.some(function (x) { return x[0] === conteo; })) valores.push([conteo, 'conteo']);
                return;
            }
            if (tipos[campo] && !esDimension(tipos[campo]) && CALCULOS.indexOf(calculo) >= 0
                && !valores.some(function (x) { return x[0] === campo; })) {
                valores.push([campo, calculo]);
            }
        });
        var filtros = function (obj) {
            var limpio = {};
            Object.keys(obj && typeof obj === 'object' ? obj : {}).forEach(function (e) {
                if (dim(e) && Array.isArray(obj[e])) limpio[e] = obj[e].map(String);
            });
            return limpio;
        };
        return {
            filas: filas,
            columnas: columnas,
            valores: valores,
            solo: filtros(disp.solo),
            excluir: filtros(disp.excluir),
            vista: VISTAS.indexOf(disp.vista) >= 0 ? disp.vista : 'tabla',
            orden: disp.orden === 'nombre' ? 'nombre' : 'valor'
        };
    }

    // ------------------------------------------------------------------
    // Cálculo de la tabla
    // ------------------------------------------------------------------
    function Acumulador() { this.n = 0; this.cuenta = 0; this.suma = 0; this.min = null; this.max = null; }
    Acumulador.prototype.agregar = function (x) {
        this.n += 1;
        if (typeof x !== 'number' || isNaN(x)) return;
        this.cuenta += 1;
        this.suma += x;
        if (this.min === null || x < this.min) this.min = x;
        if (this.max === null || x > this.max) this.max = x;
    };
    Acumulador.prototype.valor = function (calculo) {
        if (calculo === 'conteo') return this.n;
        if (!this.cuenta) return null;
        if (calculo === 'suma') return Math.round(this.suma * 100) / 100;
        if (calculo === 'promedio') return this.suma / this.cuenta;
        if (calculo === 'max') return this.max;
        return this.min;
    };

    function comparaNatural(a, b) {
        return String(a).localeCompare(String(b), 'es', { numeric: true, sensitivity: 'base' });
    }

    function pasaFiltros(fila, indice, disp) {
        var ok = true;
        Object.keys(disp.solo).forEach(function (e) {
            if (ok && indice[e] !== undefined && disp.solo[e].indexOf(String(fila[indice[e]])) < 0) ok = false;
        });
        Object.keys(disp.excluir).forEach(function (e) {
            if (ok && indice[e] !== undefined && disp.excluir[e].indexOf(String(fila[indice[e]])) >= 0) ok = false;
        });
        return ok;
    }

    /**
     * datos: {encabezado: [etiqueta], filas: [[valor]]}.
     * Devuelve las claves de filas y columnas ya ordenadas y `celda(fila,
     * columna, nValor)`, donde fila o columna en null es el total.
     */
    function calcular(datos, disp, campos) {
        var indice = {};
        datos.encabezado.forEach(function (e, i) { indice[e] = i; });
        var tipos = {};
        campos.forEach(function (c) { tipos[c.etiqueta] = c.tipo; });
        var registros = datos.filas.filter(function (f) { return pasaFiltros(f, indice, disp); });
        var nVal = disp.valores.length;
        var grupos = {};
        var clavesFila = {};
        var clavesCol = {};
        var leer = function (fila, campos) {
            return campos.map(function (e) { var v = fila[indice[e]]; return v === null || v === undefined ? '' : String(v); });
        };
        var acumular = function (clave, fila) {
            var accs = grupos[clave];
            if (!accs) {
                accs = grupos[clave] = [];
                for (var i = 0; i < nVal; i++) accs.push(new Acumulador());
            }
            disp.valores.forEach(function (v, i) {
                accs[i].agregar(v[1] === 'conteo' ? 1 : fila[indice[v[0]]]);
            });
        };
        registros.forEach(function (fila) {
            var kf = leer(fila, disp.filas);
            var kc = leer(fila, disp.columnas);
            var sf = kf.join(SEP);
            var sc = kc.join(SEP);
            clavesFila[sf] = kf;
            clavesCol[sc] = kc;
            acumular(sf + '\u0002' + sc, fila);
            acumular(sf + '\u0002*', fila);
            acumular('*\u0002' + sc, fila);
            acumular('*\u0002*', fila);
        });
        var celda = function (kf, kc, i) {
            var clave = (kf === null ? '*' : kf.join(SEP)) + '\u0002' + (kc === null ? '*' : kc.join(SEP));
            var accs = grupos[clave];
            return accs ? accs[i].valor(disp.valores[i][1]) : (disp.valores[i][1] === 'conteo' ? 0 : null);
        };
        var porTiempo = function (lista) { return lista.some(function (e) { return tipos[e] === 'periodo'; }); };
        var natural = function (a, b) {
            for (var i = 0; i < a.length; i++) {
                var c = comparaNatural(a[i], b[i]);
                if (c) return c;
            }
            return 0;
        };
        var filas = Object.keys(clavesFila).map(function (k) { return clavesFila[k]; });
        var columnas = Object.keys(clavesCol).map(function (k) { return clavesCol[k]; });
        if (nVal && disp.orden === 'valor' && !porTiempo(disp.filas)) {
            filas.sort(function (a, b) { return ((celda(b, null, 0) || 0) - (celda(a, null, 0) || 0)) || natural(a, b); });
        } else {
            filas.sort(natural);
        }
        columnas.sort(natural);
        return { registros: registros.length, filas: filas, columnas: columnas, celda: celda, tipos: tipos };
    }

    return {
        esDimension: esDimension,
        esAditivo: esAditivo,
        calculoPorDefecto: calculoPorDefecto,
        formatear: formatear,
        formatoExcel: formatoExcel,
        etiquetaDimension: etiquetaDimension,
        nombreValor: nombreValor,
        nombreCalculo: NOMBRE_CALCULO,
        disposicionValida: disposicionValida,
        calcular: calcular
    };
});
