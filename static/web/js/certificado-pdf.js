// Visor del PDF de las certificaciones (ISO 9001) en /acreditacion/
// (templates/web/partials/modal_certificado_pdf.html, specs/WEB v3).
//
// Cada botón "Ver certificado" es un <a href="…pdf" target="_blank"> real: sin
// JavaScript, en móvil o sin visor de PDF del navegador abre el PDF en una
// pestaña nueva (REQ-WEB-35), porque los PDF embebidos fallan en muchos
// teléfonos. Solo en escritorio con visor de PDF el clic se intercepta y el
// PDF se muestra en el modal (REQ-WEB-32 a 34).
//
// Las funciones puras se exportan en module.exports para probarlas con
// `node --test tests/js/certificado-pdf.test.js`.
(function (raiz) {
    'use strict';

    var CONSULTA_ESCRITORIO = '(min-width: 768px) and (hover: hover) and (pointer: fine)';

    // true solo si conviene el modal: pantalla de escritorio con puntero fino
    // y un navegador que no declara que le falta el visor de PDF. Los navegadores
    // que no conocen pdfViewerEnabled (undefined) se tratan como con visor.
    function debeUsarModal(nav, matchMedia) {
        if (nav && nav.pdfViewerEnabled === false) return false;
        if (typeof matchMedia !== 'function') return false;
        return Boolean(matchMedia(CONSULTA_ESCRITORIO).matches);
    }

    // Índice del control que recibe el foco al pulsar Tab (o Shift+Tab) dentro
    // del modal, ciclando entre el primero y el último. Si el foco no está en
    // ningún control (-1), Tab va al primero y Shift+Tab al último.
    function siguienteFoco(total, actual, haciaAtras) {
        if (total <= 0) return -1;
        if (actual < 0 || actual >= total) return haciaAtras ? total - 1 : 0;
        if (haciaAtras) return actual === 0 ? total - 1 : actual - 1;
        return actual === total - 1 ? 0 : actual + 1;
    }

    var api = {
        CONSULTA_ESCRITORIO: CONSULTA_ESCRITORIO,
        debeUsarModal: debeUsarModal,
        siguienteFoco: siguienteFoco,
    };

    if (typeof module !== 'undefined' && module.exports) {
        module.exports = api;
    }
    if (!raiz || !raiz.document) return;

    raiz.document.addEventListener('DOMContentLoaded', function () {
        var doc = raiz.document;
        var modal = doc.getElementById('modal-certificado-pdf');
        if (!modal) return;

        var titulo = modal.querySelector('#modal-certificado-pdf-titulo');
        var visor = modal.querySelector('[data-cert-pdf-visor]');
        var descargar = modal.querySelector('[data-cert-pdf-descargar]');
        var disparador = null;

        function controles() {
            return Array.prototype.filter.call(
                modal.querySelectorAll('a[href], button:not([disabled]), iframe'),
                function (el) { return el.offsetParent !== null; }
            );
        }

        function abrir(enlace) {
            disparador = enlace;
            titulo.textContent = enlace.getAttribute('data-cert-pdf-titulo') || 'Certificado';
            visor.setAttribute('title', titulo.textContent + ' (PDF)');
            visor.src = enlace.href;
            descargar.href = enlace.href;
            modal.classList.remove('hidden');
            modal.classList.add('flex');
            doc.body.style.overflow = 'hidden';
            var primero = modal.querySelector('[data-cert-pdf-cerrar]');
            if (primero) primero.focus();
        }

        function cerrar() {
            if (modal.classList.contains('hidden')) return;
            modal.classList.add('hidden');
            modal.classList.remove('flex');
            visor.src = 'about:blank';
            doc.body.style.overflow = '';
            if (disparador && typeof disparador.focus === 'function') disparador.focus();
            disparador = null;
        }

        doc.querySelectorAll('[data-cert-pdf-open]').forEach(function (enlace) {
            enlace.addEventListener('click', function (evento) {
                if (!debeUsarModal(raiz.navigator, raiz.matchMedia && raiz.matchMedia.bind(raiz))) return;
                evento.preventDefault();
                abrir(enlace);
            });
        });

        modal.querySelectorAll('[data-cert-pdf-cerrar]').forEach(function (boton) {
            boton.addEventListener('click', cerrar);
        });

        // Clic fuera del panel: el propio contenedor oscuro es el fondo.
        modal.addEventListener('click', function (evento) {
            if (evento.target === modal) cerrar();
        });

        doc.addEventListener('keydown', function (evento) {
            if (modal.classList.contains('hidden')) return;
            if (evento.key === 'Escape') {
                evento.preventDefault();
                cerrar();
                return;
            }
            if (evento.key !== 'Tab') return;
            var lista = controles();
            var siguiente = siguienteFoco(lista.length, lista.indexOf(doc.activeElement), evento.shiftKey);
            if (siguiente < 0) return;
            evento.preventDefault();
            lista[siguiente].focus();
        });
    });
})(typeof window !== 'undefined' ? window : null);
