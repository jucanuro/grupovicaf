/*
 * form_validador.js — contador de caracteres + validación en vivo para los
 * formularios de captura del LIMS. No necesita JS por formulario.
 *
 * Marcado en la plantilla:
 *
 *   <input type="text" name="razon_social"
 *          data-validar
 *          data-label="Razón social"     <!-- para los mensajes -->
 *          required                        <!-- campo obligatorio -->
 *          data-min="2"                    <!-- longitud mínima (opcional) -->
 *          maxlength="255"                 <!-- longitud máxima; alimenta el contador -->
 *          data-patron="^\d{11}$"          <!-- regex adicional (opcional) -->
 *          data-mensaje="El RUC debe tener 11 dígitos numéricos."
 *          data-tipo="email">              <!-- email | url | text (por defecto) -->
 *   <div class="campo-estado" data-for="razon_social">
 *       <span class="campo-msg" data-msg>{{ errors.razon_social }}</span>
 *       <span class="campo-contador" data-contador></span>
 *   </div>
 *
 * Comportamiento:
 *   - el contador (n/max) aparece solo con el campo enfocado;
 *   - se valida al salir del campo (blur) y, si quedó inválido, en cada tecla;
 *   - el borde del input se pone verde (válido) o rojo (inválido); si es válido
 *     y tiene contenido, un check verde reemplaza al mensaje;
 *   - al enviar, si algún campo es inválido no se envía y se enfoca el primero;
 *     antes de enfocarlo dispara `validador:rechazado` en el <form> con
 *     `detail.campo`, para que la plantilla pueda revelarlo (cambiar de pestaña,
 *     abrir un acordeón, etc.).
 *
 * El CSS (`.campo-estado`, `.campo-msg`, `.campo-contador`, `.js-input.is-*`)
 * vive en templates/base_vicafpro.html.
 *
 * Poné `novalidate` en el <form> para que este módulo controle el feedback y no
 * se solapen los globos nativos del navegador.
 */
(function () {
    'use strict';

    var RE_EMAIL = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
    var RE_URL = /^\S+\.\S{2,}$/;
    var CHECK = '✓';

    function reglas(el) {
        return {
            label: el.dataset.label || el.name || 'Este campo',
            requerido: el.hasAttribute('required'),
            min: parseInt(el.dataset.min || '0', 10),
            max: el.maxLength > 0 ? el.maxLength : null,
            patron: el.dataset.patron ? new RegExp(el.dataset.patron) : null,
            mensajePatron: el.dataset.mensaje || null,
            tipo: el.dataset.tipo || 'text'
        };
    }

    // string con el error, o null si el campo es válido
    function errorDe(el) {
        var r = reglas(el);
        var v = (el.value || '').trim();

        if (!v) return r.requerido ? r.label + ' es obligatorio.' : null;
        if (r.min && v.length < r.min) return r.label + ': mínimo ' + r.min + ' caracteres.';
        if (r.max && v.length > r.max) return r.label + ': máximo ' + r.max + ' caracteres.';
        if (r.patron && !r.patron.test(v)) return r.mensajePatron || (r.label + ' tiene un formato inválido.');
        if (r.tipo === 'email' && !RE_EMAIL.test(v)) return 'Correo electrónico inválido.';
        if (r.tipo === 'url' && !RE_URL.test(v)) return 'La URL no parece válida (ej: www.ejemplo.com).';
        return null;
    }

    function conectar(form) {
        var campos = Array.prototype.slice.call(form.querySelectorAll('[data-validar]'));
        if (!campos.length) return;

        function lineaDe(el) {
            return form.querySelector('.campo-estado[data-for="' + el.name + '"]');
        }

        function pintarContador(el) {
            var linea = lineaDe(el);
            var r = reglas(el);
            if (!linea || !r.max) return;
            var cont = linea.querySelector('[data-contador]');
            if (!cont) return;
            var n = (el.value || '').length;
            cont.textContent = n + '/' + r.max;
            var ratio = n / r.max;
            cont.dataset.nivel = ratio >= 1 ? 'over' : (ratio >= 0.8 ? 'warn' : 'ok');
        }

        // pinta el estado y devuelve true si el campo es válido
        function pintarEstado(el) {
            var linea = lineaDe(el);
            if (!linea) return true;
            var msg = linea.querySelector('[data-msg]');
            var err = errorDe(el);
            var vacio = (el.value || '').trim() === '';

            el.classList.remove('is-invalid', 'is-valid');
            linea.removeAttribute('data-tono');

            if (err) {
                el.classList.add('is-invalid');
                linea.dataset.tono = 'error';
                if (msg) msg.textContent = err;
            } else if (!vacio) {
                el.classList.add('is-valid');
                linea.dataset.tono = 'ok';
                if (msg) msg.textContent = CHECK;
            } else if (msg) {
                msg.textContent = '';
            }
            return !err;
        }

        campos.forEach(function (el) {
            var linea = lineaDe(el);
            var msg = linea && linea.querySelector('[data-msg]');
            // error ya renderizado por el servidor: dejar el campo marcado inválido
            if (msg && msg.textContent.trim() !== '') {
                el._tocado = true;
                el.classList.add('is-invalid');
                linea.dataset.tono = 'error';
            }
            pintarContador(el);

            el.addEventListener('focus', function () {
                if (linea) linea.dataset.focus = '1';
            });
            el.addEventListener('blur', function () {
                if (linea) linea.removeAttribute('data-focus');
                el._tocado = true;
                pintarEstado(el);
            });
            el.addEventListener('input', function () {
                pintarContador(el);
                if (el._tocado) pintarEstado(el);
            });
            // Los <select> envueltos por TomSelect (buscadores tipo "Cliente")
            // no reciben focus/blur nativos del elemento original — solo
            // `change`. Sin esto, esos campos no se validan hasta el submit.
            el.addEventListener('change', function () {
                el._tocado = true;
                pintarEstado(el);
            });
        });

        form.addEventListener('submit', function (e) {
            var primero = null;
            campos.forEach(function (el) {
                el._tocado = true;
                if (!pintarEstado(el) && !primero) primero = el;
            });
            if (primero) {
                e.preventDefault();
                // Corta también los otros listeners de submit del mismo form
                // (p. ej. el que hace el `fetch` de un modal AJAX), para que el
                // envío no siga adelante con datos inválidos.
                e.stopImmediatePropagation();
                // Aviso para que la plantilla pueda revelar el campo (p. ej. cambiar
                // de pestaña) antes de que le demos foco.
                form.dispatchEvent(new CustomEvent('validador:rechazado', {
                    detail: { campo: primero }
                }));
                primero.focus();
                if (primero.scrollIntoView) {
                    primero.scrollIntoView({ behavior: 'smooth', block: 'center' });
                }
            }
        });
    }

    function init() {
        var forms = [];
        document.querySelectorAll('[data-validar]').forEach(function (el) {
            if (el.form && forms.indexOf(el.form) === -1) forms.push(el.form);
        });
        forms.forEach(conectar);
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }
})();
