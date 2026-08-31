// Modales de documentos institucionales en /nosotros/ (certificados, políticas
// y el listado "ver más"). Varios modales pueden anidarse (el listado abre a
// su vez el modal de un documento), por eso el foco atrapado y Escape operan
// siempre sobre el modal visible con mayor z-index, no sobre el primero del DOM.
document.addEventListener('DOMContentLoaded', function () {
    var FOCUSABLE = 'a[href], button:not([disabled]), textarea, input, select, [tabindex]:not([tabindex="-1"])';
    var lastFocused = null;

    function abiertos() {
        return Array.from(document.querySelectorAll('.fixed.inset-0[role="dialog"]:not(.hidden)'));
    }

    function masAlFrente() {
        var modales = abiertos();
        if (!modales.length) return null;
        return modales.sort(function (a, b) {
            return parseInt(window.getComputedStyle(b).zIndex || 0, 10) - parseInt(window.getComputedStyle(a).zIndex || 0, 10);
        })[0];
    }

    function abrir(modal, trigger) {
        lastFocused = trigger || document.activeElement;
        modal.classList.remove('hidden');
        modal.setAttribute('aria-hidden', 'false');
        document.body.style.overflow = 'hidden';

        var cerrar = modal.querySelector('[data-modal-close]');
        if (cerrar) cerrar.focus();
    }

    function cerrar(modal) {
        modal.classList.add('hidden');
        modal.setAttribute('aria-hidden', 'true');

        if (!abiertos().length) {
            document.body.style.overflow = '';
        }

        if (lastFocused && typeof lastFocused.focus === 'function') lastFocused.focus();
    }

    document.querySelectorAll('[data-modal]').forEach(function (trigger) {
        trigger.addEventListener('click', function (event) {
            event.preventDefault();
            var modal = document.getElementById(trigger.getAttribute('data-modal'));
            if (modal) abrir(modal, trigger);
        });
    });

    document.querySelectorAll('[data-modal-close]').forEach(function (boton) {
        boton.addEventListener('click', function () {
            var modal = document.getElementById(boton.getAttribute('data-modal-close'));
            if (modal) cerrar(modal);
        });
    });

    document.querySelectorAll('.fixed.inset-0[role="dialog"]').forEach(function (modal) {
        modal.addEventListener('click', function (event) {
            if (event.target === modal) cerrar(modal);
        });
    });

    document.addEventListener('keydown', function (event) {
        var top = masAlFrente();
        if (!top) return;

        if (event.key === 'Escape') {
            cerrar(top);
            return;
        }

        if (event.key !== 'Tab') return;

        var focosVisibles = Array.from(top.querySelectorAll(FOCUSABLE)).filter(function (el) {
            return el.offsetParent !== null;
        });
        if (!focosVisibles.length) return;

        var primero = focosVisibles[0];
        var ultimo = focosVisibles[focosVisibles.length - 1];

        if (event.shiftKey && document.activeElement === primero) {
            event.preventDefault();
            ultimo.focus();
        } else if (!event.shiftKey && document.activeElement === ultimo) {
            event.preventDefault();
            primero.focus();
        }
    });
});
