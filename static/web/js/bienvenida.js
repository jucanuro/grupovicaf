/*
 * Aviso de bienvenida de la home (specs/WEB v8, REQ-WEB-76 y 77; v9, REQ-WEB-79).
 * Se muestra una sola vez por navegador (marca en localStorage) y se cierra
 * solo a los 10 s (con cuenta regresiva), con la X, con Esc, al tocar fuera o al ir a Acreditación.
 * Si localStorage no está disponible no se muestra: sin la marca saldría en
 * cada visita.
 */
(function () {
    'use strict';

    var CLAVE = 'vicaf_bienvenida_vista';
    var DURACION_MS = 10000;
    var aviso = document.querySelector('[data-bienvenida]');
    if (!aviso) return;

    try {
        if (window.localStorage.getItem(CLAVE)) return;
        window.localStorage.setItem(CLAVE, new Date().toISOString());
    } catch (e) {
        return;
    }

    var reducido = window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    var barra = aviso.querySelector('[data-bienvenida-barra]');
    var panel = aviso.querySelector('[data-bienvenida-panel]');
    var segundos = aviso.querySelector('[data-bienvenida-segundos]');
    var cuenta = null;
    var temporizador = null;
    var cerrado = false;

    function cerrar() {
        if (cerrado) return;
        cerrado = true;
        window.clearTimeout(temporizador);
        window.clearInterval(cuenta);
        document.removeEventListener('keydown', alTeclear);
        aviso.classList.add('opacity-0');
        if (panel) panel.classList.add('scale-95', 'translate-y-3');
        window.setTimeout(function () {
            aviso.classList.add('hidden');
            aviso.classList.remove('flex');
        }, reducido ? 0 : 500);
    }

    function alTeclear(evento) {
        if (evento.key === 'Escape') cerrar();
    }

    aviso.classList.remove('hidden');
    aviso.classList.add('flex');
    // Un cuadro después, para que la transición de opacidad se vea.
    window.requestAnimationFrame(function () {
        aviso.classList.remove('opacity-0');
        if (panel) panel.classList.remove('scale-95', 'translate-y-3');
        if (barra && !reducido) {
            barra.style.transition = 'transform ' + DURACION_MS + 'ms linear';
            barra.style.transform = 'scaleX(0)';
        }
    });

    temporizador = window.setTimeout(cerrar, DURACION_MS);
    var fin = Date.now() + DURACION_MS;
    cuenta = window.setInterval(function () {
        if (segundos) segundos.textContent = String(Math.max(0, Math.ceil((fin - Date.now()) / 1000)));
    }, 250);
    document.addEventListener('keydown', alTeclear);
    aviso.addEventListener('click', function (evento) {
        if (evento.target === aviso || evento.target.closest('[data-bienvenida-cerrar]')) cerrar();
    });
    var ir = aviso.querySelector('[data-bienvenida-ir]');
    if (ir) ir.addEventListener('click', cerrar);
})();
