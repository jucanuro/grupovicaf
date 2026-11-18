/* Vista de impresión: abre el diálogo de impresión al cargar. */
(function () {
    'use strict';
    var boton = document.querySelector('[data-imprimir]');
    if (boton) { boton.addEventListener('click', function () { window.print(); }); }
    window.addEventListener('load', function () { window.setTimeout(function () { window.print(); }, 300); });
})();
