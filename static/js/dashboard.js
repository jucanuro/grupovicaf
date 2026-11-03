/* dashboard.js — gráficos del dashboard del LIMS (VCF-LIMS, REQ-LIMS-06, 09 y 14).
 *
 * Lee los datos de <script id="dashboard-datos"> (json_script de Django) y
 * dibuja con Chart.js 4.4.1 (static/vendor/chartjs, cargado con defer antes
 * que este archivo). Los colores salen de la paleta validada en
 * specs/VCF-LIMS/design.md. El resto del dashboard es HTML del servidor.
 */
(function () {
    'use strict';

    var COLORES = {
        aceptadas: '#2a78d6',
        enGestion: '#1baf7a',
        perdidas: '#eb6834',
        linea: '#2a78d6',
        rejilla: '#e1e0d9',
        eje: '#c3c2b7',
        textoEje: '#6b6a65',
        superficie: '#ffffff'
    };

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
        return {
            backgroundColor: '#0f172a',
            padding: 10,
            cornerRadius: 8,
            titleFont: { weight: '600' },
            callbacks: {
                title: function (items) {
                    return items.length ? titulos[items[0].dataIndex] : '';
                }
            }
        };
    }

    function ejes(apilado) {
        return {
            x: {
                stacked: apilado,
                grid: { display: false },
                border: { color: COLORES.eje },
                ticks: { color: COLORES.textoEje, maxRotation: 0, autoSkip: true }
            },
            y: {
                stacked: apilado,
                beginAtZero: true,
                grid: { color: COLORES.rejilla },
                border: { display: false },
                ticks: { color: COLORES.textoEje, precision: 0 }
            }
        };
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
                    backgroundColor: 'rgba(42, 120, 214, 0.10)',
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
        if (!Chart || !datos) return;
        Chart.defaults.font.family = getComputedStyle(document.body).fontFamily;
        Chart.defaults.font.size = 11;
        barrasCotizaciones(Chart, datos.cotizaciones_mes);
        lineaEnsayos(Chart, datos.ensayos_semana);
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', iniciar);
    } else {
        iniciar();
    }
})();
