/* Avisos de correo nuevo (sin dependencias; la CSP del host solo admite scripts propios).
   - Muestra el número de sin leer y lo pone en el título de la pestaña: «(3) Correo».
   - Cuando llega un correo, suena y muestra una notificación del navegador.
   Funciona mientras la pestaña esté abierta (no es push con la pestaña cerrada). */
(function () {
    'use strict';
    var raiz = document.querySelector('[data-avisos]');
    if (!raiz) { return; }
    var url = raiz.getAttribute('data-avisos');
    var globos = document.querySelectorAll('[data-avisos-n]');
    var boton = document.querySelector('[data-avisos-sonido]');
    var tituloBase = document.title.replace(/^\(\d+\)\s*/, '');
    var CLAVE = 'vicaf_avisos_sonido';
    var activo = true;
    var ultimo = null;
    var detenido = false;
    var audio = null;

    try { activo = window.localStorage.getItem(CLAVE) !== '0'; } catch (e) { activo = true; }

    function pintarBoton() {
        if (!boton) { return; }
        boton.setAttribute('aria-pressed', activo ? 'true' : 'false');
        boton.title = activo ? 'Avisos con sonido: activados (clic para silenciar)' : 'Avisos silenciados (clic para activar)';
        var on = boton.querySelector('[data-avisos-on]');
        var off = boton.querySelector('[data-avisos-off]');
        if (on) { on.hidden = !activo; }
        if (off) { off.hidden = activo; }
    }

    // Los navegadores solo dejan sonar tras un gesto del usuario: se prepara en el primer clic o tecla.
    function prepararAudio() {
        if (audio) { return; }
        var Contexto = window.AudioContext || window.webkitAudioContext;
        if (!Contexto) { return; }
        try { audio = new Contexto(); } catch (e) { audio = null; }
    }
    ['click', 'keydown', 'touchstart'].forEach(function (nombre) {
        document.addEventListener(nombre, function () {
            prepararAudio();
            if (audio && audio.state === 'suspended') { audio.resume(); }
        }, { passive: true });
    });

    function sonar() {
        if (!audio || audio.state !== 'running') { return; }
        var t = audio.currentTime;
        [[880, 0], [1175, 0.16]].forEach(function (nota) {
            var osc = audio.createOscillator();
            var vol = audio.createGain();
            osc.type = 'sine';
            osc.frequency.value = nota[0];
            vol.gain.setValueAtTime(0.0001, t + nota[1]);
            vol.gain.exponentialRampToValueAtTime(0.25, t + nota[1] + 0.02);
            vol.gain.exponentialRampToValueAtTime(0.0001, t + nota[1] + 0.35);
            osc.connect(vol);
            vol.connect(audio.destination);
            osc.start(t + nota[1]);
            osc.stop(t + nota[1] + 0.4);
        });
    }

    function pintarNumero(total) {
        globos.forEach(function (g) {
            g.textContent = total > 99 ? '99+' : String(total);
            g.hidden = total < 1;
        });
        document.title = (total > 0 ? '(' + total + ') ' : '') + tituloBase;
    }

    function notificar(nuevos) {
        if (!activo || !nuevos.length) { return; }
        sonar();
        if (!('Notification' in window) || Notification.permission !== 'granted') { return; }
        var lista = nuevos.length > 3 ? [{ id: 'varios', cuenta: 'Correo VICAF', de: nuevos.length + ' correos nuevos', asunto: '' }] : nuevos;
        lista.forEach(function (m) {
            try {
                var n = new Notification(m.cuenta + ' · ' + m.de, { body: m.asunto, tag: 'vicaf-correo-' + m.id });
                n.onclick = function () { window.focus(); n.close(); };
            } catch (e) { /* sin notificaciones en este navegador */ }
        });
    }

    function consultar() {
        if (detenido) { return; }
        var destino = url + (ultimo === null ? '' : '?desde=' + ultimo);
        window.fetch(destino, { credentials: 'same-origin', headers: { 'Accept': 'application/json' } })
            .then(function (r) {
                if (r.status === 401 || r.status === 403) { detenido = true; return null; }
                return r.ok ? r.json() : null;
            })
            .then(function (datos) {
                if (!datos) { return; }
                pintarNumero(datos.total);
                if (ultimo !== null) { notificar(datos.nuevos || []); }
                ultimo = Math.max(ultimo || 0, datos.ultimo || 0);
            })
            .catch(function () { /* sin red: se reintenta en el siguiente ciclo */ });
    }

    if (boton) {
        boton.addEventListener('click', function () {
            activo = !activo;
            try { window.localStorage.setItem(CLAVE, activo ? '1' : '0'); } catch (e) { /* sin almacenamiento */ }
            pintarBoton();
            if (activo) {
                prepararAudio();
                if (audio && audio.state === 'suspended') { audio.resume(); }
                sonar();
                if ('Notification' in window && Notification.permission === 'default') { Notification.requestPermission(); }
            }
        });
    }
    // Pide el permiso de notificaciones una sola vez, en el primer gesto del usuario.
    document.addEventListener('click', function pedir() {
        document.removeEventListener('click', pedir);
        if (activo && 'Notification' in window && Notification.permission === 'default') { Notification.requestPermission(); }
    });

    pintarBoton();
    consultar();
    window.setInterval(consultar, 30000);
    document.addEventListener('visibilitychange', function () { if (!document.hidden) { consultar(); } });
})();
