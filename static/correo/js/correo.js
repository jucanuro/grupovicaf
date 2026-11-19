/* Correo VICAF: comportamiento de la bandeja (sin dependencias).
   Va como archivo propio porque la CSP del host no admite scripts en línea. */
(function () {
    'use strict';

    // Confirmaciones (formularios y botones con data-confirmar).
    document.addEventListener('submit', function (e) {
        var form = e.target;
        var boton = e.submitter;
        var texto = (boton && boton.dataset.confirmar) || form.dataset.confirmar;
        if (texto && !window.confirm(texto)) { e.preventDefault(); }
    });

    // Selects que se envían solos al cambiar (filtro de cuenta, mover a…).
    document.querySelectorAll('[data-autoenviar]').forEach(function (sel) {
        sel.addEventListener('change', function () {
            if (sel.value && sel.form) {
                if (sel.form.requestSubmit) { sel.form.requestSubmit(); } else { sel.form.submit(); }
            } else if (!sel.value && sel.name === 'cuenta' && sel.form) {
                sel.form.submit();
            }
        });
    });

    // Selección múltiple en la lista.
    var formLista = document.getElementById('form-lista');
    if (formLista) {
        var todos = document.querySelector('[data-seleccionar-todo]');
        // Barra de comandos: sin casillas marcadas actúa sobre el hilo abierto.
        var abierto = formLista.querySelector('[data-hilo-abierto]');
        var casillas = function () { return formLista.querySelectorAll('input[name="hilos"]'); };
        var actualizar = function () {
            var marcadas = formLista.querySelectorAll('input[name="hilos"]:checked').length;
            var inactivo = marcadas === 0 && !abierto;
            document.querySelectorAll('[data-requiere-seleccion]').forEach(function (el) {
                if (el.tagName === 'SUMMARY') {
                    el.setAttribute('aria-disabled', inactivo ? 'true' : 'false');
                    if (inactivo && el.parentNode.open) { el.parentNode.open = false; }
                } else { el.disabled = inactivo; }
            });
            if (todos) {
                todos.checked = marcadas > 0 && marcadas === casillas().length;
                todos.indeterminate = marcadas > 0 && marcadas < casillas().length;
            }
            formLista.classList.toggle('con-seleccion', marcadas > 0);
        };
        if (todos) {
            todos.addEventListener('change', function () {
                casillas().forEach(function (c) { c.checked = todos.checked; });
                actualizar();
            });
        }
        formLista.addEventListener('change', function (e) {
            if (e.target.name === 'hilos') { actualizar(); }
        });
        actualizar();

        document.addEventListener('click', function (e) {
            var resumen = e.target.closest('summary[aria-disabled="true"]');
            if (resumen) { e.preventDefault(); }
        });

        // Doble clic: pantalla completa.
        formLista.addEventListener('dblclick', function (e) {
            var fila = e.target.closest('[data-fila]');
            if (fila && !e.target.closest('.casilla')) { window.location.href = fila.dataset.urlCompleta; }
        });

        // Teclado: ↑ ↓ (o j/k) recorren, Enter abre, Mayús+Enter pantalla completa, x selecciona.
        var lista = formLista.querySelector('[data-lista]');
        if (lista) {
            lista.addEventListener('keydown', function (e) {
                var enlace = e.target.closest('.fila__enlace');
                if (!enlace) { return; }
                var enlaces = Array.prototype.slice.call(lista.querySelectorAll('.fila__enlace'));
                var i = enlaces.indexOf(enlace);
                var fila = enlace.closest('[data-fila]');
                if (e.key === 'ArrowDown' || e.key === 'j') {
                    e.preventDefault();
                    if (enlaces[i + 1]) { enlaces[i + 1].focus(); }
                } else if (e.key === 'ArrowUp' || e.key === 'k') {
                    e.preventDefault();
                    if (enlaces[i - 1]) { enlaces[i - 1].focus(); }
                } else if (e.key === 'Home') {
                    e.preventDefault(); enlaces[0].focus();
                } else if (e.key === 'End') {
                    e.preventDefault(); enlaces[enlaces.length - 1].focus();
                } else if (e.key === 'Enter' && e.shiftKey) {
                    e.preventDefault(); window.location.href = fila.dataset.urlCompleta;
                } else if (e.key === 'x') {
                    var c = fila.querySelector('input[name="hilos"]');
                    if (c) { e.preventDefault(); c.checked = !c.checked; actualizar(); }
                }
            });
            // Al volver de abrir un hilo, el foco queda en su fila.
            var activa = lista.querySelector('[aria-current="true"]');
            if (activa && !document.activeElement.closest('form,input,select,textarea')) {
                activa.focus({ preventScroll: false });
            }
        }
    }

    // Iframes del cuerpo: alto según el contenido (mismo origen, sin scripts dentro).
    var ajustar = function (iframe) {
        try {
            var doc = iframe.contentDocument;
            if (doc && doc.body && doc.body.childNodes.length) {
                var alto = Math.ceil(doc.body.getBoundingClientRect().height) + 24;
                iframe.style.height = Math.max(100, alto) + 'px';
            }
        } catch (err) { /* sin acceso: queda el alto por defecto */ }
    };
    document.querySelectorAll('iframe[data-cuerpo]').forEach(function (iframe) {
        iframe.addEventListener('load', function () {
            ajustar(iframe);
            // Las imágenes cargan después: reajustar.
            try {
                iframe.contentDocument.querySelectorAll('img').forEach(function (img) {
                    img.addEventListener('load', function () { ajustar(iframe); });
                });
            } catch (err) { /* nada */ }
        });
        ajustar(iframe);
    });

    // «Mostrar imágenes»: el enlace recarga el iframe; ocultar el aviso.
    document.querySelectorAll('[data-mostrar-imagenes]').forEach(function (a) {
        a.addEventListener('click', function () {
            var aviso = a.closest('.aviso');
            window.setTimeout(function () { if (aviso) { aviso.hidden = true; } }, 0);
        });
    });

    // Menús (Mover a, Más acciones): uno abierto a la vez; Escape o clic fuera los cierra.
    var menus = function () { return document.querySelectorAll('details[data-menu][open]'); };
    document.addEventListener('click', function (e) {
        menus().forEach(function (m) { if (!m.contains(e.target)) { m.open = false; } });
    });
    document.addEventListener('keydown', function (e) {
        if (e.key !== 'Escape') { return; }
        menus().forEach(function (m) { m.open = false; var s = m.querySelector('summary'); if (s) { s.focus(); } });
    });
    document.querySelectorAll('details[data-menu]').forEach(function (m) {
        m.addEventListener('toggle', function () {
            if (!m.open) { return; }
            menus().forEach(function (otro) { if (otro !== m) { otro.open = false; } });
            var primero = m.querySelector('.menu__item');
            if (primero) { primero.focus(); }
        });
    });

    // Panel «Detalles» de la conversación (participantes, quién lo atiende, actividad).
    // Cerrado por defecto, como en Outlook; se recuerda la preferencia en este navegador.
    var alternar = document.querySelector('[data-alternar-detalles]');
    var hilo = document.querySelector('.hilo');
    if (alternar && hilo) {
        var leer = function () { try { return window.localStorage.getItem('correo:detalles'); } catch (err) { return null; } };
        var poner = function (abierto) {
            hilo.classList.toggle('hilo--sin-detalles', !abierto);
            alternar.setAttribute('aria-expanded', abierto ? 'true' : 'false');
        };
        poner(leer() === 'abierto');
        alternar.addEventListener('click', function () {
            var abierto = alternar.getAttribute('aria-expanded') !== 'true';
            poner(abierto);
            try { window.localStorage.setItem('correo:detalles', abierto ? 'abierto' : 'cerrado'); } catch (err) { /* sin almacenamiento */ }
            if (abierto) { var lado = document.getElementById('detalles-hilo'); if (lado) { lado.scrollIntoView({ block: 'nearest' }); } }
        });
    }

    // Barra de búsqueda: sugerencias mientras se escribe (personas y correos), como Outlook.
    // Sin opción marcada, Enter hace la búsqueda completa de siempre.
    var formBusqueda = document.querySelector('form.busqueda-rapida[data-sugerencias]');
    if (formBusqueda) {
        var qInput = formBusqueda.querySelector('#q-rapida');
        var qLista = formBusqueda.querySelector('#q-rapida-lista');
        var qOpciones = [], qActiva = -1, qEspera = null, qUltima = '';
        var plano = function (c) { return c.normalize('NFD').replace(/[\u0300-\u036f]/g, '').toLowerCase(); };
        var crearEl = function (tag, attrs, texto) {
            var el = document.createElement(tag);
            Object.keys(attrs || {}).forEach(function (k) { el.setAttribute(k, attrs[k]); });
            if (texto) { el.textContent = texto; }
            return el;
        };
        // Resalta lo escrito dentro del texto (sin distinguir tildes ni mayúsculas).
        var resaltar = function (el, texto, q) {
            var chars = Array.from(texto);
            var normal = chars.map(function (c) { return plano(c).charAt(0) || c; }).join('');
            var i = q ? normal.indexOf(plano(q)) : -1;
            if (i < 0) { el.textContent = texto; return el; }
            var n = Array.from(plano(q)).length;
            el.appendChild(document.createTextNode(chars.slice(0, i).join('')));
            el.appendChild(crearEl('mark', {}, chars.slice(i, i + n).join('')));
            el.appendChild(document.createTextNode(chars.slice(i + n).join('')));
            return el;
        };
        var inicialesDe = function (o) {
            var partes = (o.nombre || o.correo).replace('@', ' ').split(/\s+/).filter(function (p) { return /^[\wÀ-ÿ]/.test(p); });
            return partes.slice(0, 2).map(function (p) { return p.charAt(0); }).join('').toUpperCase() || '?';
        };
        var qCerrar = function () {
            qLista.hidden = true; qActiva = -1;
            qInput.setAttribute('aria-expanded', 'false');
            qInput.removeAttribute('aria-activedescendant');
        };
        var qMarcar = function (i) {
            qActiva = i;
            qOpciones.forEach(function (o, j) { o.li.setAttribute('aria-selected', j === i ? 'true' : 'false'); });
            if (i >= 0) {
                qInput.setAttribute('aria-activedescendant', qOpciones[i].li.id);
                qOpciones[i].li.scrollIntoView({ block: 'nearest' });
            } else { qInput.removeAttribute('aria-activedescendant'); }
        };
        var qIr = function (o) {
            if (o.url) { window.location.href = o.url; return; }
            qCerrar();
            if (formBusqueda.requestSubmit) { formBusqueda.requestSubmit(); } else { formBusqueda.submit(); }
        };
        var qOpcion = function (li, datos) {
            li.id = 'q-rapida-op-' + qOpciones.length;
            li.setAttribute('role', 'option');
            li.setAttribute('aria-selected', 'false');
            li.addEventListener('mousedown', function (e) { e.preventDefault(); qIr(datos); });
            qOpciones.push({ li: li, url: datos.url });
            qLista.appendChild(li);
        };
        var qPintar = function (q, r) {
            qLista.textContent = ''; qOpciones = []; qActiva = -1;
            if ((r.personas || []).length) {
                qLista.appendChild(crearEl('li', { role: 'presentation', 'class': 'sugerencias__titulo' }, 'Personas'));
                r.personas.forEach(function (p) {
                    var li = crearEl('li', { 'class': 'sugerencia' });
                    li.appendChild(crearEl('span', { 'class': 'avatar avatar--' + (p.tipo || 'reciente'), 'aria-hidden': 'true' }, inicialesDe(p)));
                    var texto = crearEl('span', { 'class': 'sugerencia__texto' });
                    texto.appendChild(resaltar(crearEl('strong'), p.nombre || p.correo, q));
                    texto.appendChild(resaltar(crearEl('span', { 'class': 'mono' }), p.correo, q));
                    li.appendChild(texto);
                    if (p.detalle) { li.appendChild(crearEl('small', { 'class': 'sugerencia__detalle' }, p.detalle)); }
                    qOpcion(li, p);
                });
            }
            if ((r.correos || []).length) {
                qLista.appendChild(crearEl('li', { role: 'presentation', 'class': 'sugerencias__titulo' }, 'Correos'));
                r.correos.forEach(function (m) {
                    var li = crearEl('li', { 'class': 'sugerencia sugerencia--correo' });
                    var texto = crearEl('span', { 'class': 'sugerencia__texto' });
                    texto.appendChild(resaltar(crearEl('strong'), m.asunto, q));
                    texto.appendChild(crearEl('span', { 'class': 'sugerencia__meta' }, m.remitente + ' · ' + m.cuenta + (m.adjunto ? ' · con adjunto' : '')));
                    li.appendChild(texto);
                    li.appendChild(crearEl('small', { 'class': 'sugerencia__detalle' }, m.fecha));
                    qOpcion(li, m);
                });
            }
            var todo = crearEl('li', { 'class': 'sugerencia sugerencia--buscar' });
            todo.appendChild(crearEl('span', { 'class': 'sugerencia__texto' }, 'Buscar «' + q + '» en todo el correo'));
            todo.appendChild(crearEl('small', { 'class': 'sugerencia__detalle' }, 'Enter'));
            qOpcion(todo, {});
            qLista.hidden = false;
            qInput.setAttribute('aria-expanded', 'true');
        };
        var qBuscar = function () {
            var q = qInput.value.trim();
            if (q.length < 2) { qCerrar(); return; }
            var url = formBusqueda.dataset.sugerencias + '?q=' + encodeURIComponent(q);
            qUltima = url;
            fetch(url, { credentials: 'same-origin', headers: { 'Accept': 'application/json' } })
                .then(function (resp) { if (!resp.ok) { throw new Error(resp.status); } return resp.json(); })
                .then(function (r) {
                    if (url !== qUltima || document.activeElement !== qInput) { return; }
                    qPintar(q, r);
                })
                .catch(qCerrar);
        };
        qInput.addEventListener('input', function () {
            window.clearTimeout(qEspera);
            qEspera = window.setTimeout(qBuscar, 180);
        });
        qInput.addEventListener('focus', function () { if (qInput.value.trim().length >= 2) { qBuscar(); } });
        qInput.addEventListener('blur', function () { window.setTimeout(qCerrar, 100); });
        qInput.addEventListener('keydown', function (e) {
            var abierta = !qLista.hidden && qOpciones.length;
            if (e.key === 'ArrowDown' && abierta) { e.preventDefault(); qMarcar(Math.min(qActiva + 1, qOpciones.length - 1)); }
            else if (e.key === 'ArrowUp' && abierta) { e.preventDefault(); qMarcar(Math.max(qActiva - 1, -1)); }
            else if (e.key === 'Enter' && abierta && qActiva >= 0) { e.preventDefault(); qIr(qOpciones[qActiva]); }
            else if (e.key === 'Escape' && abierta) { e.preventDefault(); e.stopPropagation(); qCerrar(); }
        });
        formBusqueda.addEventListener('submit', function () { window.clearTimeout(qEspera); qUltima = ''; qCerrar(); });
    }

    // Avisos: se van solos.
    var avisos = document.querySelector('.avisos');
    if (avisos) { window.setTimeout(function () { avisos.classList.add('avisos--ocultar'); }, 6000); }
})();
