// Campana de la cabecera del LIMS (templates/cabecera_base.html).
// Pide los avisos a /notificaciones/ al cargar (sin frenar la página), pone el
// contador rojo solo si hay pendientes y abre/cierra el panel al hacer clic.
(function () {
    'use strict';

    var trigger = document.getElementById('notif-trigger');
    var panel = document.getElementById('notif-panel');
    var lista = document.getElementById('notif-lista');
    var badge = document.getElementById('notif-badge');
    var cerrar = document.getElementById('notif-cerrar');
    if (!trigger || !panel || !lista) return;

    var TONOS = {
        emerald: 'bg-emerald-50 text-emerald-600 border-emerald-100',
        sky: 'bg-sky-50 text-sky-600 border-sky-100',
        rose: 'bg-rose-50 text-rose-600 border-rose-100',
        orange: 'bg-orange-50 text-orange-600 border-orange-100',
        violet: 'bg-violet-50 text-violet-600 border-violet-100',
        amber: 'bg-amber-50 text-amber-600 border-amber-100'
    };

    var cargando = null;

    function el(tag, clase, texto) {
        var n = document.createElement(tag);
        if (clase) n.className = clase;
        if (texto !== undefined) n.textContent = texto;
        return n;
    }

    function pintar(datos) {
        var total = datos.total || 0;
        if (badge) {
            badge.textContent = total > 99 ? '99+' : String(total);
            badge.classList.toggle('hidden', total === 0);
        }
        trigger.setAttribute('aria-label', total ? 'Notificaciones: ' + total + ' pendientes' : 'Notificaciones: nada pendiente');

        lista.innerHTML = '';
        if (!datos.avisos || !datos.avisos.length) {
            var vacio = el('div', 'px-5 py-8 text-center');
            vacio.appendChild(el('p', 'text-sm font-bold text-slate-600', 'Todo al día'));
            vacio.appendChild(el('p', 'text-xs text-slate-400 mt-1', 'No tienes pendientes por ahora.'));
            lista.appendChild(vacio);
            return;
        }
        datos.avisos.forEach(function (a) {
            var item = el('a', 'flex items-center gap-3 px-5 py-3 hover:bg-slate-50 transition-colors');
            item.href = a.url;
            item.setAttribute('data-aviso', a.clave);
            var icono = el('span', 'w-9 h-9 rounded-xl border flex items-center justify-center shrink-0 ' + (TONOS[a.tono] || TONOS.sky));
            var i = el('i', 'w-4 h-4');
            i.setAttribute('data-lucide', a.icono);
            icono.appendChild(i);
            var textos = el('span', 'flex-1 min-w-0');
            textos.appendChild(el('span', 'block text-[13px] font-bold text-slate-800 leading-tight', a.titulo));
            textos.appendChild(el('span', 'block text-[11px] text-slate-400 mt-0.5', a.detalle));
            var numero = el('span', 'min-w-[1.75rem] h-7 px-2 rounded-full bg-slate-900 text-white text-[11px] font-black flex items-center justify-center shrink-0', String(a.cantidad));
            item.appendChild(icono);
            item.appendChild(textos);
            item.appendChild(numero);
            lista.appendChild(item);
        });
        if (window.lucide) window.lucide.createIcons();
    }

    function error() {
        lista.innerHTML = '';
        lista.appendChild(el('p', 'px-5 py-6 text-center text-xs font-semibold text-rose-500', 'No se pudieron cargar las notificaciones. Inténtalo de nuevo.'));
    }

    function cargar() {
        cargando = fetch(trigger.getAttribute('data-url'), {
            credentials: 'same-origin',
            headers: { 'Accept': 'application/json' }
        })
            .then(function (r) { if (!r.ok) throw new Error(r.status); return r.json(); })
            .then(pintar)
            .catch(error);
        return cargando;
    }

    function abierto() { return !panel.classList.contains('hidden'); }

    function abrir() {
        panel.classList.remove('hidden');
        trigger.setAttribute('aria-expanded', 'true');
        cargar();  // siempre fresco al abrir
    }

    function cerrarPanel() {
        panel.classList.add('hidden');
        trigger.setAttribute('aria-expanded', 'false');
    }

    trigger.addEventListener('click', function (e) {
        e.stopPropagation();
        if (abierto()) cerrarPanel(); else abrir();
    });
    if (cerrar) cerrar.addEventListener('click', cerrarPanel);
    document.addEventListener('click', function (e) {
        if (abierto() && !panel.contains(e.target) && !trigger.contains(e.target)) cerrarPanel();
    });
    document.addEventListener('keydown', function (e) {
        if (e.key === 'Escape' && abierto()) { cerrarPanel(); trigger.focus(); }
    });

    cargar();
})();
