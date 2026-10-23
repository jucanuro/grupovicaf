// Ensayos acreditados de /acreditacion/ (templates/web/partials/ensayos_acreditados.html,
// specs/WEB v5): buscador, filtro por línea y modal con el detalle.
//
// Sin JavaScript se ven todas las cards y las que tienen ficha llevan a ella
// (REQ-WEB-61). Con JavaScript:
//   - se muestran el buscador y el filtro (llegan con `hidden`);
//   - cada tecla filtra por nombre, norma, método o línea, sin tildes ni
//     mayúsculas, oculta las líneas vacías y anuncia el conteo (REQ-WEB-56 a 58);
//   - el clic en una card abre el modal con los datos de
//     #ensayos-acreditados-datos (REQ-WEB-59).
//
// Las funciones puras se exportan en module.exports para probarlas con
// `node --test tests/js/ensayos-acreditados.test.js`.
(function (raiz) {
    'use strict';

    // Minúsculas, sin tildes ni diéresis y con los espacios colapsados.
    function normalizar(texto) {
        return String(texto || '')
            .normalize('NFD')
            .replace(/[̀-ͯ]/g, '')
            .toLowerCase()
            .replace(/\s+/g, ' ')
            .trim();
    }

    // true si todas las palabras de la consulta están en el texto. Una
    // consulta vacía coincide siempre.
    function coincide(texto, consulta) {
        var palabras = normalizar(consulta).split(' ').filter(Boolean);
        if (!palabras.length) return true;
        var base = normalizar(texto);
        return palabras.every(function (palabra) { return base.indexOf(palabra) !== -1; });
    }

    // Una card se ve si coincide con la consulta y, con una línea elegida,
    // si es de esa línea ('' = todas).
    function visible(item, consulta, linea) {
        if (linea && item.linea !== linea) return false;
        return coincide(item.buscar, consulta);
    }

    function textoResultados(n, total) {
        if (n === total) return 'Se muestran los ' + total + ' ensayos acreditados.';
        if (n === 0) return 'Ningún ensayo acreditado coincide.';
        if (n === 1) return '1 ensayo acreditado coincide.';
        return n + ' ensayos acreditados coinciden.';
    }

    // Igual que en certificaciones.js; se repite porque esta página puede no
    // cargar ese archivo (sin certificaciones publicadas).
    function siguienteFoco(total, actual, haciaAtras) {
        if (total <= 0) return -1;
        if (actual < 0 || actual >= total) return haciaAtras ? total - 1 : 0;
        if (haciaAtras) return actual === 0 ? total - 1 : actual - 1;
        return actual === total - 1 ? 0 : actual + 1;
    }

    var api = {
        normalizar: normalizar,
        coincide: coincide,
        visible: visible,
        textoResultados: textoResultados,
        siguienteFoco: siguienteFoco,
    };

    if (typeof module !== 'undefined' && module.exports) {
        module.exports = api;
    }
    if (!raiz || !raiz.document) return;

    raiz.document.addEventListener('DOMContentLoaded', function () {
        var doc = raiz.document;
        var seccion = doc.getElementById('ensayos-acreditados');
        var fuente = doc.getElementById('ensayos-acreditados-datos');
        if (!seccion || !fuente) return;

        var datos = {};
        try {
            datos = JSON.parse(fuente.textContent) || {};
        } catch (error) {
            datos = {};
        }

        // --- Buscador y filtro ---------------------------------------------
        var controles = seccion.querySelector('[data-ensayos-controles]');
        var buscador = seccion.querySelector('[data-ensayos-buscar]');
        var contador = seccion.querySelector('[data-ensayos-contador]');
        var vacio = seccion.querySelector('[data-ensayos-vacio]');
        var botonesLinea = seccion.querySelectorAll('[data-ensayos-linea]');
        var grupos = seccion.querySelectorAll('[data-ensayos-grupo]');
        var items = Array.prototype.map.call(seccion.querySelectorAll('li[data-ensayo-linea]'), function (li) {
            return { el: li, linea: li.getAttribute('data-ensayo-linea'), buscar: li.getAttribute('data-ensayo-buscar') };
        });
        var lineaActiva = '';

        function aplicar() {
            var consulta = buscador ? buscador.value : '';
            var mostrados = 0;
            items.forEach(function (item) {
                var ver = visible(item, consulta, lineaActiva);
                item.el.hidden = !ver;
                if (ver) mostrados += 1;
            });
            grupos.forEach(function (grupo) {
                var enGrupo = grupo.querySelectorAll('li[data-ensayo-linea]:not([hidden])').length;
                grupo.hidden = enGrupo === 0;
                var cuenta = grupo.querySelector('[data-ensayos-cuenta]');
                if (cuenta) cuenta.textContent = enGrupo + (enGrupo === 1 ? ' ensayo' : ' ensayos');
            });
            if (contador) contador.textContent = textoResultados(mostrados, items.length);
            if (vacio) vacio.hidden = mostrados !== 0;
        }

        function elegirLinea(clave) {
            lineaActiva = clave;
            botonesLinea.forEach(function (boton) {
                boton.setAttribute('aria-pressed', String(boton.getAttribute('data-ensayos-linea') === clave));
            });
            aplicar();
        }

        if (controles) controles.hidden = false;
        if (buscador) buscador.addEventListener('input', aplicar);
        botonesLinea.forEach(function (boton) {
            boton.addEventListener('click', function () { elegirLinea(boton.getAttribute('data-ensayos-linea')); });
        });
        var limpiar = seccion.querySelector('[data-ensayos-limpiar]');
        if (limpiar) {
            limpiar.addEventListener('click', function () {
                if (buscador) buscador.value = '';
                elegirLinea('');
                if (buscador) buscador.focus();
            });
        }

        // --- Modal ---------------------------------------------------------
        var modal = doc.getElementById('modal-ensayo');
        if (!modal) return;
        var titulo = modal.querySelector('#modal-ensayo-titulo');
        var ficha = modal.querySelector('[data-ensayo-ficha]');
        var disparador = null;

        function poner(campo, valor) {
            modal.querySelectorAll('[data-ensayo-campo="' + campo + '"]').forEach(function (el) {
                el.textContent = valor || '';
                if (campo === 'resumen' || campo === 'linea') el.hidden = !valor;
            });
        }

        function fila(nombre, mostrar) {
            var el = modal.querySelector('[data-ensayo-fila="' + nombre + '"]');
            if (el) el.classList.toggle('hidden', !mostrar);
        }

        function controlesModal() {
            return Array.prototype.filter.call(
                modal.querySelectorAll('a[href], button:not([disabled])'),
                function (el) { return el.offsetParent !== null; }
            );
        }

        function abrir(control, ensayo) {
            disparador = control;
            titulo.textContent = ensayo.nombre || 'Ensayo acreditado';
            ['linea', 'norma', 'norma_nombre', 'metodo', 'acreditacion', 'resumen'].forEach(function (campo) {
                poner(campo, ensayo[campo]);
            });
            fila('norma', ensayo.norma || ensayo.norma_nombre);
            fila('metodo', ensayo.metodo);
            // Clase y no atributo hidden: .btn-secondary define su display.
            if (ensayo.url) {
                ficha.href = ensayo.url;
                ficha.classList.remove('hidden');
            } else {
                ficha.setAttribute('href', '#');
                ficha.classList.add('hidden');
            }
            modal.classList.remove('hidden');
            modal.classList.add('flex');
            doc.body.style.overflow = 'hidden';
            var primero = modal.querySelector('[data-ensayo-cerrar]');
            if (primero) primero.focus();
        }

        function cerrar() {
            if (modal.classList.contains('hidden')) return;
            modal.classList.add('hidden');
            modal.classList.remove('flex');
            doc.body.style.overflow = '';
            if (disparador && typeof disparador.focus === 'function') disparador.focus();
            disparador = null;
        }

        seccion.querySelectorAll('[data-ensayo-open]').forEach(function (control) {
            control.addEventListener('click', function (evento) {
                var ensayo = datos[control.getAttribute('data-ensayo-open')];
                if (!ensayo) return;  // Sin datos: el enlace sigue a la ficha.
                evento.preventDefault();
                abrir(control, ensayo);
            });
        });

        modal.querySelectorAll('[data-ensayo-cerrar]').forEach(function (boton) {
            boton.addEventListener('click', cerrar);
        });

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
            var lista = controlesModal();
            var siguiente = siguienteFoco(lista.length, lista.indexOf(doc.activeElement), evento.shiftKey);
            if (siguiente < 0) return;
            evento.preventDefault();
            lista[siguiente].focus();
        });
    });
})(typeof window !== 'undefined' ? window : null);
