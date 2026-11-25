/*
 * Borrador local de formularios largos (HU-LIMS-27).
 *
 * Cotizaciones, recepciones de muestras, solicitudes de ensayo y datos de
 * probetas se arman en varios minutos. Si se cierra el navegador, se acaba la
 * batería o se cae la sesión, lo escrito se perdía. Este módulo guarda una copia
 * en ESTE equipo (localStorage) mientras la persona escribe y, al volver a abrir
 * la pantalla, ofrece «Restaurar» o «Descartar».
 *
 * No toca la base de datos: una cotización a medias no gasta un número de oferta
 * ni aparece en las listas. El borrador es por usuario y por pantalla, caduca a
 * los 7 días y se borra al guardar bien.
 *
 *   BorradorLocal.iniciar({
 *     form,                       // el <form>
 *     contenedores: ['#tbody'],   // zonas que el JS de la página rellena con filas: se guarda su HTML
 *     temprano: true,             // restaurar antes de que el JS de la página arranque (cotización)
 *     ajax: true,                 // el guardado es por fetch: la página llama a descartar() si salió bien
 *     scripts: {'id-script-json': 'name_del_input'},  // copia un input a un <script type=json> al restaurar
 *     alRestaurar: fn,            // para reponer lo que el JS de la página calcula (íconos, totales)
 *   })
 *   BorradorLocal.marcarCambio()  // cambios hechos por JS (sin evento input)
 *   BorradorLocal.descartar()     // borrar el borrador (guardado correcto por fetch)
 */
