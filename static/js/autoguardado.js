/*
 * Guardado automático de los formularios de ensayo (HU-LIMS-26).
 *
 * Los técnicos registran desde el celular o la tablet: se acaba la batería, se
 * cierra el navegador, se pierde la señal. Cada vez que sale de un campo se
 * manda lo escrito al servidor en silencio; al volver a entrar el ensayo sigue
 * donde quedó.
 *
 *   AutoGuardado.iniciar({ form, indicador, url })
 *
 * - Se guarda al CAMBIAR un campo (al salir de él, al marcar, al elegir), no en
 *   cada tecla: así la trazabilidad no se llena de valores a medias.
 * - Si no hay señal queda «pendiente» y se reintenta solo (cada 15 s y apenas
 *   vuelve la conexión). Al cambiar de aplicación o cerrar la pestaña se
 *   intenta guardar de inmediato.
 * - Los archivos (hoja de cálculo) no se mandan: tienen su propio botón.
 * - Lo inválido lo salta el servidor y lo avisa («No se guardó: …»).
 */
(function () {
    'use strict';

    function iniciar(opciones) {
        const form = opciones.form;
        const indicador = opciones.indicador;
        const url = opciones.url || window.location.href;
        if (!form) return null;

        let temporizador = null;
        let enVuelo = false;
        let sucio = false;     // hay cambios sin confirmar
        let ultimaHora = '';

        function mostrar(texto, tono) {
            if (!indicador) return;
            indicador.textContent = texto;
            indicador.dataset.tono = tono || '';
            indicador.classList.toggle('text-green-700', tono === 'ok');
            indicador.classList.toggle('text-amber-700', tono === 'aviso');
            indicador.classList.toggle('text-red-700', tono === 'error');
            indicador.classList.toggle('text-slate-500', !tono || tono === 'trabajando');
        }

        function armar() {
            const datos = new FormData(form);
            // Los archivos no se mandan en el guardado automático.
            Array.from(datos.keys()).forEach(function (clave) {
                const valor = datos.get(clave);
                if (typeof File !== 'undefined' && valor instanceof File) datos.delete(clave);
            });
            datos.set('accion', 'autoguardar');
            datos.set('autoguardar', '1');
            return datos;
        }

        function enviar(urgente) {
            if (enVuelo) { sucio = true; return Promise.resolve(); }
            enVuelo = true;
            sucio = false;
            mostrar('Guardando…', 'trabajando');
            return fetch(url, {
                method: 'POST',
                body: armar(),
                credentials: 'same-origin',
                headers: { 'X-Requested-With': 'XMLHttpRequest' },
                keepalive: !!urgente,
            }).then(function (r) {
                return r.json().catch(function () { return { ok: false, error: 'Respuesta inesperada (' + r.status + ').' }; })
                    .then(function (res) { return { r: r, res: res }; });
            }).then(function (x) {
                if (x.r.status === 409) {
                    mostrar('Este ensayo ya está terminado; no se guardan más cambios.', 'error');
                    sucio = false;
                    return;
                }
                if (!x.res.ok) throw new Error(x.res.error || 'No se pudo guardar.');
                ultimaHora = x.res.hora || '';
                if (x.res.omitidos && x.res.omitidos.length) {
                    mostrar('Guardado a las ' + ultimaHora + '. No se guardó: ' + x.res.omitidos.join(' · '), 'aviso');
                } else {
                    mostrar('Guardado a las ' + ultimaHora, 'ok');
                }
            }).catch(function (err) {
                sucio = true;
                const sinRed = !navigator.onLine || /fetch|network|load failed/i.test(String(err && err.message));
                mostrar(sinRed ? 'Sin conexión: tus datos siguen aquí y se guardarán al volver la señal.'
                               : 'No se pudo guardar: ' + (err && err.message ? err.message : 'error'), 'error');
            }).then(function () {
                enVuelo = false;
                if (sucio && navigator.onLine) programar(1500);
            });
        }

        function programar(espera) {
            sucio = true;
            clearTimeout(temporizador);
            temporizador = setTimeout(function () { enviar(false); }, espera == null ? 500 : espera);
        }

        function alCambiar(e) {
            const t = e.target;
            if (!t || !t.name || t.type === 'file' || t.name === 'csrfmiddlewaretoken') return;
            if (t.disabled || t.readOnly) return;
            programar(500);
        }

        form.addEventListener('change', alCambiar);
        // Un campo de texto con el cursor dentro también cuenta al salir de él.
        form.addEventListener('focusout', function (e) {
            const t = e.target;
            if (t && t.name && /^(text|number|tel|date|search)$/.test(t.type || 'text') && t.dataset.autoValor !== t.value) {
                t.dataset.autoValor = t.value;
                alCambiar(e);
            }
        });
        form.addEventListener('focusin', function (e) {
            const t = e.target;
            if (t && t.name) t.dataset.autoValor = t.value;
        });

        // Al cambiar de aplicación o cerrar: guardar ya, sin esperar.
        document.addEventListener('visibilitychange', function () {
            if (document.visibilityState === 'hidden' && sucio) { clearTimeout(temporizador); enviar(true); }
        });
        window.addEventListener('pagehide', function () {
            if (sucio) { clearTimeout(temporizador); enviar(true); }
        });
        window.addEventListener('online', function () { if (sucio) programar(300); });
        setInterval(function () { if (sucio && !enVuelo && navigator.onLine) enviar(false); }, 15000);

        window.addEventListener('beforeunload', function (ev) {
            if (sucio && !enVuelo) { /* el guardado de pagehide va con keepalive */ }
            if (sucio && !navigator.onLine) { ev.preventDefault(); ev.returnValue = ''; }
        });

        return { guardarYa: function () { clearTimeout(temporizador); return enviar(false); }, hayPendientes: function () { return sucio; } };
    }

    window.AutoGuardado = { iniciar: iniciar };
})();
