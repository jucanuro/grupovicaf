/* Correo VICAF: calendario pequeño de la barra lateral (solo consulta de fechas). */
(function () {
    'use strict';
    var raiz = document.querySelector('[data-mini-cal]');
    if (!raiz) { return; }
    var titulo = raiz.querySelector('[data-mc-titulo]');
    var dias = raiz.querySelector('[data-mc-dias]');
    var NOMBRES = ['enero', 'febrero', 'marzo', 'abril', 'mayo', 'junio', 'julio', 'agosto', 'septiembre', 'octubre', 'noviembre', 'diciembre'];
    var hoy = new Date();
    var visto = new Date(hoy.getFullYear(), hoy.getMonth(), 1);

    function pintar() {
        titulo.textContent = NOMBRES[visto.getMonth()] + ' de ' + visto.getFullYear();
        dias.textContent = '';
        'LMMJVSD'.split('').forEach(function (l) {
            var c = document.createElement('span');
            c.className = 'mini-cal__cab';
            c.textContent = l;
            dias.appendChild(c);
        });
        var desfase = (visto.getDay() + 6) % 7; // semana desde el lunes
        var inicio = new Date(visto.getFullYear(), visto.getMonth(), 1 - desfase);
        for (var i = 0; i < 42; i++) {
            var f = new Date(inicio.getFullYear(), inicio.getMonth(), inicio.getDate() + i);
            var c = document.createElement('span');
            c.className = 'mini-cal__dia';
            if (f.getMonth() !== visto.getMonth()) { c.className += ' mini-cal__dia--fuera'; }
            if (f.getDay() === 0 || f.getDay() === 6) { c.className += ' mini-cal__dia--finde'; }
            if (f.toDateString() === hoy.toDateString()) { c.className += ' mini-cal__dia--hoy'; c.setAttribute('aria-current', 'date'); }
            c.textContent = f.getDate();
            dias.appendChild(c);
        }
    }
    raiz.querySelector('[data-mc-ant]').addEventListener('click', function () { visto.setMonth(visto.getMonth() - 1); pintar(); });
    raiz.querySelector('[data-mc-sig]').addEventListener('click', function () { visto.setMonth(visto.getMonth() + 1); pintar(); });
    pintar();
})();
