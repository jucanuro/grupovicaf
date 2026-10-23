// Modal de las certificaciones (templates/web/partials/modal_certificacion.html,
// specs/WEB v4). Reemplaza a modal-certificado.js (imagen INACAL) y a
// certificado-pdf.js (PDF ISO 9001) de v3.
//
// Cada card es un <a href="archivo" target="_blank" data-cert-open> real: sin
// JavaScript abre el archivo en una pestaña nueva. Con JavaScript toda card
// abre el modal (specs/WEB v6, REQ-WEB-64):
//   - imagen: se muestra en el modal en cualquier dispositivo (REQ-WEB-45);
//   - PDF: se embebe en el modal solo en escritorio con visor de PDF; en
//     móvil, tableta o sin visor el modal muestra "Abrir documento" (pestaña
//     nueva), porque los PDF embebidos quedan en blanco en muchos teléfonos.
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

    // Qué muestra el modal: 'imagen', 'pdf' (embebido) o 'enlace' (el aviso
    // con "Abrir documento" en una pestaña nueva).
    function modoApertura(tipo, nav, matchMedia) {
        if (tipo === 'imagen') return 'imagen';
        if (tipo === 'pdf' && debeUsarModal(nav, matchMedia)) return 'pdf';
        return 'enlace';
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
        var alterno = modal.querySelector('[data-cert-alterno]');
        var abrirPestana = modal.querySelector('[data-cert-abrir]');
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

            var elemento = null;
            alterno.classList.toggle('hidden', modo !== 'enlace');
            alterno.classList.toggle('flex', modo === 'enlace');
            contenido.classList.toggle('hidden', modo === 'enlace');
            panel.classList.remove('h-[90vh]');
            if (modo === 'enlace') {
                abrirPestana.href = enlace.href;
            } else if (modo === 'pdf') {
                elemento = doc.createElement('iframe');
                elemento.title = nombre + ' (PDF)';
                elemento.className = 'h-full w-full';
                panel.classList.add('h-[90vh]');
            } else {
                elemento = doc.createElement('img');
                elemento.alt = nombre;
                elemento.className = 'mx-auto h-auto max-w-full self-start object-contain p-3 sm:p-5';
                elemento.decoding = 'async';
            }
            if (elemento) {
                elemento.src = enlace.href;
                contenido.replaceChildren(elemento);
            }
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
            abrirPestana.setAttribute('href', '#');
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
                evento.preventDefault();
                abrir(enlace, modo);
            });
        });

        modal.querySelectorAll('[data-cert-cerrar]').forEach(function (boton) {
            boton.addEventListener('click', cerrar);
        });

        // "Abrir documento" deja el modal listo para volver: se cierra al usarlo.
        abrirPestana.addEventListener('click', function () { raiz.setTimeout(cerrar, 0); });

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
