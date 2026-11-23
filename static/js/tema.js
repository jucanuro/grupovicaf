/* tema.js — modo claro / oscuro del LIMS y del correo (VCF-LIMS).
 *
 * Se carga SIN defer en el <head> (antes del CSS de la página se pinta) para
 * que la pantalla no parpadee en blanco al abrir en modo oscuro. Es un archivo
 * propio y no un <script> en línea porque el host del correo tiene una CSP
 * estricta (script-src 'self').
 *
 * Preferencia:
 * - Si la persona eligió un modo, se guarda en localStorage y en la cookie
 *   `vicaf_tema` (con dominio .grupovicaf.com, así laboratorio. y email. —que
 *   no comparten localStorage— recuerdan lo mismo).
 * - Si nunca eligió, se sigue el modo del sistema (prefers-color-scheme).
 *
 * Marca <html> con la clase `dark` (convención de Tailwind) y data-tema.
 * Cualquier botón con [data-tema-alternar] cambia el modo; los gráficos
 * escuchan el evento `vicaf:tema` para redibujarse.
 */
(function () {
    'use strict';

    var CLAVE = 'vicaf-tema';
    var COOKIE = 'vicaf_tema';
    var html = document.documentElement;

    function valido(v) { return v === 'claro' || v === 'oscuro'; }

    function leerCookie() {
        var m = document.cookie.match(/(?:^|;\s*)vicaf_tema=(claro|oscuro)/);
        return m ? m[1] : null;
    }

    function guardado() {
        var c = leerCookie();
        if (valido(c)) return c;
        var v = null;
        try { v = window.localStorage.getItem(CLAVE); } catch (e) { /* modo privado */ }
        return valido(v) ? v : null;
    }

    var consulta = window.matchMedia ? window.matchMedia('(prefers-color-scheme: dark)') : null;

    function delSistema() { return consulta && consulta.matches ? 'oscuro' : 'claro'; }

    function dominioCompartido() {
        var host = window.location.hostname;
        if (/^[\d.]+$/.test(host) || host.indexOf(':') !== -1) return '';
        var partes = host.split('.');
        if (partes.length < 3 || partes[partes.length - 1] === 'localhost') return '';
        return '; domain=.' + partes.slice(-2).join('.');
    }

    function guardar(tema) {
        try { window.localStorage.setItem(CLAVE, tema); } catch (e) { /* modo privado */ }
        var seguro = window.location.protocol === 'https:' ? '; Secure' : '';
        document.cookie = COOKIE + '=' + tema + '; path=/; max-age=31536000; SameSite=Lax' + dominioCompartido() + seguro;
    }

    function actualizarBotones(tema) {
        var botones = document.querySelectorAll('[data-tema-alternar]');
        var texto = tema === 'oscuro' ? 'Cambiar a modo claro' : 'Cambiar a modo oscuro';
        for (var i = 0; i < botones.length; i++) {
            botones[i].setAttribute('aria-pressed', tema === 'oscuro' ? 'true' : 'false');
            botones[i].setAttribute('aria-label', texto);
            botones[i].setAttribute('title', texto);
            var etiqueta = botones[i].querySelector('[data-tema-texto]');
            if (etiqueta) etiqueta.textContent = tema === 'oscuro' ? 'Modo claro' : 'Modo oscuro';
        }
    }

    function aplicar(tema, avisar) {
        var oscuro = tema === 'oscuro';
        html.classList.toggle('dark', oscuro);
        html.classList.toggle('light', !oscuro);
        html.setAttribute('data-tema', tema);
        actualizarBotones(tema);
        if (avisar) {
            var evento;
            try { evento = new CustomEvent('vicaf:tema', { detail: { tema: tema } }); } catch (e) {
                evento = document.createEvent('CustomEvent');
                evento.initCustomEvent('vicaf:tema', false, false, { tema: tema });
            }
            document.dispatchEvent(evento);
        }
    }

    function actual() { return html.classList.contains('dark') ? 'oscuro' : 'claro'; }

    // 1) Antes de pintar.
    aplicar(guardado() || delSistema(), false);

    // 2) Si no eligió, acompaña al sistema cuando este cambia.
    if (consulta) {
        var alCambiar = function () { if (!guardado()) aplicar(delSistema(), true); };
        if (consulta.addEventListener) consulta.addEventListener('change', alCambiar);
        else if (consulta.addListener) consulta.addListener(alCambiar);
    }

    // 3) Botones (delegado: sirve también para los que se agregan después).
    document.addEventListener('click', function (e) {
        var boton = e.target.closest ? e.target.closest('[data-tema-alternar]') : null;
        if (!boton) return;
        e.preventDefault();
        var nuevo = actual() === 'oscuro' ? 'claro' : 'oscuro';
        guardar(nuevo);
        aplicar(nuevo, true);
    });

    document.addEventListener('DOMContentLoaded', function () { actualizarBotones(actual()); });

    // Otra pestaña cambió el modo.
    window.addEventListener('storage', function (e) {
        if (e.key === CLAVE && valido(e.newValue) && e.newValue !== actual()) aplicar(e.newValue, true);
    });

    window.vicafTema = { actual: actual };
})();
