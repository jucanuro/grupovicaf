// Modal del certificado de acreditación INACAL (templates/web/partials/modal_certificado_inacal.html).
//
// Se abre SOLO por clic. Nada de auto-open ni sessionStorage como en
// _ref/vicafpro: un modal automático es un intersticial intrusivo y penaliza
// el ranking móvil. Cualquier elemento con [data-modal-cert-open] lo dispara;
// cierra con la X, con clic en el fondo y con Escape.
document.addEventListener('DOMContentLoaded', function () {
    var modal = document.getElementById('modal-certificado-inacal');
    if (!modal) return;

    var lastFocused = null;

    function abrir(trigger) {
        lastFocused = trigger || document.activeElement;
        modal.classList.remove('hidden');
        modal.setAttribute('aria-hidden', 'false');
        document.body.style.overflow = 'hidden';
        var cerrar = modal.querySelector('[data-modal-cert-close]');
        if (cerrar) cerrar.focus();
    }

    function cerrar() {
        modal.classList.add('hidden');
        modal.setAttribute('aria-hidden', 'true');
        document.body.style.overflow = '';
        if (lastFocused && typeof lastFocused.focus === 'function') lastFocused.focus();
    }

    document.querySelectorAll('[data-modal-cert-open]').forEach(function (el) {
        el.addEventListener('click', function (event) {
            event.preventDefault();
            abrir(el);
        });
    });

    modal.querySelectorAll('[data-modal-cert-close]').forEach(function (el) {
        el.addEventListener('click', cerrar);
    });

    modal.addEventListener('click', function (event) {
        if (event.target === modal) cerrar();
    });

    document.addEventListener('keydown', function (event) {
        if (event.key === 'Escape' && !modal.classList.contains('hidden')) cerrar();
    });
});
