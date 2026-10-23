// Ensayos acreditados de /acreditacion/ (templates/web/partials/ensayos_acreditados.html,
// specs/WEB v6): buscador sobre la lista agrupada por línea.
//
// Sin JavaScript se ve la lista entera y los grupos se pliegan igual, porque
// son <details> nativos (REQ-WEB-70). Con JavaScript:
//   - se muestra el buscador (llega con `hidden`);
//   - cada tecla filtra por nombre, norma, método o línea, sin tildes ni
//     mayúsculas, oculta los grupos vacíos, abre los que tienen resultados,
//     actualiza su contador y anuncia el total (REQ-WEB-68).
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

    function textoResultados(n, total) {
        if (n === total) return 'Se muestran los ' + total + ' ensayos acreditados.';
        if (n === 0) return 'Ningún ensayo acreditado coincide.';
        if (n === 1) return '1 ensayo acreditado coincide.';
        return n + ' ensayos acreditados coinciden.';
    }

    function textoCuenta(n) {
        return n + (n === 1 ? ' ensayo' : ' ensayos');
    }

    var api = {
        normalizar: normalizar,
        coincide: coincide,
        textoResultados: textoResultados,
        textoCuenta: textoCuenta,
    };

    if (typeof module !== 'undefined' && module.exports) {
        module.exports = api;
    }
    if (!raiz || !raiz.document) return;

    raiz.document.addEventListener('DOMContentLoaded', function () {
        var seccion = raiz.document.getElementById('ensayos-acreditados');
        if (!seccion) return;

        var controles = seccion.querySelector('[data-ensayos-controles]');
        var buscador = seccion.querySelector('[data-ensayos-buscar]');
        var contador = seccion.querySelector('[data-ensayos-contador]');
        var vacio = seccion.querySelector('[data-ensayos-vacio]');
        var grupos = Array.prototype.map.call(seccion.querySelectorAll('[data-ensayos-grupo]'), function (el) {
            return {
                el: el,
                cuenta: el.querySelector('[data-ensayos-cuenta]'),
                items: Array.prototype.map.call(el.querySelectorAll('li[data-ensayo-buscar]'), function (li) {
                    return { el: li, buscar: li.getAttribute('data-ensayo-buscar') };
                }),
            };
        });
        var total = grupos.reduce(function (suma, grupo) { return suma + grupo.items.length; }, 0);
        if (!buscador || !total) return;

        function aplicar() {
            var consulta = buscador.value;
            var buscando = normalizar(consulta) !== '';
            var mostrados = 0;
            grupos.forEach(function (grupo) {
                var enGrupo = 0;
                grupo.items.forEach(function (item) {
                    var ver = coincide(item.buscar, consulta);
                    item.el.hidden = !ver;
                    if (ver) enGrupo += 1;
                });
                grupo.el.hidden = enGrupo === 0;
                // Al buscar se abren los grupos con resultados; sin búsqueda se
                // respeta lo que el visitante plegó.
                if (buscando && enGrupo) grupo.el.open = true;
                if (grupo.cuenta) grupo.cuenta.textContent = textoCuenta(enGrupo);
                mostrados += enGrupo;
            });
            if (contador) contador.textContent = textoResultados(mostrados, total);
            if (vacio) vacio.hidden = mostrados !== 0;
        }

        if (controles) controles.hidden = false;
        buscador.addEventListener('input', aplicar);
        var limpiar = seccion.querySelector('[data-ensayos-limpiar]');
        if (limpiar) {
            limpiar.addEventListener('click', function () {
                buscador.value = '';
                aplicar();
                buscador.focus();
            });
        }
    });
})(typeof window !== 'undefined' ? window : null);
