/* dashboard.js — gráficos del dashboard del LIMS (VCF-LIMS, REQ-LIMS-06, 09 y 14).
 *
 * Lee los datos de <script id="dashboard-datos"> (json_script de Django) y
 * dibuja con Chart.js 4.4.1 (static/vendor/chartjs, cargado con defer antes
 * que este archivo). Colores, ejes y ficha emergente salen del tema común
 * static/js/graficos_tema.js (paleta validada de specs/VCF-LIMS/design.md). El resto del dashboard es HTML del servidor.
 */
(function () {
    'use strict';

    // Paleta y estilo comunes (static/js/graficos_tema.js, REQ-LIMS-85).
    var G = window.VicafGraficos;
    var COLORES = null;

    function paleta() {
        var p = G.paleta();
        return {
            aceptadas: p.series[0],
            enGestion: p.series[2],
            perdidas: p.series[1],
            linea: p.series[0],
            eje: p.eje,
            superficie: p.superficie
        };
    }

    function leerDatos() {
        var nodo = document.getElementById('dashboard-datos');
        if (!nodo) return null;
        try {
            return JSON.parse(nodo.textContent);
        } catch (e) {
            return null;
        }
    }

    function tooltipBase(titulos) {
        return G.ficha({
            callbacks: {
                title: function (items) {
                    return items.length ? titulos[items[0].dataIndex] : '';
                }
            }
        });
    }

    function ejes(apilado) {
        return G.ejes({ apilado: apilado });
    }

    function barrasCotizaciones(Chart, datos) {
        var lienzo = document.getElementById('grafico-cotizaciones-mes');
        if (!lienzo || !datos) return;
        var serie = function (etiqueta, valores, color, ultima) {
            return {
                label: etiqueta,
                data: valores,
                backgroundColor: color,
                // 2 px de superficie entre segmentos; solo el de arriba redondeado.
                borderColor: COLORES.superficie,
                borderWidth: { top: 2, bottom: 0, left: 0, right: 0 },
                borderSkipped: false,
                borderRadius: ultima ? { topLeft: 4, topRight: 4 } : 0,
                maxBarThickness: 36
            };
        };
        new Chart(lienzo, {
            type: 'bar',
            data: {
                labels: datos.etiquetas,
                datasets: [
                    serie('Aceptadas', datos.aceptadas, COLORES.aceptadas, false),
                    serie('En gestión', datos.en_gestion, COLORES.enGestion, false),
                    serie('Rechazadas o anuladas', datos.perdidas, COLORES.perdidas, true)
                ]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                animation: false,
                interaction: { mode: 'index', intersect: false },
                plugins: {
                    legend: { display: false },  // la leyenda es HTML, arriba del gráfico
                    tooltip: tooltipBase(datos.titulos)
                },
                scales: ejes(true)
            }
        });
    }

    function lineaEnsayos(Chart, datos) {
        var lienzo = document.getElementById('grafico-ensayos-semana');
        if (!lienzo || !datos) return;
        var ultimo = datos.valores.length - 1;
        new Chart(lienzo, {
            type: 'line',
            data: {
                labels: datos.etiquetas,
                datasets: [{
                    label: 'Ensayos finalizados',
                    data: datos.valores,
                    borderColor: COLORES.linea,
                    backgroundColor: function (ctx) { return G.degradado(ctx.chart, COLORES.linea); },
                    borderWidth: 2,
                    fill: true,
                    tension: 0,
                    // Solo el último punto se marca; el resto aparece al pasar el cursor.
                    pointRadius: datos.valores.map(function (_, i) { return i === ultimo ? 4 : 0; }),
                    pointHoverRadius: 5,
                    pointBackgroundColor: COLORES.linea,
                    pointBorderColor: COLORES.superficie,
                    pointBorderWidth: 2
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                animation: false,
                interaction: { mode: 'index', intersect: false },
                plugins: {
                    legend: { display: false },  // una sola serie: el título la nombra
                    tooltip: tooltipBase(datos.titulos)
                },
                scales: ejes(false)
            },
            plugins: [crosshair]
        });
    }

    // Línea vertical bajo el cursor (REQ-LIMS-09).
    var crosshair = {
        id: 'crosshair',
        afterDatasetsDraw: function (chart) {
            var activos = chart.tooltip && chart.tooltip.getActiveElements();
            if (!activos || !activos.length) return;
            var x = activos[0].element.x;
            var area = chart.chartArea;
            var ctx = chart.ctx;
            ctx.save();
            ctx.beginPath();
            ctx.moveTo(x, area.top);
            ctx.lineTo(x, area.bottom);
            ctx.lineWidth = 1;
            ctx.strokeStyle = COLORES.eje;
            ctx.stroke();
            ctx.restore();
        }
    };

    function iniciar() {
        if (window.lucide && typeof window.lucide.createIcons === 'function') {
            window.lucide.createIcons();
        }
        var Chart = window.Chart;
        var datos = leerDatos();
        if (!Chart || !datos || !G) return;
        G.aplicar();
        dibujar(Chart, datos);
        // Al cambiar de modo claro/oscuro se vuelven a dibujar con la otra paleta.
        document.addEventListener('vicaf:tema', function () { dibujar(Chart, datos); });
    }

    function dibujar(Chart, datos) {
        COLORES = paleta();
        ['grafico-cotizaciones-mes', 'grafico-ensayos-semana'].forEach(function (id) {
            var lienzo = document.getElementById(id);
            var previo = lienzo && Chart.getChart ? Chart.getChart(lienzo) : null;
            if (previo) previo.destroy();
        });
        barrasCotizaciones(Chart, datos.cotizaciones_mes);
        lineaEnsayos(Chart, datos.ensayos_semana);
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', iniciar);
    } else {
        iniciar();
    }
})();
