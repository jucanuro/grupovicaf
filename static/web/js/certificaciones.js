// Modal de las certificaciones (templates/web/partials/modal_certificacion.html,
// specs/WEB v4). Reemplaza a modal-certificado.js (imagen INACAL) y a
// certificado-pdf.js (PDF ISO 9001) de v3.
//
// Cada card es un <a href="archivo" target="_blank" data-cert-open> real: sin
// JavaScript abre el archivo en una pestaña nueva. Con JavaScript:
//   - imagen: se muestra en el modal en cualquier dispositivo (REQ-WEB-45);
//   - PDF: se embebe en el modal solo en escritorio con visor de PDF; en
//     móvil, tableta o sin visor el clic sigue a la pestaña nueva (REQ-WEB-46),
//     porque los PDF embebidos fallan en muchos teléfonos.
//
// Las funciones puras se exportan en module.exports para probarlas con
// `node --test tests/js/certificaciones.test.js`.
(function (raiz) {
    'use strict';

    var CONSULTA_ESCRITORIO = '(min-width: 768px) and (hover: hover) and (pointer: fine)';

    // true solo si conviene embeber un PDF: pantalla de escritorio con puntero
    // fino y un navegador que no declara que le falta el visor de PDF. Los
    // navegadores que no conocen pdfViewerEnabled (undefined) se tratan como
    // con visor.
    function debeUsarModal(nav, matchMedia) {
        if (nav && nav.pdfViewerEnabled === false) return false;
        if (typeof matchMedia !== 'function') return false;
        return Boolean(matchMedia(CONSULTA_ESCRITORIO).matches);
    }

    // Cómo se abre una card: 'imagen' o 'pdf' (en el modal) o 'pestana' (no se
    // intercepta el clic y el enlace abre la pestaña nueva).
    function modoApertura(tipo, nav, matchMedia) {
        if (tipo === 'imagen') return 'imagen';
        if (tipo === 'pdf' && debeUsarModal(nav, matchMedia)) return 'pdf';
        return 'pestana';
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
        modoApertura: modoApertura,
        siguienteFoco: siguienteFoco,
    };

    if (typeof module !== 'undefined' && module.exports) {
        module.exports = api;
    }
    if (!raiz || !raiz.document) return;

    raiz.document.addEventListener('DOMContentLoaded', function () {
        var doc = raiz.document;
        var modal = doc.getElementById('modal-certificacion');
        if (!modal) return;

        var panel = modal.querySelector('[data-cert-panel]');
        var titulo = modal.querySelector('#modal-certificacion-titulo');
        var contenido = modal.querySelector('[data-cert-contenido]');
        var descargar = modal.querySelector('[data-cert-descargar]');
        var disparador = null;

        function controles() {
            return Array.prototype.filter.call(
                modal.querySelectorAll('a[href], button:not([disabled]), iframe'),
                function (el) { return el.offsetParent !== null; }
            );
        }

        function abrir(enlace, modo) {
            disparador = enlace;
            var nombre = enlace.getAttribute('data-cert-titulo') || 'Certificado';
            titulo.textContent = nombre;

            var elemento;
            if (modo === 'pdf') {
                elemento = doc.createElement('iframe');
                elemento.title = nombre + ' (PDF)';
                elemento.className = 'h-full w-full';
                panel.classList.add('h-[90vh]');
            } else {
                elemento = doc.createElement('img');
                elemento.alt = nombre;
                elemento.className = 'mx-auto h-auto max-w-full self-start object-contain p-3 sm:p-5';
                elemento.decoding = 'async';
                panel.classList.remove('h-[90vh]');
            }
            elemento.src = enlace.href;
            contenido.replaceChildren(elemento);
            descargar.href = enlace.href;

            modal.classList.remove('hidden');
            modal.classList.add('flex');
            doc.body.style.overflow = 'hidden';
            var primero = modal.querySelector('[data-cert-cerrar]');
            if (primero) primero.focus();
        }

        function cerrar() {
            if (modal.classList.contains('hidden')) return;
            modal.classList.add('hidden');
            modal.classList.remove('flex');
            // Quitar el <img>/<iframe> libera el archivo (y detiene el visor de PDF).
            contenido.replaceChildren();
            descargar.setAttribute('href', '#');
            doc.body.style.overflow = '';
            if (disparador && typeof disparador.focus === 'function') disparador.focus();
            disparador = null;
        }

        doc.querySelectorAll('[data-cert-open]').forEach(function (enlace) {
            enlace.addEventListener('click', function (evento) {
                var modo = modoApertura(
                    enlace.getAttribute('data-cert-tipo'),
                    raiz.navigator,
                    raiz.matchMedia && raiz.matchMedia.bind(raiz)
                );
                if (modo === 'pestana') return;
                evento.preventDefault();
                abrir(enlace, modo);
            });
        });

        modal.querySelectorAll('[data-cert-cerrar]').forEach(function (boton) {
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
