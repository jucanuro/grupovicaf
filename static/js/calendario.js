/* Calendario de actividades del LIMS (rediseño 2026-11, mockups aprobados).
 *
 * - Barra lateral: mini mes, calendarios de equipo y personales (casilla =
 *   mostrar/ocultar, se recuerda en este navegador), filtros y conteos.
 * - FullCalendar 6 en vistas compactas: bloques translúcidos con el color del
 *   calendario, título y hora; en el mes, una línea por evento.
 * - Arrastrar en la grilla abre la creación rápida; «Más opciones» abre el
 *   formulario de dos paneles (izquierda campos, derecha vista previa).
 * - Clic en un evento: tarjeta con Completar / Editar / Duplicar / Eliminar.
 *
 * Quién ve qué lo decide el servidor (actividades/visibilidad.py); aquí solo
 * se filtra lo que ya llegó.
 */
(function () {
    'use strict';

    const D = JSON.parse(document.getElementById('datos-calendario').textContent);
    const U = window.VC_URLS;
    const $ = (id) => document.getElementById(id);
    const app = $('cal-app');
    if (!app) return;

    const ESC = { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' };
    const esc = (s) => String(s == null ? '' : s).replace(/[&<>"']/g, (c) => ESC[c]);
    const ls = {
        get(k, d) { try { const v = localStorage.getItem(k); return v == null ? d : JSON.parse(v); } catch (e) { return d; } },
        set(k, v) { try { localStorage.setItem(k, JSON.stringify(v)); } catch (e) { /* sin almacenamiento */ } },
    };
    const urlCon = (plantilla, id) => plantilla.replace(/\/0\/(?!.*\/0\/)/, `/${id}/`);

    const COLORES = ['#2563eb', '#7c3aed', '#db2777', '#dc2626', '#ea580c', '#f59e0b', '#16a34a', '#0891b2', '#0d9488', '#64748b'];
    const TERMINADAS = ['COMPLETADA', 'CANCELADA'];
    const nombreDe = (lista, k) => (lista.find((x) => x[0] === k) || [k, k])[1];

    // ---------- calendarios ----------
    const SIN_CAL = { id: 0, nombre: 'Otras actividades', color: '#64748b', tipo: 'EQUIPO', miembros: 0, puede_crear: false, sin: true };
    const ENSAYOS = { id: 'ensayos', nombre: 'Ensayos del laboratorio', color: D.color_ensayos, tipo: 'EQUIPO', auto: true, puede_crear: false };
    const todosLosCalendarios = () => [...D.calendarios, ENSAYOS, SIN_CAL];
    const calendarioPorId = (id) => todosLosCalendarios().find((c) => String(c.id) === String(id)) || SIN_CAL;
    const calendariosParaCrear = () => D.calendarios.filter((c) => c.puede_crear);

    let ocultos = new Set(ls.get('vc_ocultos', []).map(String));
    let soloMios = false;
    let soloVencidas = false;
    let textoBuscar = '';
    let miniMes = new Date(new Date().getFullYear(), new Date().getMonth(), 1);

    // ---------- utilidades de fecha ----------
    const pad = (n) => String(n).padStart(2, '0');
    const hora = (d) => `${d.getHours()}:${pad(d.getMinutes())}`;
    const fechaCorta = (d) => d.toLocaleDateString('es-PE', { weekday: 'short', day: 'numeric', month: 'short' }).replace(/\./g, '');
    const fechaLarga = (d) => d.toLocaleDateString('es-PE', { weekday: 'long', day: 'numeric', month: 'long' });
    const aInputFechaHora = (d) => `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`;
    const aInputFecha = (d) => `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`;
    const mismoDia = (a, b) => a.getFullYear() === b.getFullYear() && a.getMonth() === b.getMonth() && a.getDate() === b.getDate();
    const sumarMin = (d, m) => new Date(d.getTime() + m * 60000);
    const iniciales = (n) => (n || '?').split(/\s+/).filter(Boolean).slice(0, 2).map((p) => p[0]).join('').toUpperCase();
    const colorPersona = (n) => COLORES[[...(n || '')].reduce((a, c) => a + c.charCodeAt(0), 0) % COLORES.length];

    function cuandoTexto(inicio, fin, todoElDia) {
        if (todoElDia) {
            const ultimo = fin ? sumarMin(fin, -1) : inicio;
            return mismoDia(inicio, ultimo) ? `${fechaCorta(inicio)} · todo el día` : `${fechaCorta(inicio)} – ${fechaCorta(ultimo)} · todo el día`;
        }
        if (!fin || mismoDia(inicio, fin)) return `${fechaCorta(inicio)} · ${hora(inicio)} – ${fin ? hora(fin) : ''}`;
        return `${fechaCorta(inicio)} ${hora(inicio)} – ${fechaCorta(fin)} ${hora(fin)}`;
    }

    // ---------- selector de hora (lista cada 15 min, como Google/Apple) ----------
    const PASO_MIN = 15;
    const minDelDia = (d) => d.getHours() * 60 + d.getMinutes();
    const textoHora = (min) => `${pad(Math.floor(min / 60) % 24)}:${pad(min % 60)}`;
    function textoDuracion(min) {
        if (min < 60) return `${min} min`;
        const h = Math.floor(min / 60), m = min % 60;
        return m ? `${h} h ${m} min` : `${h} h`;
    }
    // Acepta «9», «930», «9:30», «9.30», «2pm», «2:15 p. m.».
    function leerHora(txt) {
        const t = String(txt || '').toLowerCase().replace(/[\s.]/g, '');
        if (!t) return null;
        const pm = /p/.test(t), am = /a/.test(t);
        const dig = t.replace(/[^0-9:]/g, '');
        let h, m = 0;
        if (dig.includes(':')) { const p = dig.split(':'); h = Number(p[0]); m = Number(p[1] || 0); }
        else if (dig.length <= 2) h = Number(dig);
        else { h = Number(dig.slice(0, -2)); m = Number(dig.slice(-2)); }
        if (!dig || Number.isNaN(h) || Number.isNaN(m)) return null;
        if (pm && h < 12) h += 12;
        if (am && h === 12) h = 0;
        if (h > 23 || m > 59) return null;
        return h * 60 + m;
    }

    /**
     * Convierte un <input> de texto en un selector de hora: al enfocarlo abre
     * una lista (flechas, Enter, Esc) y también acepta lo que se escriba.
     * opciones() → [{min, dur?, extra}] ; elegir(opción) guarda; actual() → min.
     */
    let selectorAbierto = null;
    function selectorHora(input, { opciones, elegir, actual }) {
        const lista = document.createElement('div');
        lista.className = 'vc-horas';
        lista.hidden = true;
        lista.setAttribute('role', 'listbox');
        lista.id = `${input.id}_lista`;
        input.setAttribute('role', 'combobox');
        input.setAttribute('aria-controls', lista.id);
        input.setAttribute('aria-expanded', 'false');
        input.setAttribute('autocomplete', 'off');
        input.insertAdjacentElement('afterend', lista);
        let marcado = -1;
        let items = [];

        function pintar() {
            const sel = actual();
            items = opciones();
            lista.innerHTML = items.map((o, i) => `<button type="button" role="option" tabindex="-1" data-i="${i}"`
                + ` class="${o.min === sel ? 'sel' : ''}" aria-selected="${o.min === sel}">`
                + `<span>${textoHora(o.min)}</span>${o.extra ? `<small>${esc(o.extra)}</small>` : ''}</button>`).join('');
            marcado = items.findIndex((o) => o.min === sel);
        }
        function marcar(i, centrar) {
            const bs = lista.querySelectorAll('button');
            bs.forEach((b) => b.classList.remove('foco'));
            marcado = Math.max(0, Math.min(items.length - 1, i));
            const b = bs[marcado];
            if (!b) return;
            b.classList.add('foco');
            if (centrar) lista.scrollTop = b.offsetTop - lista.clientHeight / 2 + b.offsetHeight / 2;
            else b.scrollIntoView({ block: 'nearest' });
        }
        function abrir() {
            if (selectorAbierto && selectorAbierto !== cerrar) selectorAbierto();
            pintar();
            lista.hidden = false;
            input.setAttribute('aria-expanded', 'true');
            selectorAbierto = cerrar;
            // Sin hora elegida, se ubica en las 8:00.
            const i = marcado >= 0 ? marcado : items.findIndex((o) => o.min >= 480);
            marcar(i < 0 ? 0 : i, true);
            requestAnimationFrame(() => { input.select(); });
        }
        function cerrar() {
            lista.hidden = true;
            input.setAttribute('aria-expanded', 'false');
            if (selectorAbierto === cerrar) selectorAbierto = null;
        }
        function confirmarTexto() {
            const min = leerHora(input.value);
            if (min == null) { input.value = textoHora(actual()); return; }
            if (min !== actual()) elegir({ min }); else input.value = textoHora(min);
        }
        input.addEventListener('focus', abrir);
        input.addEventListener('click', () => { if (lista.hidden) abrir(); });
        input.addEventListener('blur', () => setTimeout(() => {
            if (lista.contains(document.activeElement)) return;
            cerrar();
            confirmarTexto();
        }, 120));
        input.addEventListener('keydown', (e) => {
            if (e.key === 'ArrowDown' || e.key === 'ArrowUp') {
                e.preventDefault();
                if (lista.hidden) abrir();
                marcar(marcado + (e.key === 'ArrowDown' ? 1 : -1));
            } else if (e.key === 'Enter') {
                e.preventDefault();
                e.stopPropagation();
                const escrito = leerHora(input.value);
                if (!lista.hidden && marcado >= 0 && (escrito == null || escrito === actual())) elegir(items[marcado]);
                else confirmarTexto();
                cerrar();
            } else if (e.key === 'Escape' && !lista.hidden) {
                e.preventDefault();
                e.stopPropagation();
                input.value = textoHora(actual());
                cerrar();
            } else if (e.key === 'Tab') {
                cerrar();
            }
        });
        input.addEventListener('input', () => {
            // Al escribir, salta a la hora más cercana de la lista.
            const min = leerHora(input.value);
            if (min == null || lista.hidden) return;
            let i = items.findIndex((o) => o.min >= min);
            if (i < 0) i = items.length - 1;
            marcar(i, true);
        });
        lista.addEventListener('mousedown', (e) => e.preventDefault());
        lista.addEventListener('click', (e) => {
            const b = e.target.closest('button[data-i]');
            if (!b) return;
            elegir(items[Number(b.dataset.i)]);
            cerrar();
        });
        return { cerrar };
    }
    const horasDelDia = () => Array.from({ length: 1440 / PASO_MIN }, (_, i) => ({ min: i * PASO_MIN }));
    // Lista del fin: desde el inicio, con la duración al lado (hasta 24 h).
    function horasDesde(inicio) {
        const base = minDelDia(inicio);
        return Array.from({ length: 1440 / PASO_MIN }, (_, i) => {
            const dur = (i + 1) * PASO_MIN;
            return { min: (base + dur) % 1440, dur, extra: textoDuracion(dur) };
        });
    }

    const fijarHora = (d, min) => { const x = new Date(d); x.setHours(Math.floor(min / 60), min % 60, 0, 0); return x; };
    // Fin a partir de una opción de la lista (con duración) o de una hora escrita.
    function finDesde(inicio, o) {
        if (o.dur != null) return sumarMin(inicio, o.dur);
        let f = fijarHora(inicio, o.min);
        if (f <= inicio) f = sumarMin(f, 1440);
        return f;
    }

    // ---------- servidor ----------
    async function enviar(url, datos) {
        let resp;
        try {
            resp = await fetch(url, {
                method: 'POST', credentials: 'same-origin',
                headers: { 'X-CSRFToken': CSRF_TOKEN, 'Content-Type': 'application/json' },
                body: JSON.stringify(datos || {}),
            });
        } catch (e) {
            return { ok: false, data: { error: 'No hay conexión con el servidor. Revisa tu internet e inténtalo de nuevo.' } };
        }
        let data = null;
        try { data = await resp.json(); } catch (e) { data = null; }
        if (!data) {
            const motivo = resp.status === 403
                ? 'Tu sesión venció o no tienes permiso. Recarga la página e inténtalo de nuevo.'
                : `El servidor respondió con un error (${resp.status}). Inténtalo de nuevo.`;
            return { ok: false, data: { error: motivo } };
        }
        return { ok: resp.ok && data.success !== false, data };
    }

    let toastTimer = null;
    function aviso(texto, accion) {
        const t = $('vc-toast');
        t.innerHTML = esc(texto) + (accion ? ` <button type="button">${esc(accion.texto)}</button>` : '');
        t.hidden = false;
        if (accion) t.querySelector('button').onclick = () => { t.hidden = true; accion.fn(); };
        clearTimeout(toastTimer);
        toastTimer = setTimeout(() => { t.hidden = true; }, accion ? 7000 : 3500);
    }

    // ---------- eventos: carga y filtros ----------
    let cache = { clave: null, datos: [] };

    function esVencida(e) {
        const p = e.extendedProps || {};
        if (p.tipo !== 'actividad' || TERMINADAS.includes(p.estado)) return false;
        return new Date(e.end || e.start) < new Date();
    }

    function filtrar(lista) {
        return lista.filter((e) => {
            const p = e.extendedProps || {};
            if (ocultos.has(String(p.calendario_id))) return false;
            if (soloMios && p.tipo === 'actividad' && !(p.participo || p.mio)) return false;
            if (soloVencidas && !esVencida(e)) return false;
            if (textoBuscar) {
                const t = `${e.title} ${p.cliente || ''} ${p.proyecto_codigo || ''} ${p.ubicacion || ''}`.toLowerCase();
                if (!t.includes(textoBuscar)) return false;
            }
            return true;
        });
    }

    function actualizarConteos() {
        const vis = filtrar(cache.datos).filter((e) => e.extendedProps.tipo === 'actividad');
        $('vc-kpi-total').textContent = vis.length;
        $('vc-kpi-hechas').textContent = vis.filter((e) => e.extendedProps.estado === 'COMPLETADA').length;
        $('vc-num-vencidas').textContent = cache.datos.filter(esVencida).length;
    }

    function cargarEventos(info, ok, falla) {
        const clave = `${info.startStr}|${info.endStr}`;
        if (cache.clave === clave) {
            ok(filtrar(cache.datos));
            actualizarConteos();
            return;
        }
        const q = new URLSearchParams({ start: info.startStr, end: info.endStr });
        fetch(`${U.eventos}?${q}`, { credentials: 'same-origin' })
            .then((r) => { if (!r.ok) throw new Error(r.status); return r.json(); })
            .then((datos) => {
                cache = { clave, datos };
                ok(filtrar(datos));
                actualizarConteos();
            })
            .catch((err) => { aviso('No se pudieron cargar las actividades. Recarga la página.'); falla(err); });
    }

    const refiltrar = () => calendar.refetchEvents();
    const recargar = () => { cache.clave = null; calendar.refetchEvents(); };

    // ---------- cómo se dibuja cada evento ----------
    const PX_POR_MIN = 22 / 30; // .fc-timegrid-slot = 22px cada 30 min

    function contenidoEvento(arg) {
        const e = arg.event;
        const p = e.extendedProps;
        const vista = arg.view.type;
        const titulo = esc(e.title);
        if (vista === 'listWeek') {
            const extra = [p.cliente, p.proyecto_codigo, calendarioPorId(p.calendario_id).nombre].filter(Boolean).map(esc).join(' · ');
            return { html: `${titulo}${extra ? ` <span class="vc-sub">· ${extra}</span>` : ''}` };
        }
        if (vista === 'dayGridMonth' && !e.allDay) {
            return { html: `<div class="vc-fila-mes"><i></i><b>${titulo}</b><small>${e.start ? hora(e.start) : ''}</small></div>` };
        }
        if (e.allDay || vista === 'dayGridMonth') {
            return { html: `<div class="vc-ev-in"><span class="vc-ev-t">${titulo}</span></div>` };
        }
        const min = e.end ? (e.end - e.start) / 60000 : 30;
        const alto = min * PX_POR_MIN;
        const rango = `${hora(e.start)}${e.end ? ` – ${hora(e.end)}` : ''}`;
        if (alto < 30) {
            return { html: `<div class="vc-ev-in"><span class="vc-ev-t">${titulo}</span> <span class="vc-ev-h">${hora(e.start)}</span></div>` };
        }
        const lineas = Math.max(1, Math.floor((alto - 16) / 13));
        return { html: `<div class="vc-ev-in" style="--lineas:${lineas}"><span class="vc-ev-t">${titulo}</span><span class="vc-ev-h">${rango}</span></div>` };
    }

    function clasesEvento(arg) {
        const e = arg.event;
        const p = e.extendedProps;
        const cls = ['vc-ev'];
        const min = e.end ? (e.end - e.start) / 60000 : 30;
        if (!e.allDay && min * PX_POR_MIN < 30) cls.push('vc-ev-corta');
        if (p.estado === 'COMPLETADA') cls.push('vc-ev-hecha');
        return cls;
    }

    function alMontarEvento(arg) {
        const e = arg.event;
        const p = e.extendedProps;
        arg.el.style.setProperty('--c', p.color || e.backgroundColor);
        arg.el.title = `${e.title}\n${e.start ? cuandoTexto(e.start, e.end, e.allDay) : ''}${p.cliente ? `\n${p.cliente}` : ''}`;
        arg.el.dataset.eventoId = e.id;
        if (!e.allDay && e.start) {
            arg.el.dataset.ini = e.start.getTime();
            arg.el.dataset.fin = (e.end || sumarMin(e.start, 30)).getTime();
            programarSolapes();
        }
    }

    // Como en el calendario de referencia: un evento largo (un ensayo de
    // varias horas) queda de fondo y las reuniones cortas que caen encima se
    // dibujan desde el 28 % del ancho, no desde la mitad, para que se lean.
    let solapesTimer = null;
    function programarSolapes() {
        clearTimeout(solapesTimer);
        solapesTimer = setTimeout(ajustarSolapes, 0);
    }
    function ajustarSolapes() {
        document.querySelectorAll('.vc-fc .fc-timegrid-col').forEach((col) => {
            const evs = [...col.querySelectorAll('.fc-timegrid-event-harness > .vc-ev[data-ini]')];
            const largos = evs.filter((el) => (el.dataset.fin - el.dataset.ini) >= 180 * 60000);
            if (!largos.length) return;
            evs.forEach((el) => {
                const harness = el.parentElement;
                const izquierda = parseFloat((harness.style.inset || '').split(' ')[3]);
                if (!(izquierda > 0) || (el.dataset.fin - el.dataset.ini) >= 180 * 60000) return;
                const pisa = largos.some((l) => Number(l.dataset.ini) < Number(el.dataset.fin) && Number(l.dataset.fin) > Number(el.dataset.ini));
                if (pisa) harness.style.left = `${Math.min(80, 28 + (izquierda - 50) * 1.44)}%`;
            });
        });
    }

    // ---------- FullCalendar ----------
    const vistaGuardada = ls.get('vc_vista', null);
    const enCelular = window.matchMedia('(max-width: 700px)').matches;
    const calendar = new FullCalendar.Calendar($('fullcalendar'), {
        locale: 'es',
        firstDay: 1,
        headerToolbar: false,
        height: '100%',
        initialView: enCelular ? 'timeGridDay' : (vistaGuardada || 'timeGridWeek'),
        nowIndicator: true,
        slotMinTime: '06:00:00',
        slotMaxTime: '22:00:00',
        scrollTime: '07:30:00',
        slotDuration: '00:30:00',
        snapDuration: '00:15:00',
        slotLabelFormat: { hour: 'numeric', minute: '2-digit', hour12: false },
        eventTimeFormat: { hour: 'numeric', minute: '2-digit', hour12: false },
        allDayText: 'todo el día',
        noEventsText: 'No hay actividades en estas fechas',
        dayMaxEvents: true,
        views: { dayGridMonth: { dayMaxEvents: 4 }, timeGrid: { dayMaxEvents: 2 } },
        moreLinkText: (n) => `+${n} más`,
        selectable: !!D.puede_crear,
        selectMirror: true,
        editable: !!D.puede_editar,
        eventDisplay: 'auto',
        dayHeaderContent: (arg) => {
            if (arg.view.type === 'dayGridMonth') return arg.text.replace('.', '');
            const dia = arg.date.toLocaleDateString('es-PE', { weekday: 'short' }).replace('.', '');
            return { html: `${esc(dia)}<b>${arg.date.getDate()}</b>` };
        },
        events: cargarEventos,
        eventContent: contenidoEvento,
        eventClassNames: clasesEvento,
        eventDidMount: alMontarEvento,
        select: (info) => abrirRapido(info),
        eventClick: (info) => { info.jsEvent.preventDefault(); abrirDetalle(info.event, info.el); },
        eventDrop: moverEvento,
        eventResize: moverEvento,
        datesSet: alCambiarFechas,
    });
    calendar.render();

    // ---------- barra superior ----------
    function alCambiarFechas(arg) {
        const v = arg.view;
        const ini = v.currentStart;
        const fin = sumarMin(v.currentEnd, -1);
        const mes = (d) => d.toLocaleDateString('es-PE', { month: 'long' });
        let titulo;
        if (v.type === 'timeGridDay') {
            titulo = `${esc(fechaLarga(ini))} <span>${ini.getFullYear()}</span>`;
        } else if (ini.getMonth() === fin.getMonth()) {
            titulo = `${esc(mes(ini))} <span>${ini.getFullYear()}</span>`;
        } else {
            titulo = `${esc(mes(ini).slice(0, 3))} – ${esc(mes(fin).slice(0, 3))} <span>${fin.getFullYear()}</span>`;
        }
        $('vc-titulo').innerHTML = titulo;
        document.querySelectorAll('.viewBtn').forEach((b) => {
            const activo = b.dataset.view === v.type;
            b.classList.toggle('activo', activo);
            b.setAttribute('aria-selected', activo ? 'true' : 'false');
        });
        if (!enCelular) ls.set('vc_vista', v.type);
        miniMes = new Date(ini.getFullYear(), ini.getMonth(), 1);
        if (v.type === 'dayGridMonth') miniMes = new Date(v.currentStart.getFullYear(), v.currentStart.getMonth(), 1);
        pintarMiniMes();
        $('vc-kpi-total-txt').textContent = v.type === 'dayGridMonth' ? 'este mes' : v.type === 'timeGridDay' ? 'este día' : 'esta semana';
    }

    $('vc-prev').onclick = () => calendar.prev();
    $('vc-next').onclick = () => calendar.next();
    $('vc-hoy').onclick = () => calendar.today();
    document.querySelectorAll('.viewBtn').forEach((b) => { b.onclick = () => calendar.changeView(b.dataset.view); });
    $('vc-buscar').addEventListener('input', (e) => { textoBuscar = e.target.value.trim().toLowerCase(); refiltrar(); });
    $('vc-solo-mios').addEventListener('change', (e) => { soloMios = e.target.checked; refiltrar(); });
    $('vc-ver-vencidas').onclick = () => {
        soloVencidas = !soloVencidas;
        $('vc-ver-vencidas').classList.toggle('activo', soloVencidas);
        $('vc-ver-vencidas').style.background = soloVencidas ? 'var(--vc-sel)' : '';
        if (soloVencidas && calendar.view.type !== 'listWeek') calendar.changeView('listWeek');
        refiltrar();
    };
    $('vc-abrir-lateral').onclick = () => app.classList.toggle('lateral-abierto');

    // ---------- mini mes ----------
    function pintarMiniMes() {
        const cont = $('vc-mini');
        const hoy = new Date();
        const v = calendar.view;
        const primero = new Date(miniMes.getFullYear(), miniMes.getMonth(), 1);
        const desde = sumarMin(primero, -((primero.getDay() + 6) % 7) * 1440);
        let h = `<div class="vc-mini-h"><span>${esc(primero.toLocaleDateString('es-PE', { month: 'long' }))} ${primero.getFullYear()}</span>`
            + '<span><button type="button" data-mini="-1" aria-label="Mes anterior">‹</button><button type="button" data-mini="1" aria-label="Mes siguiente">›</button></span></div><div class="vc-mini-g">';
        ['L', 'M', 'M', 'J', 'V', 'S', 'D'].forEach((d) => { h += `<span>${d}</span>`; });
        for (let i = 0; i < 42; i++) {
            const d = new Date(desde.getFullYear(), desde.getMonth(), desde.getDate() + i);
            const cls = [];
            if (d.getMonth() !== primero.getMonth()) cls.push('o');
            if (d >= v.currentStart && d < v.currentEnd && v.type !== 'dayGridMonth') cls.push('r');
            if (mismoDia(d, hoy)) cls.push('t');
            h += `<button type="button" class="${cls.join(' ')}" data-fecha="${aInputFecha(d)}">${d.getDate()}</button>`;
        }
        cont.innerHTML = h + '</div>';
    }
    $('vc-mini').addEventListener('click', (e) => {
        const b = e.target.closest('button');
        if (!b) return;
        if (b.dataset.mini) {
            miniMes = new Date(miniMes.getFullYear(), miniMes.getMonth() + Number(b.dataset.mini), 1);
            pintarMiniMes();
        } else if (b.dataset.fecha) {
            calendar.gotoDate(b.dataset.fecha);
            app.classList.remove('lateral-abierto');
        }
    });

    // ---------- lista de calendarios ----------
    function filaCalendario(c) {
        const id = String(c.id);
        const extra = c.auto ? 'auto' : c.tipo === 'PERSONAL' ? 'solo yo' : (c.miembros ? `${c.miembros} miembros` : 'todos');
        return `<label class="vc-cal" style="--c:${c.color}" title="${esc(c.puede_crear || c.auto || c.sin ? '' : 'Solo puedes ver este calendario')}">`
            + `<input type="checkbox" data-cal="${esc(id)}" ${ocultos.has(id) ? '' : 'checked'}><i>✓</i>`
            + `<span class="vc-cal-n">${esc(c.nombre)}</span><small>${esc(extra)}</small></label>`;
    }
    function pintarCalendarios() {
        const equipo = D.calendarios.filter((c) => c.tipo === 'EQUIPO');
        const personales = D.calendarios.filter((c) => c.tipo === 'PERSONAL');
        $('vc-cal-equipo').innerHTML = [...equipo, ENSAYOS, SIN_CAL].map(filaCalendario).join('');
        $('vc-cal-personal').innerHTML = personales.map(filaCalendario).join('');
        $('vc-personal-vacio').hidden = personales.length > 0;
    }
    $('vc-lateral').addEventListener('change', (e) => {
        const id = e.target.dataset && e.target.dataset.cal;
        if (id === undefined) return;
        if (e.target.checked) ocultos.delete(id); else ocultos.add(id);
        ls.set('vc_ocultos', [...ocultos]);
        refiltrar();
    });
    pintarCalendarios();

    // ---------- tarjetas emergentes ----------
    function colocar(pop, ancla) {
        pop.hidden = false;
        if (window.matchMedia('(max-width: 900px)').matches) return;
        const r = ancla.getBoundingClientRect ? ancla.getBoundingClientRect() : ancla;
        const w = pop.offsetWidth;
        const h = pop.offsetHeight;
        let left = r.right + 8;
        if (left + w > window.innerWidth - 8) left = r.left - w - 8;
        if (left < 8) left = Math.min(window.innerWidth - w - 8, Math.max(8, r.left));
        let top = Math.min(Math.max(8, r.top), window.innerHeight - h - 8);
        pop.style.left = `${left}px`;
        pop.style.top = `${top}px`;
    }
    function cerrarPops(conservarSeleccion) {
        $('popRapido').hidden = true;
        $('popDetalle').hidden = true;
        if (!conservarSeleccion) calendar.unselect();
    }
    document.addEventListener('mousedown', (e) => {
        if (e.target.closest('.vc-pop, .vc-modal, .fc-event, .fc-highlight, .fc-event-mirror, .fc-timegrid-slot, .fc-daygrid-day, #vc-toast')) return;
        cerrarPops();
    });

    // ---------- creación rápida ----------
    let rapido = null;
    function chipsCalendario(cont, elegido, alElegir) {
        cont.innerHTML = calendariosParaCrear().map((c) => `<button type="button" class="vc-chip${String(c.id) === String(elegido) ? ' activo' : ''}" style="--c:${c.color}" data-id="${c.id}" aria-pressed="${String(c.id) === String(elegido)}">`
            + `<i></i>${esc(c.nombre)}<small>${c.tipo === 'PERSONAL' ? 'solo yo' : 'equipo'}</small></button>`).join('');
        cont.onclick = (e) => {
            const b = e.target.closest('button[data-id]');
            if (!b) return;
            cont.querySelectorAll('button').forEach((x) => { x.classList.toggle('activo', x === b); x.setAttribute('aria-pressed', x === b); });
            alElegir(b.dataset.id);
        };
    }
    function calendarioPorDefecto() {
        const ultimo = ls.get('vc_ultimo_cal', null);
        const lista = calendariosParaCrear();
        return (lista.find((c) => String(c.id) === String(ultimo)) || lista[0] || {}).id || '';
    }

    function abrirRapido(info) {
        cerrarPops(true);
        if (!calendariosParaCrear().length) {
            abrirFormulario({ inicio: info.start, fin: info.end, todoElDia: info.allDay });
            return;
        }
        rapido = { inicio: info.start, fin: info.end, todoElDia: info.allDay, cal: calendarioPorDefecto() };
        if (info.view.type === 'dayGridMonth' && info.allDay && (info.end - info.start) <= 86400000) {
            // En el mes, un clic en un día propone 9:00–10:00 en vez de «todo el día».
            const d = new Date(info.start);
            d.setHours(9, 0, 0, 0);
            rapido = Object.assign(rapido, { inicio: d, fin: sumarMin(d, 60), todoElDia: false });
        }
        $('rapido_titulo').value = '';
        pintarRapidoHoras();
        $('rapido_error').hidden = true;
        chipsCalendario($('rapido_calendarios'), rapido.cal, (id) => { rapido.cal = id; });
        // Junto a lo que se arrastró (el bloque provisional), no donde soltó el ratón.
        colocar($('popRapido'), anclaDeFecha(info.start, info.allDay));
        $('rapido_titulo').focus();
    }

    // Horas editables en la creación rápida (en el mismo día).
    function pintarRapidoHoras() {
        const conHoras = !rapido.todoElDia && mismoDia(rapido.inicio, sumarMin(rapido.fin, -1));
        $('rapido_cuando').textContent = conHoras ? fechaCorta(rapido.inicio) : cuandoTexto(rapido.inicio, rapido.fin, rapido.todoElDia);
        $('rapido_horas').hidden = !conHoras;
        $('rapido_hi').value = textoHora(minDelDia(rapido.inicio));
        $('rapido_hf').value = textoHora(minDelDia(rapido.fin));
    }
    selectorHora($('rapido_hi'), {
        opciones: horasDelDia,
        actual: () => minDelDia(rapido.inicio),
        elegir: (o) => {
            const dur = rapido.fin - rapido.inicio;
            rapido.inicio = fijarHora(rapido.inicio, o.min);
            rapido.fin = new Date(rapido.inicio.getTime() + dur);
            pintarRapidoHoras();
        },
    });
    selectorHora($('rapido_hf'), {
        opciones: () => horasDesde(rapido.inicio),
        actual: () => minDelDia(rapido.fin),
        elegir: (o) => { rapido.fin = finDesde(rapido.inicio, o); pintarRapidoHoras(); },
    });

    function anclaDeFecha(fecha, todoElDia) {
        const dia = aInputFecha(fecha);
        const celda = (!todoElDia && document.querySelector(`.vc-fc .fc-timegrid-col[data-date="${dia}"]`))
            || document.querySelector(`.vc-fc .fc-daygrid-day[data-date="${dia}"]`);
        if (!celda) return $('fullcalendar');
        const r = celda.getBoundingClientRect();
        let top = r.top;
        if (!todoElDia && celda.classList.contains('fc-timegrid-col')) {
            const slot = document.querySelector(`.vc-fc .fc-timegrid-slot-lane[data-time="${pad(fecha.getHours())}:${pad(fecha.getMinutes() < 30 ? 0 : 30)}:00"]`);
            if (slot) top = slot.getBoundingClientRect().top - 20;
        }
        return { left: r.left, right: r.right, top };
    }

    function payloadBase(datos) {
        return Object.assign({
            clase: 'REUNION', estado: 'PROGRAMADA', prioridad: 'MEDIA', descripcion: '',
            participantes: [], recordatorios: [], es_visible: true,
        }, datos);
    }

    async function guardarRapido() {
        const titulo = $('rapido_titulo').value.trim();
        if (titulo.length < 2) {
            $('rapido_error').textContent = 'Escribe un título (mínimo 2 letras).';
            $('rapido_error').hidden = false;
            $('rapido_titulo').focus();
            return;
        }
        const boton = $('rapido_guardar');
        boton.disabled = true;
        const res = await enviar(U.guardar, payloadBase({
            titulo,
            categoria_id: rapido.cal || null,
            fecha_inicio: rapido.inicio.toISOString(),
            fecha_fin: rapido.fin.toISOString(),
            todo_el_dia: rapido.todoElDia,
            recordatorios: rapido.todoElDia ? [] : [{ minutos_antes: 30, tipo: 'APP' }],
        }));
        boton.disabled = false;
        if (!res.ok) {
            $('rapido_error').textContent = res.data.error || 'No se pudo guardar.';
            $('rapido_error').hidden = false;
            return;
        }
        ls.set('vc_ultimo_cal', rapido.cal);
        cerrarPops();
        recargar();
        aviso('Actividad creada.');
    }
    $('rapido_guardar').onclick = guardarRapido;
    $('rapido_titulo').addEventListener('keydown', (e) => { if (e.key === 'Enter') { e.preventDefault(); guardarRapido(); } });
    $('rapido_mas').onclick = () => {
        const datos = { inicio: rapido.inicio, fin: rapido.fin, todoElDia: rapido.todoElDia, titulo: $('rapido_titulo').value, categoria_id: rapido.cal };
        cerrarPops();
        abrirFormulario(datos);
    };

    // ---------- mover / estirar ----------
    async function moverEvento(info) {
        const e = info.event;
        const id = e.extendedProps.actividad_id;
        if (!id) { info.revert(); return; }
        const fin = e.end || (e.allDay ? sumarMin(e.start, 1440) : sumarMin(e.start, 60));
        const res = await enviar(urlCon(U.reprogramar, id), {
            fecha_inicio: e.start.toISOString(), fecha_fin: fin.toISOString(), todo_el_dia: e.allDay,
        });
        if (!res.ok) {
            info.revert();
            aviso(res.data.error || 'No se pudo mover la actividad.');
            return;
        }
        const antes = info.oldEvent;
        const finAntes = antes.end || (antes.allDay ? sumarMin(antes.start, 1440) : sumarMin(antes.start, 60));
        cache.clave = null;
        aviso(`«${e.title}» movida a ${cuandoTexto(e.start, fin, e.allDay)}.`, {
            texto: 'Deshacer',
            fn: async () => {
                await enviar(urlCon(U.reprogramar, id), {
                    fecha_inicio: antes.start.toISOString(), fecha_fin: finAntes.toISOString(), todo_el_dia: antes.allDay,
                });
                recargar();
            },
        });
    }

    // ---------- tarjeta del evento ----------
    let detalleActual = null;
    async function abrirDetalle(ev, el) {
        cerrarPops();
        const p = ev.extendedProps;
        const pop = $('popDetalle');
        const cuerpo = $('popDetalleCuerpo');
        const cal = calendarioPorId(p.calendario_id);
        const cabecera = (titulo, sub) => `<div class="vc-det-hd" style="--c:${p.color || cal.color}"><i></i><div><h4>${esc(titulo)}</h4><p>${esc(sub)}</p></div>`
            + '<button type="button" class="vc-icono" data-cerrar-pop aria-label="Cerrar" style="margin-left:auto">✕</button></div>';
        const linea = (icono, html) => (html ? `<div class="vc-det-l"><span>${icono}</span><span>${html}</span></div>` : '');

        if (p.tipo === 'ensayo') {
            cuerpo.innerHTML = cabecera(ev.title, `${fechaCorta(ev.start)} · ${cal.nombre}`)
                + linea('🧪', esc(p.servicio)) + linea('🏷', `${esc(p.codigo_solicitud)} · <span class="vc-badge">${esc(p.estado)}</span>`)
                + linea('🏢', esc(p.cliente)) + linea('👤', esc(p.responsable))
                + (p.solicitud_id ? `<div class="vc-acts"><a href="${esc(urlCon(U.solicitud, p.solicitud_id))}">Abrir solicitud ↗</a></div>` : '');
            colocar(pop, el);
            return;
        }

        cuerpo.innerHTML = cabecera(ev.title, `${cuandoTexto(ev.start, ev.end, ev.allDay)} · ${cal.nombre}`) + '<p class="vc-sub">Cargando…</p>';
        colocar(pop, el);
        let d;
        try {
            const r = await fetch(urlCon(U.detalle, p.actividad_id), { credentials: 'same-origin' });
            if (!r.ok) throw new Error(r.status);
            d = await r.json();
        } catch (e) {
            cuerpo.innerHTML = cabecera(ev.title, 'No se pudo cargar el detalle.');
            return;
        }
        detalleActual = d;
        const personas = d.participantes.length
            ? d.participantes.map((x) => esc(x.nombre) + (x.rol === 'RESPONSABLE' ? ' <span class="vc-badge">responsable</span>' : '')).join(', ')
            : `Sin participantes · lo ven todos en «${esc(d.calendario_nombre || 'Otras actividades')}»`;
        const enlace = d.enlace_externo && /^https?:\/\//i.test(d.enlace_externo)
            ? ` · <a class="vc-link" href="${esc(d.enlace_externo)}" target="_blank" rel="noopener noreferrer">Abrir enlace ↗</a>` : '';
        const avisoTxt = d.aviso_cliente_enviado_en ? ` · aviso enviado ${esc(fechaCorta(new Date(d.aviso_cliente_enviado_en)))}` : '';
        let acciones = '';
        if (d.puede_editar && !TERMINADAS.includes(d.estado)) acciones += '<button type="button" class="vc-ok-btn" data-accion="completar">✓ Completar</button>';
        if (d.puede_editar) acciones += '<button type="button" data-accion="editar">✎ Editar</button>';
        if (D.puede_crear && calendariosParaCrear().length) acciones += '<button type="button" data-accion="duplicar">⧉ Duplicar</button>';
        if (d.puede_eliminar) acciones += '<button type="button" class="vc-peligro" data-accion="eliminar" aria-label="Eliminar">🗑</button>';
        cuerpo.innerHTML = cabecera(d.titulo, `${cuandoTexto(new Date(d.fecha_inicio), new Date(d.fecha_fin), d.todo_el_dia)} · ${d.calendario_nombre || 'Otras actividades'}`)
            + linea('👥', personas)
            + linea('🏷', `${esc(nombreDe(D.clases, d.clase))} · prioridad ${esc(nombreDe(D.prioridades, d.prioridad).toLowerCase())} · <span class="vc-badge">${esc(nombreDe(D.estados, d.estado))}</span>`)
            + linea('🏢', d.cliente_nombre ? `${esc(d.cliente_nombre)}${avisoTxt}` : 'Sin cliente · actividad interna')
            + linea('📁', esc(d.proyecto_nombre))
            + linea('📍', (d.ubicacion || enlace) ? `${esc(d.ubicacion || '')}${enlace}` : '')
            + linea('📝', esc(d.descripcion))
            + linea('✍', `Creada por ${esc(d.creado_por)}`)
            + (acciones ? `<div class="vc-acts">${acciones}</div>` : '');
        colocar(pop, el);
    }

    $('popDetalle').addEventListener('click', async (e) => {
        if (e.target.closest('[data-cerrar-pop]')) { cerrarPops(); return; }
        const b = e.target.closest('[data-accion]');
        if (!b || !detalleActual) return;
        const d = detalleActual;
        if (b.dataset.accion === 'editar') { cerrarPops(); abrirFormulario({ detalle: d }); }
        if (b.dataset.accion === 'duplicar') { cerrarPops(); abrirFormulario({ detalle: d, duplicar: true }); }
        if (b.dataset.accion === 'completar') {
            b.disabled = true;
            const res = await enviar(U.guardar, payloadDesdeDetalle(d, { estado: 'COMPLETADA' }));
            if (!res.ok) { b.disabled = false; aviso(res.data.error || 'No se pudo completar.'); return; }
            cerrarPops();
            recargar();
            aviso(`«${d.titulo}» completada.`);
        }
        if (b.dataset.accion === 'eliminar') {
            if (!b.dataset.confirmar) {
                b.dataset.confirmar = '1';
                b.textContent = '¿Eliminar? Sí';
                return;
            }
            const res = await enviar(urlCon(U.eliminar, d.id), {});
            if (!res.ok) { aviso(res.data.error || 'No se pudo eliminar.'); return; }
            cerrarPops();
            recargar();
            aviso(`«${d.titulo}» eliminada.`);
        }
    });

    function payloadDesdeDetalle(d, cambios) {
        return Object.assign({
            id: d.id, titulo: d.titulo, descripcion: d.descripcion, clase: d.clase, estado: d.estado,
            prioridad: d.prioridad, fecha_inicio: d.fecha_inicio, fecha_fin: d.fecha_fin,
            todo_el_dia: d.todo_el_dia, bloquea_agenda: d.bloquea_agenda, es_visible: d.es_visible,
            ubicacion: d.ubicacion, enlace_externo: d.enlace_externo, observaciones: d.observaciones,
            categoria_id: d.categoria_id, cliente_id: d.cliente_id, cliente_nombre_manual: d.cliente_nombre_manual,
            proyecto_id: d.proyecto_id,
            participantes: d.participantes.map((x) => ({ trabajador_id: x.trabajador_id, rol: x.rol, confirmado: x.confirmado, comentario: x.comentario })),
            recordatorios: d.recordatorios.map((r) => ({ minutos_antes: r.minutos_antes, tipo: r.tipo })),
            avisar_cliente: false,
        }, cambios || {});
    }

    // ---------- formulario de dos paneles ----------
    const F = {
        modal: $('modalFormulario'), titulo: $('titulo'), inicio: $('fecha_inicio'), fin: $('fecha_fin'),
        todoElDia: $('todo_el_dia'), clase: $('clase'), estado: $('estado'), proyecto: $('proyecto_id'),
        clienteBuscar: $('cliente_buscar'), clienteId: $('cliente_id'), clienteManual: $('cliente_nombre_manual'),
        avisar: $('avisar_cliente'), error: $('form_error'),
    };
    const form = { cal: '', prioridad: 'MEDIA', participantes: [], cliente: null, detalle: null };

    F.clase.innerHTML = D.clases.map(([v, t]) => `<option value="${esc(v)}">${esc(t)}</option>`).join('');
    F.estado.innerHTML = D.estados.map(([v, t]) => `<option value="${esc(v)}">${esc(t)}</option>`).join('');
    F.proyecto.insertAdjacentHTML('beforeend', D.proyectos.map((p) => `<option value="${p.id}">${esc(p.codigo_proyecto)} · ${esc(p.nombre_proyecto)}</option>`).join(''));
    $('lista_trabajadores').innerHTML = D.trabajadores.map((t) => `<option value="${esc(t.nombre)}"></option>`).join('');
    $('lista_clientes').innerHTML = D.clientes.map((c) => `<option value="${esc(c.razon_social)}${c.correo_contacto ? ` — ${esc(c.correo_contacto)}` : ''}"></option>`).join('');
    if (!D.ve_todos) {
        F.clienteBuscar.closest('.vc-tags').hidden = true;
        F.clienteManual.hidden = false;
        F.clienteManual.placeholder = 'Nombre del cliente (opcional)';
    }

    const seg = $('prioridad_seg');
    seg.innerHTML = D.prioridades.map(([v, t]) => `<button type="button" data-v="${esc(v)}" role="radio">${esc(t)}</button>`).join('');
    seg.onclick = (e) => { const b = e.target.closest('button'); if (b) { form.prioridad = b.dataset.v; pintarPrioridad(); actualizarVista(); } };
    function pintarPrioridad() { seg.querySelectorAll('button').forEach((b) => { const a = b.dataset.v === form.prioridad; b.classList.toggle('activo', a); b.setAttribute('aria-checked', a); }); }

    // Los campos ocultos #fecha_inicio/#fecha_fin guardan el valor; lo visible es
    // fecha + hora (lista cada 15 min) de inicio y de fin.
    const V = { fiDia: $('fi_dia'), fiHora: $('fi_hora'), ffDia: $('ff_dia'), ffHora: $('ff_hora') };
    function ponerFechas(inicio, fin, todoElDia) {
        F.todoElDia.checked = !!todoElDia;
        if (todoElDia) {
            F.inicio.value = aInputFecha(inicio);
            F.fin.value = aInputFecha(sumarMin(fin || sumarMin(inicio, 1440), -1));
        } else {
            F.inicio.value = aInputFechaHora(inicio);
            F.fin.value = aInputFechaHora(fin || sumarMin(inicio, 60));
        }
        pintarCuando();
    }
    function leerFechas() {
        if (!F.inicio.value || !F.fin.value) return null;
        if (F.todoElDia.checked) {
            const i = new Date(`${F.inicio.value}T00:00`);
            const f = new Date(`${F.fin.value}T00:00`);
            return { inicio: i, fin: sumarMin(f, 1440), todoElDia: true };
        }
        return { inicio: new Date(F.inicio.value), fin: new Date(F.fin.value), todoElDia: false };
    }
    function pintarCuando() {
        const f = leerFechas();
        const todo = F.todoElDia.checked;
        F.modal.querySelectorAll('[data-solo-hora]').forEach((el) => { el.hidden = todo; });
        if (!f) return;
        V.fiDia.value = aInputFecha(f.inicio);
        V.ffDia.value = aInputFecha(todo ? sumarMin(f.fin, -1) : f.fin);
        V.fiHora.value = textoHora(minDelDia(f.inicio));
        V.ffHora.value = textoHora(minDelDia(f.fin));
        // La fecha de fin solo se muestra si es otro día (como Google).
        V.ffDia.classList.toggle('vc-tenue', !todo && mismoDia(f.inicio, f.fin));
    }
    function fijarFechas(inicio, fin) {
        if (F.todoElDia.checked) ponerFechas(inicio, sumarMin(fin, 1440), true);
        else ponerFechas(inicio, fin, false);
        actualizarVista();
    }
    const diaDe = (valor, base) => {
        if (!valor) return null;
        const d = new Date(`${valor}T00:00`);
        d.setHours(base.getHours(), base.getMinutes(), 0, 0);
        return d;
    };
    V.fiDia.addEventListener('change', () => {
        // Mover el inicio arrastra el fin: se conserva la duración.
        const f = leerFechas(); const i = f && diaDe(V.fiDia.value, f.inicio);
        if (!i) return pintarCuando();
        const dur = f.fin - f.inicio;
        fijarFechas(i, new Date(i.getTime() + (F.todoElDia.checked ? dur - 86400000 : dur)));
    });
    V.ffDia.addEventListener('change', () => {
        const f = leerFechas(); let fin = f && diaDe(V.ffDia.value, F.todoElDia.checked ? f.inicio : f.fin);
        if (!fin) return pintarCuando();
        if (fin < f.inicio) fin = F.todoElDia.checked ? new Date(f.inicio) : sumarMin(f.inicio, 60);
        fijarFechas(f.inicio, fin);
    });
    selectorHora(V.fiHora, {
        opciones: horasDelDia,
        actual: () => { const f = leerFechas(); return f ? minDelDia(f.inicio) : 540; },
        elegir: (o) => {
            const f = leerFechas(); if (!f) return;
            const i = fijarHora(f.inicio, o.min);
            fijarFechas(i, new Date(i.getTime() + (f.fin - f.inicio)));
        },
    });
    selectorHora(V.ffHora, {
        opciones: () => { const f = leerFechas(); return f && mismoDia(f.inicio, sumarMin(f.fin, -1)) ? horasDesde(f.inicio) : horasDelDia(); },
        actual: () => { const f = leerFechas(); return f ? minDelDia(f.fin) : 600; },
        elegir: (o) => {
            const f = leerFechas(); if (!f) return;
            const otroDia = !mismoDia(f.inicio, sumarMin(f.fin, -1));
            const fin = o.dur != null || !otroDia ? finDesde(f.inicio, o) : fijarHora(f.fin, o.min);
            fijarFechas(f.inicio, fin <= f.inicio ? sumarMin(f.inicio, PASO_MIN) : fin);
        },
    });
    F.todoElDia.addEventListener('change', () => {
        // Se leen las fechas con el estado anterior de la casilla.
        const ahora = F.todoElDia.checked;
        F.todoElDia.checked = !ahora;
        const f = leerFechas() || { inicio: new Date(), fin: sumarMin(new Date(), 60) };
        if (ahora) {
            const i = new Date(f.inicio); i.setHours(0, 0, 0, 0);
            const u = new Date(sumarMin(f.fin, -1)); u.setHours(0, 0, 0, 0);
            ponerFechas(i, sumarMin(u, 1440), true);
        } else {
            const i = new Date(f.inicio); i.setHours(9, 0, 0, 0);
            ponerFechas(i, sumarMin(i, 60), false);
        }
        actualizarVista();
    });

    // participantes
    function pintarParticipantes() {
        $('participantes_chips').innerHTML = form.participantes.map((p, i) => `<span class="vc-tag" style="--c:${colorPersona(p.nombre)}"><b>${esc(iniciales(p.nombre))}</b>${esc(p.nombre)}`
            + `<button type="button" data-quitar="${i}" aria-label="Quitar a ${esc(p.nombre)}">✕</button></span>`).join('');
    }
    function agregarParticipante() {
        const texto = $('participantes_buscar').value.trim().toLowerCase();
        if (!texto) return false;
        const t = D.trabajadores.find((x) => x.nombre.toLowerCase() === texto) || D.trabajadores.filter((x) => x.nombre.toLowerCase().includes(texto)).find((x, _, arr) => arr.length === 1);
        if (!t) return false;
        if (!form.participantes.some((p) => String(p.trabajador_id) === String(t.id))) {
            form.participantes.push({ trabajador_id: t.id, nombre: t.nombre, rol: form.participantes.length ? 'APOYO' : 'RESPONSABLE' });
        }
        $('participantes_buscar').value = '';
        pintarParticipantes();
        actualizarVista();
        return true;
    }
    $('participantes_buscar').addEventListener('change', agregarParticipante);
    $('participantes_buscar').addEventListener('keydown', (e) => {
        if (e.key === 'Enter') { e.preventDefault(); agregarParticipante(); }
        if (e.key === 'Backspace' && !e.target.value && form.participantes.length) { form.participantes.pop(); pintarParticipantes(); actualizarVista(); }
    });
    $('participantes_chips').addEventListener('click', (e) => {
        const b = e.target.closest('[data-quitar]');
        if (!b) return;
        form.participantes.splice(Number(b.dataset.quitar), 1);
        if (form.participantes.length) form.participantes[0].rol = 'RESPONSABLE';
        pintarParticipantes();
        actualizarVista();
    });

    // cliente
    function ponerCliente(c) {
        form.cliente = c;
        F.clienteId.value = c ? c.id : '';
        F.clienteBuscar.value = '';
        F.clienteBuscar.hidden = !!c;
        $('cliente_chip').innerHTML = c ? `<span class="vc-tag" style="--c:#0f766e"><b>🏢</b>${esc(c.razon_social)}${c.correo_contacto ? ` <span class="vc-sub">${esc(c.correo_contacto)}</span>` : ''}`
            + '<button type="button" data-quitar-cliente aria-label="Quitar cliente">✕</button></span>' : '';
        F.avisar.disabled = !(c && c.correo_contacto);
        if (F.avisar.disabled) F.avisar.checked = false;
        const enviado = form.detalle && form.detalle.aviso_cliente_enviado_en && !form.duplicar
            ? ` Último aviso: ${fechaCorta(new Date(form.detalle.aviso_cliente_enviado_en))}.` : '';
        $('avisar_cliente_ayuda').textContent = c
            ? (c.correo_contacto ? `(se enviará a ${c.correo_contacto})${enviado}` : '(este cliente no tiene correo registrado)')
            : '(se activa al elegir un cliente con correo)';
        actualizarVista();
    }
    F.clienteBuscar.addEventListener('change', () => {
        const texto = F.clienteBuscar.value.trim().toLowerCase();
        if (!texto) return;
        const c = D.clientes.find((x) => `${x.razon_social}${x.correo_contacto ? ` — ${x.correo_contacto}` : ''}`.toLowerCase() === texto)
            || D.clientes.find((x) => (x.correo_contacto || '').toLowerCase() === texto)
            || D.clientes.filter((x) => x.razon_social.toLowerCase().includes(texto) || (x.correo_contacto || '').toLowerCase().includes(texto)).find((x, _, arr) => arr.length === 1);
        if (c) ponerCliente(c);
    });
    $('cliente_chip').addEventListener('click', (e) => { if (e.target.closest('[data-quitar-cliente]')) { ponerCliente(null); F.clienteBuscar.focus(); } });

    $('actividadForm').addEventListener('input', actualizarVista);
    $('actividadForm').addEventListener('change', actualizarVista);

    function abrirFormulario(op) {
        cerrarPops();
        op = op || {};
        const d = op.detalle || null;
        form.detalle = d;
        form.duplicar = !!op.duplicar;
        const editando = d && !op.duplicar;
        F.error.textContent = '';
        $('formTitle').textContent = editando ? 'Editar actividad' : (op.duplicar ? 'Duplicar actividad' : 'Nueva actividad');
        $('actividad_id').value = editando ? d.id : '';
        F.titulo.value = d ? d.titulo : (op.titulo || '');

        let inicio; let fin; let todo;
        if (d) {
            inicio = new Date(d.fecha_inicio); fin = new Date(d.fecha_fin); todo = d.todo_el_dia;
        } else if (op.inicio) {
            inicio = op.inicio; fin = op.fin; todo = op.todoElDia;
        } else {
            const v = calendar.view;
            const hoy = new Date();
            inicio = (hoy >= v.currentStart && hoy < v.currentEnd) ? new Date(hoy) : new Date(v.currentStart);
            if (inicio.getDate() === hoy.getDate() && inicio.getMonth() === hoy.getMonth()) {
                inicio.setMinutes(inicio.getMinutes() < 30 ? 30 : 60, 0, 0);
            } else {
                inicio.setHours(9, 0, 0, 0);
            }
            fin = sumarMin(inicio, 60); todo = false;
        }
        ponerFechas(inicio, fin, todo);

        const cals = calendariosParaCrear();
        form.cal = d ? (d.categoria_id || '') : (op.categoria_id || calendarioPorDefecto());
        if (d && !cals.some((c) => String(c.id) === String(form.cal))) form.cal = editando ? (d.categoria_id || '') : calendarioPorDefecto();
        chipsCalendario($('form_calendarios'), form.cal, (id) => { form.cal = id; actualizarVista(); });
        if (editando && !d.categoria_id) {
            $('form_calendarios').insertAdjacentHTML('afterbegin', `<button type="button" class="vc-chip activo" style="--c:${SIN_CAL.color}" data-id=""><i></i>Sin calendario</button>`);
        }

        F.clase.value = d ? d.clase : 'REUNION';
        form.prioridad = d ? d.prioridad : 'MEDIA';
        pintarPrioridad();
        F.estado.hidden = !editando;
        F.estado.value = editando ? d.estado : 'PROGRAMADA';
        F.proyecto.value = d && d.proyecto_id ? String(d.proyecto_id) : '';

        form.participantes = d ? d.participantes.map((x) => ({ trabajador_id: x.trabajador_id, nombre: x.nombre, rol: x.rol, confirmado: x.confirmado, comentario: x.comentario })) : [];
        $('participantes_buscar').value = '';
        pintarParticipantes();

        const cliente = d && d.cliente_id ? (D.clientes.find((c) => c.id === d.cliente_id) || { id: d.cliente_id, razon_social: d.cliente_nombre || 'Cliente', correo_contacto: d.cliente_tiene_correo ? '…' : '' }) : null;
        F.clienteManual.value = d ? (d.cliente_nombre_manual || '') : '';
        F.avisar.checked = false;
        ponerCliente(cliente);

        $('descripcion').value = d ? d.descripcion : '';
        $('ubicacion').value = d ? d.ubicacion : '';
        $('enlace_externo').value = d ? d.enlace_externo : '';
        $('observaciones').value = d ? d.observaciones : '';
        $('bloquea_agenda').checked = d ? d.bloquea_agenda : false;
        const rec = d ? (d.recordatorios[0] || null) : { minutos_antes: 30 };
        $('recordatorio').value = rec ? String(rec.minutos_antes) : '';
        if (rec && $('recordatorio').value !== String(rec.minutos_antes)) {
            $('recordatorio').insertAdjacentHTML('beforeend', `<option value="${rec.minutos_antes}">${rec.minutos_antes} min antes</option>`);
            $('recordatorio').value = String(rec.minutos_antes);
        }
        $('masOpciones').open = !!(d && (d.descripcion || d.ubicacion || d.enlace_externo || d.observaciones));

        F.modal.hidden = false;
        document.body.style.overflow = 'hidden';
        actualizarVista();
        setTimeout(() => F.titulo.focus(), 30);
    }

    function cerrarModales() {
        document.querySelectorAll('.vc-modal').forEach((m) => { m.hidden = true; });
        document.body.style.overflow = '';
    }
    document.querySelectorAll('[data-cerrar-modal]').forEach((b) => { b.onclick = cerrarModales; });
    document.querySelectorAll('.vc-modal').forEach((m) => m.addEventListener('mousedown', (e) => { if (e.target === m) cerrarModales(); }));

    // vista previa y resumen (panel derecho)
    function actualizarVista() {
        if (F.modal.hidden) return;
        const f = leerFechas();
        const cal = form.cal ? calendarioPorId(form.cal) : SIN_CAL;
        const titulo = F.titulo.value.trim() || '(sin título)';
        const prev = $('vista_previa');
        const res = $('resumen');
        const choques = $('choques');
        if (!f || f.fin < f.inicio) {
            prev.innerHTML = '<p class="vc-sub">Revisa las fechas: el fin no puede ser antes del inicio.</p>';
            res.innerHTML = '';
            choques.textContent = '';
            return;
        }
        const idActual = $('actividad_id').value;
        const otros = cache.datos.filter((e) => e.extendedProps.tipo === 'actividad' && String(e.extendedProps.actividad_id) !== String(idActual)
            && !e.allDay && new Date(e.start) < f.fin && new Date(e.end || e.start) > f.inicio && !f.todoElDia);

        if (f.todoElDia) {
            prev.innerHTML = `<span class="vc-prev-dia">${esc(cuandoTexto(f.inicio, f.fin, true))}</span>`
                + `<div class="vc-prev-ev vc-ev vc-ev-nuevo fc-h-event" style="--c:${cal.color};left:10px;right:10px;top:34px;height:24px;background:color-mix(in srgb, ${cal.color} 18%, var(--vc-pn));border-left:3px solid ${cal.color}"><div class="vc-ev-in"><span class="vc-ev-t">${esc(titulo)}</span></div></div>`;
        } else {
            const h0 = Math.max(0, Math.min(f.inicio.getHours() - 1, 19));
            const pxh = 44;
            const top0 = 26;
            let h = `<span class="vc-prev-dia">${esc(fechaCorta(f.inicio))}</span>`;
            for (let i = 0; i < 5; i++) h += `<div class="vc-prev-h" style="top:${top0 + i * pxh}px">${h0 + i}:00</div>`;
            const bloques = [{ t: titulo, c: cal.color, i: f.inicio, f: f.fin, nuevo: true },
                ...otros.slice(0, 3).map((e) => ({ t: e.title, c: e.extendedProps.color, i: new Date(e.start), f: new Date(e.end || e.start) }))];
            const n = bloques.length;
            const ancho = 100 / n;
            const base = new Date(f.inicio); base.setHours(h0, 0, 0, 0);
            bloques.forEach((b, k) => {
                const ini = Math.max(0, (b.i - base) / 60000);
                const fin = Math.min(5 * 60, (b.f - base) / 60000);
                const alto = Math.max(18, (fin - ini) * pxh / 60 - 2);
                h += `<div class="vc-prev-ev vc-ev${b.nuevo ? ' vc-ev-nuevo' : ''}" style="--c:${b.c};top:${top0 + ini * pxh / 60 + 1}px;height:${alto}px;left:calc(50px + (100% - 60px) * ${k * ancho / 100});width:calc((100% - 60px) * ${ancho / 100} - 3px);background:color-mix(in srgb, ${b.c} 18%, var(--vc-pn));border-left:3px solid ${b.c}">`
                    + `<div class="vc-ev-in" style="--lineas:${Math.max(1, Math.floor((alto - 16) / 13))}"><span class="vc-ev-t">${esc(b.t)}</span>${alto > 30 ? `<span class="vc-ev-h">${hora(b.i)} – ${hora(b.f)}</span>` : ''}</div></div>`;
            });
            prev.innerHTML = h;
        }

        const nombresPart = form.participantes.map((p) => p.nombre.split(' ')[0]);
        let loVeran;
        if (cal.tipo === 'PERSONAL') loVeran = 'Solo tú (calendario personal)';
        else if (form.participantes.length) loVeran = `Solo ${form.participantes.length === 1 ? 'el participante' : `los ${form.participantes.length} participantes`} y tú`;
        else loVeran = cal.miembros ? `Los ${cal.miembros} miembros de «${cal.nombre}»` : `Todos los que ven «${cal.nombre}»`;
        $('participantes_ayuda').textContent = cal.tipo === 'PERSONAL'
            ? 'En un calendario personal solo lo verás tú, aunque agregues personas.'
            : (form.participantes.length ? 'Con participantes, el evento solo les aparece a ellos (y a ti).' : `Sin participantes lo verán todos los que ven «${cal.nombre}».`);
        const clienteTxt = form.cliente ? esc(form.cliente.razon_social) : (F.clienteManual.value.trim() ? esc(F.clienteManual.value.trim()) : 'Ninguno · <b>actividad interna</b>');
        const alCliente = F.avisar.checked ? `<span>Se le enviará un aviso a ${esc(form.cliente.correo_contacto)}</span>` : '<span class="vc-ok">No se le envía nada</span>';
        const recTxt = $('recordatorio').selectedOptions[0] ? $('recordatorio').selectedOptions[0].textContent : 'Sin recordatorio';
        const estado = F.estado.hidden ? 'Programada' : nombreDe(D.estados, F.estado.value);
        res.innerHTML = `<dt>Calendario</dt><dd><span class="vc-cal-ref" style="--c:${cal.color}"><i></i>${esc(cal.nombre)}</span></dd>`
            + `<dt>Lo verán</dt><dd>${esc(loVeran)}</dd>`
            + `<dt>Cuándo</dt><dd>${esc(cuandoTexto(f.inicio, f.fin, f.todoElDia))}</dd>`
            + `<dt>Tipo</dt><dd>${esc(nombreDe(D.clases, F.clase.value))} · prioridad ${esc(nombreDe(D.prioridades, form.prioridad).toLowerCase())} · ${esc(estado)}</dd>`
            + (nombresPart.length ? `<dt>Participantes</dt><dd>${esc(nombresPart.join(', '))}</dd>` : '')
            + `<dt>Cliente</dt><dd>${clienteTxt}</dd>`
            + `<dt>Al cliente</dt><dd>${alCliente}</dd>`
            + `<dt>Recordatorio</dt><dd>${esc(recTxt)}</dd>`;
        choques.textContent = otros.length
            ? `⚠ Choca con ${otros.length} actividad${otros.length > 1 ? 'es' : ''} a la misma hora (se muestra${otros.length > 1 ? 'n' : ''} al lado, no se bloquea).`
            : '';
    }

    async function guardarFormulario() {
        F.error.textContent = '';
        const titulo = F.titulo.value.trim();
        const fallar = (msg, el) => { F.error.textContent = msg; if (el) el.focus(); };
        if (titulo.length < 2) return fallar('Escribe el título de la actividad.', F.titulo);
        const f = leerFechas();
        if (!f) return fallar('Indica la fecha de inicio y de fin.', V.fiDia);
        if (f.fin < f.inicio) return fallar('La fecha de fin no puede ser anterior a la de inicio.', V.ffDia);
        if (F.clase.value === 'ENSAYO' && !F.proyecto.value) return fallar('Para una actividad de tipo Ensayo elige el proyecto.', F.proyecto);
        if (!form.cal && calendariosParaCrear().length && !$('actividad_id').value) return fallar('Elige un calendario.', null);
        agregarParticipante();

        const rec = $('recordatorio').value;
        const datos = {
            id: $('actividad_id').value || null,
            titulo,
            descripcion: $('descripcion').value.trim(),
            clase: F.clase.value,
            estado: F.estado.hidden ? 'PROGRAMADA' : F.estado.value,
            prioridad: form.prioridad,
            fecha_inicio: f.inicio.toISOString(),
            fecha_fin: f.fin.toISOString(),
            todo_el_dia: f.todoElDia,
            categoria_id: form.cal || null,
            cliente_id: form.cliente ? form.cliente.id : null,
            cliente_nombre_manual: form.cliente ? '' : F.clienteManual.value.trim(),
            avisar_cliente: F.avisar.checked,
            proyecto_id: F.proyecto.value || null,
            ubicacion: $('ubicacion').value.trim(),
            enlace_externo: $('enlace_externo').value.trim(),
            observaciones: $('observaciones').value.trim(),
            bloquea_agenda: $('bloquea_agenda').checked,
            es_visible: true,
            participantes: form.participantes.map((p, i) => ({ trabajador_id: p.trabajador_id, rol: i === 0 ? 'RESPONSABLE' : (p.rol === 'RESPONSABLE' ? 'APOYO' : p.rol || 'APOYO'), confirmado: !!p.confirmado, comentario: p.comentario || '' })),
            recordatorios: rec && !f.todoElDia ? [{ minutos_antes: Number(rec), tipo: 'APP' }] : [],
        };
        const boton = $('btnGuardarActividad');
        boton.disabled = true;
        const res = await enviar(U.guardar, datos);
        boton.disabled = false;
        if (!res.ok) return fallar(res.data.error || 'No se pudo guardar la actividad.', null);
        if (form.cal) ls.set('vc_ultimo_cal', form.cal);
        cerrarModales();
        recargar();
        if (!datos.id) calendar.gotoDate(f.inicio);
        aviso(datos.avisar_cliente ? 'Actividad guardada · el aviso al cliente sale en unos segundos.' : 'Actividad guardada.');
        return true;
    }
    $('btnGuardarActividad').onclick = guardarFormulario;
    $('actividadForm').addEventListener('submit', (e) => { e.preventDefault(); guardarFormulario(); });
    F.titulo.addEventListener('keydown', (e) => { if (e.key === 'Enter') { e.preventDefault(); guardarFormulario(); } });
    if ($('btnNuevaActividad')) $('btnNuevaActividad').onclick = () => abrirFormulario({});
    if ($('vc-fab')) $('vc-fab').onclick = () => abrirFormulario({});

    // ---------- nuevo calendario ----------
    const cf = { tipo: 'PERSONAL', color: COLORES[1] };
    function abrirCalendario(tipo) {
        cerrarPops();
        cf.tipo = tipo === 'EQUIPO' && D.puede_crear ? 'EQUIPO' : 'PERSONAL';
        cf.color = COLORES[(D.calendarios.length + 1) % COLORES.length];
        $('cal_nombre').value = '';
        $('cal_error').textContent = '';
        $('cal_tipo_fila').hidden = !D.puede_crear;
        $('cal_colores').innerHTML = COLORES.map((c) => `<button type="button" style="--c:${c}" data-color="${c}" aria-label="Color ${c}"></button>`).join('');
        $('cal_miembros').innerHTML = D.trabajadores.filter((t) => !t.yo).map((t) => `<div class="vc-miembro"><span>${esc(t.nombre)}</span>`
            + `<label><input type="checkbox" data-ve="${t.id}"> Ve</label><label><input type="checkbox" data-crea="${t.id}"> Crea</label></div>`).join('');
        pintarCal();
        $('modalCalendario').hidden = false;
        setTimeout(() => $('cal_nombre').focus(), 30);
    }
    function pintarCal() {
        $('cal_colores').querySelectorAll('button').forEach((b) => b.classList.toggle('activo', b.dataset.color === cf.color));
        $('cal_tipo').querySelectorAll('button').forEach((b) => b.classList.toggle('activo', b.dataset.tipo === cf.tipo));
        $('cal_miembros_bloque').hidden = cf.tipo !== 'EQUIPO';
        $('calTitulo').textContent = cf.tipo === 'EQUIPO' ? 'Nuevo calendario de equipo' : 'Nuevo calendario personal';
        $('calSub').textContent = cf.tipo === 'EQUIPO' ? 'Compartido con tu equipo' : 'Solo lo verás tú';
    }
    $('cal_colores').addEventListener('click', (e) => { const b = e.target.closest('[data-color]'); if (b) { cf.color = b.dataset.color; pintarCal(); } });
    $('cal_tipo').addEventListener('click', (e) => { const b = e.target.closest('[data-tipo]'); if (b) { cf.tipo = b.dataset.tipo; pintarCal(); } });
    $('cal_miembros').addEventListener('change', (e) => {
        // «Crea» implica «Ve».
        if (e.target.dataset.crea && e.target.checked) $('cal_miembros').querySelector(`[data-ve="${e.target.dataset.crea}"]`).checked = true;
        if (e.target.dataset.ve && !e.target.checked) $('cal_miembros').querySelector(`[data-crea="${e.target.dataset.ve}"]`).checked = false;
    });
    document.querySelectorAll('[data-nuevo-calendario]').forEach((b) => { b.onclick = () => abrirCalendario(b.dataset.nuevoCalendario); });
    async function guardarCalendario() {
        const nombre = $('cal_nombre').value.trim();
        if (nombre.length < 2) { $('cal_error').textContent = 'Escribe el nombre del calendario.'; $('cal_nombre').focus(); return; }
        const marcados = (attr) => [...$('cal_miembros').querySelectorAll(`[data-${attr}]:checked`)].map((x) => x.dataset[attr]);
        const res = await enviar(U.calendario, {
            nombre, color: cf.color, tipo: cf.tipo,
            miembros: cf.tipo === 'EQUIPO' ? marcados('ve') : [],
            miembros_crean: cf.tipo === 'EQUIPO' ? marcados('crea') : [],
        });
        if (!res.ok) { $('cal_error').textContent = res.data.error || 'No se pudo crear.'; return; }
        D.calendarios.push(res.data.calendario);
        D.calendarios.sort((a, b) => (a.tipo + a.nombre).localeCompare(b.tipo + b.nombre));
        pintarCalendarios();
        cerrarModales();
        aviso(`Calendario «${res.data.calendario.nombre}» creado.`);
    }
    $('btnGuardarCalendario').onclick = guardarCalendario;
    $('cal_nombre').addEventListener('keydown', (e) => { if (e.key === 'Enter') { e.preventDefault(); guardarCalendario(); } });

    // ---------- teclado ----------
    document.addEventListener('keydown', (e) => {
        if (e.key === 'Escape') {
            cerrarPops();
            cerrarModales();
            app.classList.remove('lateral-abierto');
            return;
        }
        const enCampo = e.target.closest('input, textarea, select, [contenteditable="true"]');
        const abierto = !$('modalFormulario').hidden || !$('modalCalendario').hidden;
        if (enCampo || abierto || e.ctrlKey || e.metaKey || e.altKey) return;
        if (e.key === 'c' && D.puede_crear) { e.preventDefault(); abrirFormulario({}); }
        if (e.key === '/') { e.preventDefault(); $('vc-buscar').focus(); }
        if (e.key === 't') calendar.today();
    });
})();