(function () {
    'use strict';

    const PREFIJO = 'vcf-borrador:';
    const PENDIENTE = 'vcf-borrador-pendiente';
    const FLAG = 'vcf-borrador-restaurar:';
    const CADUCA_MS = 7 * 24 * 3600 * 1000;
    const IGNORADOS = /^(submit|button|reset|file|image)$/;

    function ls() { try { return window.localStorage; } catch (e) { return null; } }
    function ss() { try { return window.sessionStorage; } catch (e) { return null; } }
    function leer(almacen, clave) { try { return almacen ? almacen.getItem(clave) : null; } catch (e) { return null; } }
    function escribir(almacen, clave, valor) { try { if (almacen) almacen.setItem(clave, valor); return true; } catch (e) { return false; } }
    function borrar(almacen, clave) { try { if (almacen) almacen.removeItem(clave); } catch (e) { /* sin almacenamiento */ } }

    function usuario() { return (document.body && document.body.dataset.usuarioId) || '0'; }
    function llaveDe(ruta) { return PREFIJO + usuario() + ':' + (ruta || window.location.pathname); }

    // --- Limpieza global (se ejecuta en cada pantalla del LIMS) --------------------
    function limpiezaGlobal() {
        const almacen = ls();
        if (!almacen) return;
        // 1. Caducados.
        try {
            const ahora = Date.now();
            for (let i = almacen.length - 1; i >= 0; i--) {
                const k = almacen.key(i);
                if (!k || k.indexOf(PREFIJO) !== 0) continue;
                let d = null;
                try { d = JSON.parse(almacen.getItem(k)); } catch (e) { d = null; }
                if (!d || !d.ts || ahora - d.ts > CADUCA_MS) almacen.removeItem(k);
            }
        } catch (e) { /* ignorar */ }
        // 2. Formularios enviados: si la página ya es otra, el guardado salió bien.
        const pendientes = leer(ss(), PENDIENTE);
        if (!pendientes) return;
        borrar(ss(), PENDIENTE);
        try {
            // Un guardado correcto termina en otra pantalla o en una redirección (el mismo
            // formulario vuelve a abrirse tras un 302). Un error de validación se vuelve a mostrar
            // sin redirección y el borrador se conserva.
            let redirecciones = 0;
            try {
                const nav = window.performance && performance.getEntriesByType && performance.getEntriesByType('navigation')[0];
                redirecciones = nav && nav.redirectCount ? nav.redirectCount : 0;
            } catch (e) { redirecciones = 0; }
            JSON.parse(pendientes).forEach(function (p) {
                if (!p || !p.llave || !p.ruta) return;
                if (p.ruta !== window.location.pathname || redirecciones > 0) borrar(almacen, p.llave);
            });
        } catch (e) { /* ignorar */ }
    }

    // --- Serializar / aplicar --------------------------------------------------------
    function zonas(form, selectores) {
        return (selectores || []).map(function (s) { return form.querySelector(s); }).filter(Boolean);
    }

    function dentroDe(el, lista) {
        return lista.some(function (z) { return z.contains(el); });
    }

    // Lo escrito vive en propiedades; innerHTML solo ve atributos: se copian antes de guardar el HTML.
    function congelar(zona) {
        zona.querySelectorAll('input, textarea, select').forEach(function (el) {
            if (el.tagName === 'SELECT') {
                Array.from(el.options).forEach(function (o) {
                    if (o.selected) o.setAttribute('selected', ''); else o.removeAttribute('selected');
                });
            } else if (el.tagName === 'TEXTAREA') {
                el.textContent = el.value;
            } else if (el.type === 'checkbox' || el.type === 'radio') {
                if (el.checked) el.setAttribute('checked', ''); else el.removeAttribute('checked');
            } else if (!IGNORADOS.test(el.type)) {
                el.setAttribute('value', el.value);
            }
        });
    }

    function serializar(form, selectores) {
        const z = zonas(form, selectores);
        const campos = [];
        Array.from(form.elements).forEach(function (el) {
            if (!el.name || el.name === 'csrfmiddlewaretoken' || IGNORADOS.test(el.type) || dentroDe(el, z)) return;
            if (el.type === 'checkbox' || el.type === 'radio') {
                campos.push({ n: el.name, t: el.type, v: el.value, c: el.checked });
            } else if (el.tagName === 'SELECT' && el.multiple) {
                campos.push({ n: el.name, t: 'multi', v: Array.from(el.selectedOptions).map(function (o) { return o.value; }) });
            } else {
                campos.push({ n: el.name, t: el.type || 'text', v: el.value });
            }
        });
        const html = z.map(function (zona) { congelar(zona); return zona.innerHTML; });
        return { campos: campos, html: html, selectores: selectores || [], ts: Date.now() };
    }

    function firma(datos) {
        return JSON.stringify([datos.campos, datos.html]);
    }

    function fijar(el, campo) {
        if (campo.t === 'checkbox' || campo.t === 'radio') { el.checked = !!campo.c; return; }
        if (campo.t === 'multi') {
            Array.from(el.options).forEach(function (o) { o.selected = campo.v.indexOf(o.value) !== -1; });
            return;
        }
        if (el.tomselect) { el.tomselect.setValue(campo.v, true); return; }  // selectores con buscador
        if (el.value !== campo.v) el.value = campo.v;
    }

    function aplicar(form, datos) {
        const z = datos.selectores.map(function (s) { return form.querySelector(s); });
        z.forEach(function (zona, i) { if (zona && datos.html[i] != null) zona.innerHTML = datos.html[i]; });
        const vivas = z.filter(Boolean);
        // Los campos se emparejan por nombre y orden de aparición.
        const porNombre = {};
        Array.from(form.elements).forEach(function (el) {
            if (!el.name || el.name === 'csrfmiddlewaretoken' || IGNORADOS.test(el.type) || dentroDe(el, vivas)) return;
            (porNombre[el.name] = porNombre[el.name] || []).push(el);
        });
        const vistos = {};
        datos.campos.forEach(function (campo) {
            const lista = porNombre[campo.n];
            if (!lista) return;
            const i = vistos[campo.n] = (vistos[campo.n] || 0) + 1;
            const el = lista[i - 1];
            if (el) fijar(el, campo);
        });
    }

    function hace(ts) {
        const min = Math.max(0, Math.round((Date.now() - ts) / 60000));
        if (min < 1) return 'hace un momento';
        if (min < 60) return 'hace ' + min + ' min';
        const h = Math.round(min / 60);
        if (h < 24) return 'hace ' + h + ' h';
        return 'hace ' + Math.round(h / 24) + ' días';
    }

    function estilos() {
        if (document.getElementById('borrador-local-estilos')) return;
        const st = document.createElement('style');
        st.id = 'borrador-local-estilos';
        st.textContent =
            '.bl-aviso{position:sticky;top:0;z-index:60;display:flex;flex-wrap:wrap;align-items:center;gap:.6rem 1rem;' +
            'padding:.7rem 1rem;margin:0 0 1rem;border-radius:.9rem;background:#fffbeb;border:1px solid #fcd34d;color:#78350f;font-size:13px;font-weight:600}' +
            '.bl-aviso b{font-weight:800}.bl-aviso span{flex:1 1 16rem}' +
            '.bl-aviso button{border:0;border-radius:.65rem;padding:.45rem .9rem;font-size:12px;font-weight:800;cursor:pointer}' +
            '.bl-aviso .bl-si{background:#0f172a;color:#fff}.bl-aviso .bl-no{background:#fff;color:#334155;box-shadow:inset 0 0 0 1px #cbd5e1}' +
            '.bl-chip{position:fixed;left:1rem;bottom:1rem;z-index:60;padding:.3rem .7rem;border-radius:999px;background:#0f172acc;' +
            'color:#fff;font-size:11px;font-weight:700;opacity:0;transition:opacity .25s;pointer-events:none}.bl-chip.visible{opacity:1}';
        document.head.appendChild(st);
    }

    // --- API ---------------------------------------------------------------------------
    let activo = null;

    function iniciar(o) {
        const form = o && o.form;
        const almacen = ls();
        if (!form || !almacen) return null;
        estilos();
        const llave = llaveDe(o.ruta);
        const selectores = o.contenedores || [];
        let temporizador = null;
        let enviado = false;
        let chip = null;
        let base = null;          // cómo quedó la pantalla al terminar de armarse (con el borrador, si se restauró)
        let personaActuo = false; // el JS de la página mueve campos al arrancar: solo cuentan los gestos de la persona

        function guardarAhora() {
            if (enviado || base === null) return;
            clearTimeout(temporizador);
            const datos = serializar(form, selectores);
            if (firma(datos) === base) return;  // nada cambió respecto a lo que cargó la página
            if (escribir(almacen, llave, JSON.stringify(datos))) {
                if (!chip) { chip = document.createElement('div'); chip.className = 'bl-chip'; document.body.appendChild(chip); }
                chip.textContent = 'Borrador guardado en este equipo · ' + new Date().toTimeString().slice(0, 5);
                chip.classList.add('visible');
                setTimeout(function () { chip.classList.remove('visible'); }, 1800);
            }
        }

        function programar() {
            if (enviado || base === null || !personaActuo) return;
            clearTimeout(temporizador);
            temporizador = setTimeout(guardarAhora, 700);
        }

        function fijarBase() {
            base = firma(serializar(form, selectores));
        }

        ['pointerdown', 'keydown', 'touchstart'].forEach(function (ev) {
            document.addEventListener(ev, function (e) { if (e.isTrusted) personaActuo = true; }, true);
        });

        function leerBorrador() {
            try { return JSON.parse(leer(almacen, llave)); } catch (e) { return null; }
        }

        function restaurar(datos) {
            aplicar(form, datos);
            Object.keys(o.scripts || {}).forEach(function (idScript) {
                const script = document.getElementById(idScript);
                const input = form.querySelector('[name="' + o.scripts[idScript] + '"]');
                if (script && input && input.value) script.textContent = input.value;
            });
            if (typeof o.alRestaurar === 'function') o.alRestaurar(datos);
        }

        function aviso(datos) {
            const barra = document.createElement('div');
            barra.className = 'bl-aviso';
            barra.setAttribute('role', 'alert');
            barra.innerHTML = '<span><b>Hay un borrador sin guardar</b> de esta pantalla (' + hace(datos.ts) +
                ', en este equipo). ¿Quieres seguir donde lo dejaste?</span>' +
                '<button type="button" class="bl-si">Restaurar borrador</button>' +
                '<button type="button" class="bl-no">Descartar</button>';
            form.parentNode.insertBefore(barra, form);
            barra.querySelector('.bl-no').addEventListener('click', function () {
                borrar(almacen, llave);
                barra.remove();
            });
            barra.querySelector('.bl-si').addEventListener('click', function () {
                if (o.temprano) {
                    // El JS de la página arma sus tablas al cargar: se recarga y se restaura antes de que arranque.
                    escribir(ss(), FLAG + llave, '1');
                    window.location.reload();
                } else {
                    restaurar(datos);
                    barra.remove();
                    programar();
                }
            });
        }

        function arrancar() {
            const datos = leerBorrador();
            if (datos && datos.campos) {
                if (leer(ss(), FLAG + llave)) {
                    borrar(ss(), FLAG + llave);
                    restaurar(datos);
                } else {
                    // Solo se ofrece si es distinto de lo que muestra la página ahora.
                    const actual = serializar(form, selectores);
                    if (firma(actual) !== firma(datos)) aviso(datos);
                }
            }
            if (!o.temprano) fijarBase();
        }

        form.addEventListener('input', programar);
        form.addEventListener('change', programar);
        form.addEventListener('submit', function (ev) {
            if (o.ajax) return;
            // Se marca como enviado solo si ningún validador frenó el envío.
            setTimeout(function () {
                if (ev.defaultPrevented) return;
                try {
                    const lista = JSON.parse(leer(ss(), PENDIENTE) || '[]');
                    lista.push({ llave: llave, ruta: window.location.pathname });
                    escribir(ss(), PENDIENTE, JSON.stringify(lista));
                } catch (e) { /* ignorar */ }
            }, 0);
        });
        document.addEventListener('visibilitychange', function () {
            if (document.visibilityState === 'hidden' && temporizador) guardarAhora();
        });
        window.addEventListener('pagehide', function () { if (temporizador) guardarAhora(); });

        activo = { guardarAhora: guardarAhora, programar: programar, descartar: function () {
            enviado = true;
            clearTimeout(temporizador);
            borrar(almacen, llave);
        } };

        // Temprano: antes de que arranque el JS de la página. Tarde: cuando ya terminó de armarse.
        if (o.temprano) {
            // Restaurar antes de que el JS de la página arme sus tablas; la base se toma cuando ya terminó.
            const restauradoYa = !!leer(ss(), FLAG + llave);
            if (restauradoYa) arrancar();
            const despues = function () { setTimeout(function () { if (!restauradoYa) arrancar(); fijarBase(); }, 0); };
            if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', despues);
            else despues();
        } else if (document.readyState === 'complete') {
            setTimeout(arrancar, 0);
        } else {
            window.addEventListener('load', function () { setTimeout(arrancar, 0); });
        }
        return activo;
    }

    window.BorradorLocal = {
        iniciar: iniciar,
        marcarCambio: function () { if (activo) activo.programar(); },
        descartar: function () { if (activo) activo.descartar(); },
    };

    limpiezaGlobal();
})();
