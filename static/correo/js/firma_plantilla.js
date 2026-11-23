/* Correo VICAF: formulario de la firma con plantilla. Manda el mismo formulario
   a la vista previa (iframe) mientras se escribe, y permite ampliarla o verla
   en ancho de móvil. Sin scripts en línea: la CSP del host del correo lo exige. */
(function () {
    'use strict';
    var form = document.querySelector('[data-form-plantilla]');
    if (!form) { return; }
    var vista = document.getElementById('fe-vista');
    var lienzo = document.getElementById('fe-lienzo');
    var ampliar = document.getElementById('fe-ampliar');
    var urlPrevia = form.getAttribute('data-url-previa');
    var anchos = vista.querySelectorAll('[data-ancho]');
    var temporizador = null;
    var INICIAL = { logo_ancho: '130', logo_pos: 'izquierda', color_principal: '#12306b',
                    color_acento: '#f5a623', color_panel: '#f3f6fc' };

    // Se envía el formulario completo a la vista previa y se restaura su destino.
    function actualizar() {
        var destino = form.getAttribute('target');
        var accion = form.getAttribute('action');
        form.setAttribute('target', 'firma-previa');
        form.setAttribute('action', urlPrevia);
        form.submit();
        if (destino === null) { form.removeAttribute('target'); } else { form.setAttribute('target', destino); }
        if (accion === null) { form.removeAttribute('action'); } else { form.setAttribute('action', accion); }
    }
    function programar() {
        window.clearTimeout(temporizador);
        temporizador = window.setTimeout(actualizar, 350);
    }
    form.addEventListener('input', function (e) {
        if (e.target.id === 'd-logo_ancho') { document.getElementById('o-logo_ancho').textContent = e.target.value; }
        programar();
    });
    form.addEventListener('change', programar);

    anchos.forEach(function (b) {
        if (!b.getAttribute('data-ancho')) { return; }
        b.addEventListener('click', function () {
            lienzo.style.maxWidth = b.getAttribute('data-ancho') + 'px';
            anchos.forEach(function (o) { if (o.getAttribute('data-ancho')) { o.setAttribute('aria-pressed', o === b ? 'true' : 'false'); } });
        });
    });
    lienzo.style.maxWidth = '900px';

    function alternarAmpliado(abierto) {
        vista.classList.toggle('fe__vista--ampliada', abierto);
        document.body.classList.toggle('fe-sin-scroll', abierto);
        ampliar.textContent = abierto ? 'Cerrar' : 'Ampliar';
        ampliar.setAttribute('aria-pressed', abierto ? 'true' : 'false');
    }
    ampliar.addEventListener('click', function () {
        alternarAmpliado(!vista.classList.contains('fe__vista--ampliada'));
    });
    document.addEventListener('keydown', function (e) {
        if (e.key === 'Escape' && vista.classList.contains('fe__vista--ampliada')) { alternarAmpliado(false); }
    });

    document.getElementById('fe-restablecer').addEventListener('click', function () {
        Object.keys(INICIAL).forEach(function (nombre) {
            var campo = form.elements[nombre];
            if (campo) { campo.value = INICIAL[nombre]; }
        });
        document.getElementById('o-logo_ancho').textContent = INICIAL.logo_ancho;
        programar();
    });

    actualizar();
}());
