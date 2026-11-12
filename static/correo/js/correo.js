/* Correo VICAF: comportamiento de la bandeja (sin dependencias).
   Va como archivo propio porque la CSP del host no admite scripts en línea. */
(function () {
    'use strict';

    // Confirmaciones (formularios y botones con data-confirmar).
    document.addEventListener('submit', function (e) {
        var form = e.target;
        var boton = e.submitter;
        var texto = (boton && boton.dataset.confirmar) || form.dataset.confirmar;
        if (texto && !window.confirm(texto)) { e.preventDefault(); }
    });

    // Selects que se envían solos al cambiar (filtro de cuenta, mover a…).
    document.querySelectorAll('[data-autoenviar]').forEach(function (sel) {
        sel.addEventListener('change', function () {
            if (sel.value && sel.form) {
                if (sel.form.requestSubmit) { sel.form.requestSubmit(); } else { sel.form.submit(); }
            } else if (!sel.value && sel.name === 'cuenta' && sel.form) {
                sel.form.submit();
            }
        });
    });

    // Selección múltiple en la lista.
    var formLista = document.getElementById('form-lista');
    if (formLista) {
        var todos = formLista.querySelector('[data-seleccionar-todo]');
        var casillas = function () { return formLista.querySelectorAll('input[name="hilos"]'); };
        var actualizar = function () {
            var marcadas = formLista.querySelectorAll('input[name="hilos"]:checked').length;
            formLista.querySelectorAll('[data-requiere-seleccion]').forEach(function (el) { el.disabled = marcadas === 0; });
            if (todos) {
                todos.checked = marcadas > 0 && marcadas === casillas().length;
                todos.indeterminate = marcadas > 0 && marcadas < casillas().length;
            }
            formLista.classList.toggle('con-seleccion', marcadas > 0);
        };
        if (todos) {
            todos.addEventListener('change', function () {
                casillas().forEach(function (c) { c.checked = todos.checked; });
                actualizar();
            });
        }
        formLista.addEventListener('change', function (e) {
            if (e.target.name === 'hilos') { actualizar(); }
        });
        actualizar();

        // El botón «Mover» exige elegir carpeta.
        formLista.addEventListener('submit', function (e) {
            if (e.submitter && e.submitter.value === 'mover') {
                var destino = formLista.querySelector('select[name="destino"]');
                if (destino && !destino.value) { e.preventDefault(); destino.focus(); }
            }
        });

        // Doble clic: pantalla completa.
        formLista.addEventListener('dblclick', function (e) {
            var fila = e.target.closest('[data-fila]');
            if (fila && !e.target.closest('.casilla')) { window.location.href = fila.dataset.urlCompleta; }
        });

        // Teclado: ↑ ↓ (o j/k) recorren, Enter abre, Mayús+Enter pantalla completa, x selecciona.
        var lista = formLista.querySelector('[data-lista]');
        if (lista) {
            lista.addEventListener('keydown', function (e) {
                var enlace = e.target.closest('.fila__enlace');
                if (!enlace) { return; }
                var enlaces = Array.prototype.slice.call(lista.querySelectorAll('.fila__enlace'));
                var i = enlaces.indexOf(enlace);
                var fila = enlace.closest('[data-fila]');
                if (e.key === 'ArrowDown' || e.key === 'j') {
                    e.preventDefault();
                    if (enlaces[i + 1]) { enlaces[i + 1].focus(); }
                } else if (e.key === 'ArrowUp' || e.key === 'k') {
                    e.preventDefault();
                    if (enlaces[i - 1]) { enlaces[i - 1].focus(); }
                } else if (e.key === 'Home') {
                    e.preventDefault(); enlaces[0].focus();
                } else if (e.key === 'End') {
                    e.preventDefault(); enlaces[enlaces.length - 1].focus();
                } else if (e.key === 'Enter' && e.shiftKey) {
                    e.preventDefault(); window.location.href = fila.dataset.urlCompleta;
                } else if (e.key === 'x') {
                    var c = fila.querySelector('input[name="hilos"]');
                    if (c) { e.preventDefault(); c.checked = !c.checked; actualizar(); }
                }
            });
            // Al volver de abrir un hilo, el foco queda en su fila.
            var activa = lista.querySelector('[aria-current="true"]');
            if (activa && !document.activeElement.closest('form,input,select,textarea')) {
                activa.focus({ preventScroll: false });
            }
        }
    }

    // Iframes del cuerpo: alto según el contenido (mismo origen, sin scripts dentro).
    var ajustar = function (iframe) {
        try {
            var doc = iframe.contentDocument;
            if (doc && doc.body && doc.body.childNodes.length) {
                var alto = Math.ceil(doc.body.getBoundingClientRect().height) + 24;
                iframe.style.height = Math.max(100, alto) + 'px';
            }
        } catch (err) { /* sin acceso: queda el alto por defecto */ }
    };
    document.querySelectorAll('iframe[data-cuerpo]').forEach(function (iframe) {
        iframe.addEventListener('load', function () {
            ajustar(iframe);
            // Las imágenes cargan después: reajustar.
            try {
                iframe.contentDocument.querySelectorAll('img').forEach(function (img) {
                    img.addEventListener('load', function () { ajustar(iframe); });
                });
            } catch (err) { /* nada */ }
        });
        ajustar(iframe);
    });

    // «Mostrar imágenes»: el enlace recarga el iframe; ocultar el aviso.
    document.querySelectorAll('[data-mostrar-imagenes]').forEach(function (a) {
        a.addEventListener('click', function () {
            var aviso = a.closest('.aviso');
            window.setTimeout(function () { if (aviso) { aviso.hidden = true; } }, 0);
        });
    });

    // Avisos: se van solos.
    var avisos = document.querySelector('.avisos');
    if (avisos) { window.setTimeout(function () { avisos.classList.add('avisos--ocultar'); }, 6000); }
})();
