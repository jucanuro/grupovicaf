/* Cálculos del ensayo de compresión (ASTM C39), vista previa en el navegador.
 * Mismas reglas que proyectos/calculos_compresion.py; el valor oficial lo
 * calcula el servidor al terminar. Si se cambia una regla, cambiarla en ambos.
 */
(function (global) {
    'use strict';

    var MPA_A_KGCM2 = 10.1972;
    var PI = 3.1416;  // como la hoja del laboratorio (áreas del informe real)
    var TABLA_FACTOR_LD = [[1.00, 0.87], [1.25, 0.93], [1.50, 0.96], [1.75, 0.98]];

    // Redondeo "half up" decimal sin el error de coma flotante de Math.round(x*100)/100.
    function q(valor, decimales) {
        var signo = valor < 0 ? -1 : 1;
        var r = Number(Math.round(Number(Math.abs(valor) + 'e' + decimales)) + 'e-' + decimales);
        return signo * r;
    }

    function factorCorreccion(ld) {
        if (ld > 1.75) return 1.00;
        if (ld < 1.00) return null;
        for (var i = 0; i < TABLA_FACTOR_LD.length - 1; i++) {
            var a = TABLA_FACTOR_LD[i], b = TABLA_FACTOR_LD[i + 1];
            if (ld >= a[0] && ld <= b[0]) return q(a[1] + (b[1] - a[1]) * (ld - a[0]) / (b[0] - a[0]), 2);
        }
        return TABLA_FACTOR_LD[TABLA_FACTOR_LD.length - 1][1];
    }

    function numero(v) {
        if (v === null || v === undefined) return null;
        var t = String(v).trim().replace(',', '.');
        if (t === '') return null;
        var n = Number(t);
        return isFinite(n) ? n : null;
    }

    /** datos: {d1, d2, l1, l2, l3, carga_kn, masa_g?, fc?}. Devuelve null si faltan datos. */
    function calcular(datos) {
        var d1 = numero(datos.d1), d2 = numero(datos.d2);
        var l1 = numero(datos.l1), l2 = numero(datos.l2), l3 = numero(datos.l3);
        var carga = numero(datos.carga_kn);
        var vals = [d1, d2, l1, l2, l3, carga];
        for (var i = 0; i < vals.length; i++) if (vals[i] === null || vals[i] <= 0) return null;

        var diametro = q(Math.round(q((d1 + d2) / 2, 6) * 4) / 4, 2);
        var longitud = q((l1 + l2 + l3) / 3, 2);
        var area = q(PI * diametro * diametro / 4, 2);
        var ld = q(longitud / diametro, 2);
        var factor = factorCorreccion(ld);
        var r = { diametro: diametro, longitud: longitud, area: area, ld: ld, factor: factor };
        if (factor === null) { r.error = 'La relación L/D es menor que 1,00: la norma no admite el ensayo.'; return r; }
        r.mpa = q(carga * 1000 / area * factor, 1);
        r.kgcm2 = q(r.mpa * MPA_A_KGCM2, 1);
        var fc = numero(datos.fc);
        r.porcentaje = fc ? q(r.kgcm2 / fc * 100, 0) : null;
        var masa = numero(datos.masa_g);
        r.densidad = masa ? q(masa / (area * longitud) * 1e6 / 10, 0) * 10 : null;
        return r;
    }

    global.CompresionCalculos = { calcular: calcular, factorCorreccion: factorCorreccion, q: q };
})(window);
