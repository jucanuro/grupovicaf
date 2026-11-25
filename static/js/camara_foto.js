/*
 * Cámara dentro de la página para las fotos de ensayo.
 *
 * En la PC el atributo `capture` de <input type="file"> no abre la cámara: el
 * navegador muestra el explorador de archivos (por eso «Cámara» parecía no
 * funcionar). Aquí se usa getUserMedia: vista en vivo, «Tomar foto», cambiar de
 * cámara y, en modo varias, seguir tomando sin cerrar.
 *
 * En el celular se prefiere la cámara nativa (el <input capture>), que enfoca
 * y expone mejor. Si getUserMedia no está disponible (http sin localhost,
 * permiso negado, sin cámara) se vuelve al <input capture>.
 *
 *   CamaraFoto.disponible()            -> true si se puede abrir la cámara en la página
 *   CamaraFoto.preferida()             -> true si conviene usarla (PC con cámara)
 *   CamaraFoto.abrir({ varias, titulo, alTomar(blob), alFallar(mensaje) })
 */
(function () {
    'use strict';

    let modal = null;
    let video = null;
    let flujo = null;
    let camaras = [];
    let indice = 0;
    let opciones = null;
    let tomadas = 0;

    function disponible() {
        return !!(window.isSecureContext && navigator.mediaDevices && navigator.mediaDevices.getUserMedia);
    }

    function preferida() {
        // Pantalla táctil sin puntero fino = celular/tablet: mejor la app de cámara nativa.
        const tactil = window.matchMedia && window.matchMedia('(pointer: coarse)').matches
            && !window.matchMedia('(pointer: fine)').matches;
        return disponible() && !tactil;
    }

    function crearModal() {
        if (modal) return;
        modal = document.createElement('div');
        modal.className = 'camara-modal';
        modal.setAttribute('role', 'dialog');
        modal.setAttribute('aria-modal', 'true');
        modal.setAttribute('aria-label', 'Cámara');
        modal.innerHTML =
            '<div class="camara-barra">' +
            '  <p class="camara-titulo" data-camara-titulo>Cámara</p>' +
            '  <span class="camara-contador" data-camara-contador hidden></span>' +
            '</div>' +
            '<div class="camara-vista"><video playsinline muted autoplay></video>' +
            '  <div class="camara-flash" data-camara-flash></div>' +
            '  <p class="camara-aviso" data-camara-aviso hidden></p></div>' +
            '<div class="camara-acciones">' +
            '  <button type="button" class="v-btn v-btn--oscuro" data-camara-cerrar>Cerrar</button>' +
            '  <button type="button" class="camara-disparo" data-camara-tomar aria-label="Tomar foto"><span></span></button>' +
            '  <button type="button" class="v-btn v-btn--oscuro" data-camara-cambiar hidden>Cambiar cámara</button>' +
            '</div>';
        document.body.appendChild(modal);
        video = modal.querySelector('video');
        modal.querySelector('[data-camara-cerrar]').addEventListener('click', cerrar);
        modal.querySelector('[data-camara-tomar]').addEventListener('click', tomar);
        modal.querySelector('[data-camara-cambiar]').addEventListener('click', function () {
            if (camaras.length < 2) return;
            indice = (indice + 1) % camaras.length;
            iniciar(camaras[indice].deviceId);
        });
        document.addEventListener('keydown', function (e) {
            if (!modal.classList.contains('abierto')) return;
            if (e.key === 'Escape') cerrar();
            if (e.key === ' ' || e.key === 'Enter') { e.preventDefault(); tomar(); }
        });
    }

    function detener() {
        if (flujo) flujo.getTracks().forEach(function (t) { t.stop(); });
        flujo = null;
    }

    function aviso(texto) {
        const p = modal.querySelector('[data-camara-aviso]');
        p.textContent = texto || '';
        p.hidden = !texto;
    }

    function iniciar(deviceId) {
        detener();
        const video_ = deviceId
            ? { deviceId: { exact: deviceId }, width: { ideal: 1920 }, height: { ideal: 1080 } }
            : { facingMode: { ideal: 'environment' }, width: { ideal: 1920 }, height: { ideal: 1080 } };
        return navigator.mediaDevices.getUserMedia({ video: video_, audio: false }).then(function (s) {
            flujo = s;
            video.srcObject = s;
            aviso('');
            return navigator.mediaDevices.enumerateDevices().then(function (lista) {
                camaras = lista.filter(function (d) { return d.kind === 'videoinput'; });
                modal.querySelector('[data-camara-cambiar]').hidden = camaras.length < 2;
            });
        });
    }

    function tomar() {
        if (!flujo || !video.videoWidth) return;
        const lienzo = document.createElement('canvas');
        lienzo.width = video.videoWidth;
        lienzo.height = video.videoHeight;
        lienzo.getContext('2d').drawImage(video, 0, 0);
        const flash = modal.querySelector('[data-camara-flash]');
        flash.classList.remove('activo');
        void flash.offsetWidth;
        flash.classList.add('activo');
        lienzo.toBlob(function (blob) {
            if (!blob) return;
            tomadas += 1;
            const alTomar = opciones.alTomar;
            if (opciones.varias) {
                const c = modal.querySelector('[data-camara-contador]');
                c.hidden = false;
                c.textContent = tomadas + (tomadas === 1 ? ' foto tomada' : ' fotos tomadas');
            } else {
                cerrar();
            }
            alTomar(blob);
        }, 'image/jpeg', 0.92);
    }

    function cerrar() {
        detener();
        if (modal) modal.classList.remove('abierto');
        document.body.style.overflow = '';
    }

    function abrir(o) {
        opciones = o;
        tomadas = 0;
        crearModal();
        modal.querySelector('[data-camara-titulo]').textContent = o.titulo || 'Cámara';
        modal.querySelector('[data-camara-contador]').hidden = true;
        modal.querySelector('[data-camara-cerrar]').textContent = o.varias ? 'Listo' : 'Cerrar';
        modal.classList.add('abierto');
        document.body.style.overflow = 'hidden';
        aviso('Abriendo la cámara…');
        iniciar(null).catch(function (err) {
            cerrar();
            const nombre = err && err.name;
            const mensaje = nombre === 'NotAllowedError'
                ? 'No hay permiso para usar la cámara. Actívalo en el candado de la barra de direcciones.'
                : (nombre === 'NotFoundError' || nombre === 'OverconstrainedError')
                    ? 'No se encontró ninguna cámara en este equipo.'
                    : 'No se pudo abrir la cámara.';
            if (o.alFallar) o.alFallar(mensaje);
        });
    }

    window.CamaraFoto = { disponible: disponible, preferida: preferida, abrir: abrir };
})();
