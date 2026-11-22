// Menú lateral del LIMS (templates/menu_lateral.html): plegar/desplegar,
// abrir/cerrar cada grupo, buscar módulo y marcar la página actual.
// Lo plegado se recuerda en el navegador (localStorage, si está disponible).
(function () {
    'use strict';

    var menu = document.getElementById('menu-lateral');
    if (!menu) return;

    var CLAVE_PLEGADO = 'vicaf.menu.plegado';
    var CLAVE_GRUPOS = 'vicaf.menu.grupos_cerrados';

    function leer(clave) { try { return window.localStorage.getItem(clave); } catch (e) { return null; } }
    function guardar(clave, valor) { try { window.localStorage.setItem(clave, valor); } catch (e) { /* sin almacenamiento */ } }

    // --- Plegar / desplegar todo el menú -------------------------------
    var boton = document.getElementById('menu-lateral-plegar');

    function plegar(plegado, persistir) {
        menu.setAttribute('data-plegado', plegado ? '1' : '0');
        if (boton) {
            boton.setAttribute('aria-expanded', plegado ? 'false' : 'true');
            boton.setAttribute('title', plegado ? 'Desplegar menú' : 'Plegar menú');
        }
        // Lucide cambia <i> por <svg>: se buscan de nuevo cada vez.
        var abierto = boton && boton.querySelector('[data-icono-abierto]');
        var cerrado = boton && boton.querySelector('[data-icono-plegado]');
        if (abierto) abierto.classList.toggle('hidden', plegado);
        if (cerrado) cerrado.classList.toggle('hidden', !plegado);
        if (persistir) guardar(CLAVE_PLEGADO, plegado ? '1' : '0');
    }

    plegar(leer(CLAVE_PLEGADO) === '1', false);
    if (boton) {
        boton.addEventListener('click', function () {
            plegar(menu.getAttribute('data-plegado') !== '1', true);
        });
    }

    // --- Grupos que se abren y cierran ----------------------------------
    var cerrados = (leer(CLAVE_GRUPOS) || '').split(',').filter(Boolean);
    menu.querySelectorAll('[data-menu-grupo]').forEach(function (grupo) {
        var nombre = grupo.getAttribute('data-menu-grupo');
        var titulo = grupo.querySelector('.menu-lateral__titulo');
        function poner(cerrado) {
            grupo.setAttribute('data-cerrado', cerrado ? '1' : '0');
            if (titulo) titulo.setAttribute('aria-expanded', cerrado ? 'false' : 'true');
        }
        poner(cerrados.indexOf(nombre) !== -1);
        if (titulo) {
            titulo.addEventListener('click', function () {
                var cerrar = grupo.getAttribute('data-cerrado') !== '1';
                poner(cerrar);
                cerrados = cerrados.filter(function (n) { return n !== nombre; });
                if (cerrar) cerrados.push(nombre);
                guardar(CLAVE_GRUPOS, cerrados.join(','));
            });
        }
    });

    // --- Página actual: el enlace con el prefijo más largo --------------
    var ruta = window.location.pathname;
    var mejor = null;
    var largo = 0;
    menu.querySelectorAll('[data-menu-item]').forEach(function (a) {
        var p = a.getAttribute('href');
        if (p && ruta.indexOf(p) === 0 && p.length > largo) { mejor = a; largo = p.length; }
    });
    if (mejor) {
        mejor.setAttribute('aria-current', 'page');
        var grupoActual = mejor.closest('[data-menu-grupo]');
        if (grupoActual) grupoActual.setAttribute('data-cerrado', '0');
    }

    // --- Buscar módulo ---------------------------------------------------
    var buscar = document.getElementById('menu-lateral-buscar');
    var vacio = document.getElementById('menu-lateral-vacio');
    function normal(t) { return (t || '').toLowerCase().normalize('NFD').replace(/[̀-ͯ]/g, ''); }
    if (buscar) {
        buscar.addEventListener('input', function () {
            var q = normal(buscar.value.trim());
            var visibles = 0;
            menu.querySelectorAll('[data-menu-grupo]').forEach(function (grupo) {
                var enGrupo = 0;
                grupo.querySelectorAll('[data-menu-item]').forEach(function (a) {
                    var ok = !q || normal(a.getAttribute('data-search')).indexOf(q) !== -1;
                    a.hidden = !ok;
                    if (ok) enGrupo += 1;
                });
                grupo.hidden = enGrupo === 0;
                if (q && enGrupo) grupo.setAttribute('data-cerrado', '0');
                visibles += enGrupo;
            });
            if (vacio) vacio.classList.toggle('hidden', visibles > 0);
        });
        buscar.addEventListener('keydown', function (e) {
            if (e.key === 'Enter') {
                var primero = menu.querySelector('[data-menu-item]:not([hidden])');
                if (primero) window.location.href = primero.getAttribute('href');
            }
        });
    }
})();
