/* graficos_tema.js — tema común de Chart.js del LIMS (HU-LIMS-23, REQ-LIMS-85).
 *
 * Se carga con defer después de chart.umd.js y antes de dashboard.js /
 * analisis.js. Fija los valores por defecto (tipografía, rejilla, barras
 * redondeadas, ficha emergente como tarjeta) y expone la paleta validada
 * (skill dataviz; specs/VCF-LIMS/design.md) en claro y en oscuro. El modo
 * oscuro tiene sus propios tonos, no es una inversión. Al cambiar el tema
 * (evento `vicaf:tema` de static/js/tema.js) se vuelven a fijar antes de que
 * cada pantalla redibuje.
 */
(function () {
    'use strict';

    var CLARO = {
        series: ['#2a78d6', '#eb6834', '#1baf7a', '#eda100', '#e87ba4', '#008300', '#6250d6', '#e34948'],
        otros: '#8a8984',
        superficie: '#ffffff',
        rejilla: '#eef1f5',
        eje: '#d5dae2',
        texto: '#64748b',
        textoFuerte: '#0f172a',
        fichaFondo: '#ffffff',
        fichaBorde: '#e2e8f0',
        relleno: 0.12
    };
    var OSCURO = {
        series: ['#3987e5', '#d95926', '#199e70', '#c98500', '#d55181', '#0ca30c', '#9085e9', '#e66767'],
        otros: '#7c8796',
        superficie: '#111a2b',
        rejilla: '#1f2b3e',
        eje: '#334359',
        texto: '#94a3b8',
        textoFuerte: '#e5e7eb',
        fichaFondo: '#0f172a',
        fichaBorde: '#334155',
        relleno: 0.18
    };

    function oscuro() { return document.documentElement.classList.contains('dark'); }
    function paleta() { return oscuro() ? OSCURO : CLARO; }

    function hexARgba(hex, alfa) {
        var h = hex.replace('#', '');
        var n = parseInt(h.length === 3 ? h.replace(/./g, '$&$&') : h, 16);
        return 'rgba(' + (n >> 16 & 255) + ', ' + (n >> 8 & 255) + ', ' + (n & 255) + ', ' + alfa + ')';
    }

    /** Ficha emergente como tarjeta (mismo look que la ficha del Gantt y del calendario). */
    function ficha(extra) {
        var p = paleta();
        var base = {
            backgroundColor: p.fichaFondo,
            borderColor: p.fichaBorde,
            borderWidth: 1,
            titleColor: p.textoFuerte,
            bodyColor: p.textoFuerte,
            footerColor: p.texto,
            titleFont: { weight: '700', size: 12 },
            bodyFont: { size: 12 },
            footerFont: { size: 11, weight: '500' },
            padding: { x: 12, y: 10 },
            cornerRadius: 10,
            caretSize: 0,
            caretPadding: 10,
            boxWidth: 9,
            boxHeight: 9,
            boxPadding: 5,
            usePointStyle: true,
            displayColors: true
        };
        if (extra) Object.keys(extra).forEach(function (k) { base[k] = extra[k]; });
        return base;
    }

    function ejes(opciones) {
        var p = paleta();
        var o = opciones || {};
        return {
            x: {
                stacked: !!o.apilado,
                grid: { display: false },
                border: { color: p.eje },
                ticks: { color: p.texto, maxRotation: 0, autoSkip: true, padding: 6 }
            },
            y: {
                stacked: !!o.apilado,
                beginAtZero: true,
                grid: { color: p.rejilla, drawTicks: false },
                border: { display: false, dash: [3, 3] },
                ticks: { color: p.texto, precision: o.decimales ? undefined : 0, padding: 8, maxTicksLimit: 6 }
            }
        };
    }

    /** Degradado vertical bajo una línea (de la serie a transparente). */
    function degradado(chart, color) {
        var area = chart.chartArea;
        if (!area) return hexARgba(color, paleta().relleno);
        var g = chart.ctx.createLinearGradient(0, area.top, 0, area.bottom);
        g.addColorStop(0, hexARgba(color, paleta().relleno + 0.1));
        g.addColorStop(1, hexARgba(color, 0));
        return g;
    }

    function aplicar() {
        var Chart = window.Chart;
        if (!Chart || !Chart.defaults) return;
        var p = paleta();
        var d = Chart.defaults;
        d.font.family = getComputedStyle(document.body).fontFamily || 'Inter, system-ui, sans-serif';
        d.font.size = 11;
        d.color = p.texto;
        d.borderColor = p.rejilla;
        d.animation = false;
        d.plugins.legend.labels.color = p.textoFuerte;
        d.plugins.legend.labels.usePointStyle = true;
        d.plugins.legend.labels.pointStyle = 'rectRounded';
        d.plugins.legend.labels.boxWidth = 10;
        d.plugins.legend.labels.boxHeight = 10;
        d.plugins.legend.labels.padding = 14;
        Object.assign(d.plugins.tooltip, ficha());
        d.elements.bar.borderRadius = 4;
        d.elements.bar.borderSkipped = 'start';
        d.elements.line.borderWidth = 2;
        d.elements.line.tension = 0;
        d.elements.point.radius = 0;
        d.elements.point.hoverRadius = 5;
        d.elements.point.hoverBorderWidth = 2;
        d.elements.arc.borderColor = p.superficie;
        d.elements.arc.borderWidth = 2;
        d.scale.grid.color = p.rejilla;
        d.scale.ticks.color = p.texto;
    }

    window.VicafGraficos = {
        paleta: paleta,
        oscuro: oscuro,
        ficha: ficha,
        ejes: ejes,
        degradado: degradado,
        rgba: hexARgba,
        aplicar: aplicar
    };

    // Antes que cualquier listener de las pantallas (este archivo carga primero).
    document.addEventListener('vicaf:tema', aplicar);
    if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', aplicar);
    else aplicar();
})();
