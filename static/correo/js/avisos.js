/* Avisos de correo nuevo (sin dependencias; la CSP del host solo admite scripts propios).
   - Muestra el número de sin leer y lo pone en el título de la pestaña: «(3) Correo».
   - La campana abre un panel con lo pendiente: sin leer por cuenta, hilos asignados,
     envíos fallidos y borradores, cada uno con enlace a su pantalla.
   - Cuando llega un correo, suena y muestra una notificación del navegador.
   Funciona mientras la pestaña esté abierta (no es push con la pestaña cerrada). */
(function () {
    'use strict';
    var raiz = document.querySelector('[data-avisos]');
    if (!raiz) { return; }
    var url = raiz.getAttribute('data-avisos');
    var globos = document.querySelectorAll('[data-avisos-n]');
    var boton = document.querySelector('[data-avisos-sonido]');
    var abrir = document.querySelector('[data-avisos-abrir]');
    var panel = document.querySelector('[data-avisos-panel]');
    var cuerpo = document.querySelector('[data-avisos-cuerpo]');
    var globoPendientes = document.querySelector('[data-avisos-pendientes]');
    var datosPanel = null;
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
        var texto = boton.querySelector('[data-avisos-sonido-texto]');
        if (texto) { texto.textContent = activo ? 'Sonido activado' : 'Sonido silenciado'; }
    }

    // ---------- Panel de la campana ----------
    function el(etiqueta, clase, texto) {
        var n = document.createElement(etiqueta);
        if (clase) { n.className = clase; }
        if (texto !== undefined && texto !== null) { n.textContent = texto; }
        return n;
    }

    var FORMATO_HORA = { hour: '2-digit', minute: '2-digit' };
    var FORMATO_DIA = { day: '2-digit', month: 'short' };
    function cuando(iso) {
        var f = new Date(iso);
        if (isNaN(f.getTime())) { return ''; }
        var hoy = new Date();
        var mismoDia = f.toDateString() === hoy.toDateString();
        try { return f.toLocaleString('es-PE', mismoDia ? FORMATO_HORA : FORMATO_DIA); } catch (e) { return ''; }
    }

    function seccion(titulo, n, tono, filas, vacio) {
        var s = el('section', 'avisos-panel__seccion');
        var cab = el('h3', 'avisos-panel__subtitulo');
        cab.appendChild(el('span', null, titulo));
        cab.appendChild(el('span', 'contador-aviso contador-aviso--' + (n > 0 ? tono : 'cero'), String(n)));
        s.appendChild(cab);
        if (!filas.length) {
            if (vacio) { s.appendChild(el('p', 'avisos-panel__vacio', vacio)); }
            return s;
        }
        var ul = el('ul', 'avisos-panel__lista');
        filas.forEach(function (m) {
            var li = el('li');
            var a = el('a', 'aviso-fila');
            a.href = m.url;
            var linea = el('span', 'aviso-fila__linea');
            linea.appendChild(el('strong', 'aviso-fila__de', m.de));
            linea.appendChild(el('time', 'aviso-fila__hora', cuando(m.fecha)));
            a.appendChild(linea);
            a.appendChild(el('span', 'aviso-fila__asunto', m.asunto));
            a.appendChild(el('span', 'aviso-fila__cuenta', m.cuenta));
            li.appendChild(a);
            ul.appendChild(li);
        });
        s.appendChild(ul);
        if (n > filas.length) { s.appendChild(el('p', 'avisos-panel__mas', 'y ' + (n - filas.length) + ' más')); }
        return s;
    }

    function pintarPanel() {
        if (!cuerpo || !datosPanel) { return; }
        var d = datosPanel;
        var p = d.pendientes || {};
        var asignados = p.asignados || { n: 0, lista: [] };
        var fallidos = p.fallidos || { n: 0, lista: [] };
        var borradores = p.borradores || { n: 0, lista: [] };
        while (cuerpo.firstChild) { cuerpo.removeChild(cuerpo.firstChild); }

        // Resumen en cifras
        var resumen = el('div', 'avisos-resumen');
        [['Sin leer', d.total, 'azul'], ['Asignados a mí', asignados.n, 'ambar'],
         ['Envíos fallidos', fallidos.n, 'rojo'], ['Borradores', borradores.n, 'suave']].forEach(function (c) {
            var caja = el('div', 'avisos-resumen__caja avisos-resumen__caja--' + (c[1] > 0 ? c[2] : 'cero'));
            caja.appendChild(el('strong', null, String(c[1])));
            caja.appendChild(el('span', null, c[0]));
            resumen.appendChild(caja);
        });
        cuerpo.appendChild(resumen);
        if (p.en_cola) {
            cuerpo.appendChild(el('p', 'avisos-panel__nota', p.en_cola === 1 ? '1 correo saliendo (en cola de envío).' : p.en_cola + ' correos saliendo (en cola de envío).'));
        }

        // Sin leer por cuenta
        if ((d.por_cuenta || []).length > 1) {
            var cuentas = el('ul', 'avisos-cuentas');
            d.por_cuenta.forEach(function (c) {
                var li = el('li');
                var a = el('a', 'avisos-cuentas__fila');
                a.href = c.url;
                a.appendChild(el('span', null, c.nombre));
                a.appendChild(el('span', 'contador-aviso contador-aviso--' + (c.no_leidos > 0 ? 'azul' : 'cero'), String(c.no_leidos)));
                li.appendChild(a);
                cuentas.appendChild(li);
            });
            cuerpo.appendChild(cuentas);
        }

        if (fallidos.n) { cuerpo.appendChild(seccion('No se pudieron enviar', fallidos.n, 'rojo', fallidos.lista)); }
        cuerpo.appendChild(seccion('Asignados a mí', asignados.n, 'ambar', asignados.lista, 'No tienes correos asignados pendientes.'));
        cuerpo.appendChild(seccion('Sin leer', d.total, 'azul', d.sin_leer || [], 'Estás al día: no hay correos sin leer.'));
        if (borradores.n) { cuerpo.appendChild(seccion('Mis borradores', borradores.n, 'suave', borradores.lista)); }
    }

    function abrirPanel(si) {
        if (!panel || !abrir) { return; }
        panel.hidden = !si;
        abrir.setAttribute('aria-expanded', si ? 'true' : 'false');
        if (si) { pintarPanel(); consultar(); }
    }
    if (abrir && panel) {
        abrir.addEventListener('click', function () {
            abrirPanel(panel.hidden);
        });
        document.addEventListener('click', function (e) {
            if (!panel.hidden && !panel.contains(e.target) && !abrir.contains(e.target)) { abrirPanel(false); }
        });
        document.addEventListener('keydown', function (e) {
            if (e.key === 'Escape' && !panel.hidden) { abrirPanel(false); abrir.focus(); }
        });
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

    // La campana suma lo que pide atención: sin leer + asignados + envíos fallidos.
    function pintarCampana(datos) {
        var p = datos.pendientes || {};
        var asignados = (p.asignados || {}).n || 0;
        var fallidos = (p.fallidos || {}).n || 0;
        var n = (datos.total || 0) + asignados + fallidos;
        if (globoPendientes) {
            globoPendientes.textContent = n > 99 ? '99+' : String(n);
            globoPendientes.hidden = n < 1;
        }
        if (abrir) {
            var partes = [datos.total + ' sin leer'];
            if (asignados) { partes.push(asignados + ' asignados a ti'); }
            if (fallidos) { partes.push(fallidos + ' envíos fallidos'); }
            abrir.setAttribute('aria-label', 'Avisos: ' + partes.join(', '));
            abrir.title = 'Avisos: ' + partes.join(', ');
        }
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
                pintarCampana(datos);
                datosPanel = datos;
                if (panel && !panel.hidden) { pintarPanel(); }
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
