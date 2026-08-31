// Página de línea de servicio (templates/web/linea_detalle.html):
//   1) el <select> móvil navega a la línea elegida (el sidebar real de
//      escritorio ya son <a> indexables; esto es solo azúcar para lg:hidden).
//   2) "ver más" en la galería revela las miniaturas ocultas más allá de las
//      primeras 8.
//   3) lightbox: la imagen grande NO se pone en el DOM hasta que se abre —
//      el <img> del lightbox no tiene src hasta el primer clic — con
//      navegación por teclado, Escape y foco atrapado dentro del diálogo.
document.addEventListener('DOMContentLoaded', function () {
    var selectorMovil = document.getElementById('selector-lineas-movil');
    if (selectorMovil) {
        selectorMovil.addEventListener('change', function () {
            if (this.value) window.location.href = this.value;
        });
    }

    var botonVerMas = document.getElementById('btn-ver-mas-galeria');
    var galeria = document.getElementById('galeria-grid');
    if (botonVerMas && galeria) {
        botonVerMas.addEventListener('click', function () {
            galeria.querySelectorAll('.galeria-item.hidden').forEach(function (item) {
                item.classList.remove('hidden');
            });
            botonVerMas.remove();
        });
    }

    if (!galeria) return;

    var miniaturas = Array.prototype.slice.call(galeria.querySelectorAll('.galeria-item'));
    if (!miniaturas.length) return;

    var lightbox = document.getElementById('lightbox-galeria');
    var lightboxImg = document.getElementById('lightbox-galeria-img');
    var lightboxContador = document.getElementById('lightbox-galeria-contador');
    var btnCerrar = document.getElementById('lightbox-galeria-cerrar');
    var btnAnterior = document.getElementById('lightbox-galeria-anterior');
    var btnSiguiente = document.getElementById('lightbox-galeria-siguiente');
    if (!lightbox || !lightboxImg) return;

    var indiceActual = 0;
    var ultimoEnfocado = null;

    function mostrar(indice) {
        indiceActual = (indice + miniaturas.length) % miniaturas.length;
        var item = miniaturas[indiceActual];
        // Se asigna el src recién aquí: si esta foto todavía no se había
        // pedido (estaba tras "ver más" y nunca entró a viewport), el
        // navegador la descarga ahora; si ya se veía como miniatura, la sirve
        // de su propia caché HTTP — cero peso extra en ese caso.
        lightboxImg.src = item.dataset.full;
        lightboxImg.alt = item.dataset.alt;
        if (lightboxContador) {
            lightboxContador.textContent = (indiceActual + 1) + ' / ' + miniaturas.length;
        }
    }

    function abrir(indice, trigger) {
        ultimoEnfocado = trigger || document.activeElement;
        mostrar(indice);
        lightbox.classList.remove('hidden');
        lightbox.setAttribute('aria-hidden', 'false');
        document.body.style.overflow = 'hidden';
        if (btnCerrar) btnCerrar.focus();
        document.addEventListener('keydown', alManejarTeclado);
    }

    function cerrar() {
        lightbox.classList.add('hidden');
        lightbox.setAttribute('aria-hidden', 'true');
        document.body.style.overflow = '';
        lightboxImg.src = '';
        document.removeEventListener('keydown', alManejarTeclado);
        if (ultimoEnfocado && typeof ultimoEnfocado.focus === 'function') ultimoEnfocado.focus();
    }

    function siguiente() { mostrar(indiceActual + 1); }
    function anterior() { mostrar(indiceActual - 1); }

    function alManejarTeclado(event) {
        if (event.key === 'Escape') {
            cerrar();
            return;
        }
        if (event.key === 'ArrowRight') {
            siguiente();
            return;
        }
        if (event.key === 'ArrowLeft') {
            anterior();
            return;
        }
        if (event.key === 'Tab') {
            // Foco atrapado: el diálogo solo tiene 3 controles interactivos.
            var focosDelDialogo = [btnCerrar, btnAnterior, btnSiguiente].filter(Boolean);
            var indiceFoco = focosDelDialogo.indexOf(document.activeElement);
            event.preventDefault();
            var siguienteIndice;
            if (event.shiftKey) {
                siguienteIndice = indiceFoco <= 0 ? focosDelDialogo.length - 1 : indiceFoco - 1;
            } else {
                siguienteIndice = indiceFoco === focosDelDialogo.length - 1 ? 0 : indiceFoco + 1;
            }
            focosDelDialogo[siguienteIndice].focus();
        }
    }

    miniaturas.forEach(function (item, indice) {
        item.addEventListener('click', function () {
            abrir(indice, item);
        });
    });

    if (btnCerrar) btnCerrar.addEventListener('click', cerrar);
    if (btnAnterior) btnAnterior.addEventListener('click', anterior);
    if (btnSiguiente) btnSiguiente.addEventListener('click', siguiente);
    lightbox.addEventListener('click', function (event) {
        if (event.target === lightbox) cerrar();
    });
});
