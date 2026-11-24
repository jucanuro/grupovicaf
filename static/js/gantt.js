/* gantt.js — Gantt del LIMS (HU-LIMS-22, REQ-LIMS-74 a 84).
 *
 * Lee una vez el JSON de actividades:gantt_actividades_json (ensayos y
 * actividades) y filtra en el navegador. La vista «Ensayos» agrupa por
 * solicitud y pinta cada línea por su estado real (actividades/gantt_ensayos.py);
 * «Actividades» agrupa por calendario con el color del calendario.
 * Sin librerías: todo es HTML y CSS (static/css/gantt.css).
 */
(function () {
    'use strict';

    var app = document.getElementById('gantt-app');
    if (!app) return;

    var DIA = 86400000;
    var CLAVE = 'vicaf.gantt.v1';
    var COLORES = { pend: 'var(--vg-pend)', proc: 'var(--vg-proc)', ok: 'var(--vg-ok)', venc: 'var(--vg-venc)' };
    var ZOOM = { semana: 1, seis: 6, trimestre: 13 };
    var MESES = ['ene', 'feb', 'mar', 'abr', 'may', 'jun', 'jul', 'ago', 'set', 'oct', 'nov', 'dic'];
    var MESES_LARGO = ['Enero', 'Febrero', 'Marzo', 'Abril', 'Mayo', 'Junio', 'Julio', 'Agosto', 'Setiembre', 'Octubre', 'Noviembre', 'Diciembre'];
    var AVATAR = ['#2563eb', '#db2777', '#7c3aed', '#0891b2', '#ea580c', '#16a34a', '#4f46e5', '#be123c'];
    var AGRUPAR = {
        ensayos: [['solicitud', 'Solicitud'], ['tecnico', 'Técnico'], ['cliente', 'Cliente']],
        actividades: [['calendario', 'Calendario'], ['responsable', 'Persona']]
    };
    var ESTADOS = {
        ensayos: [['proc', 'En proceso'], ['pend', 'Sin empezar'], ['ok', 'Terminado']],
        actividades: [['proc', 'En curso'], ['pend', 'Programada'], ['ok', 'Completada']]
    };

    var $ = function (id) { return document.getElementById(id); };
    var cuerpo = $('vg-cuerpo');
    var pop = $('vg-pop');
    var movil = window.matchMedia('(max-width: 900px)');

    var hoy = soloFecha(new Date());
    var datos = [];
    var cargado = false;
    var guardado = leerPreferencias();
    var est = {
        vista: guardado.vista === 'actividades' ? 'actividades' : 'ensayos',
        agrupar: guardado.agrupar || {},
        zoom: ZOOM[guardado.zoom] ? guardado.zoom : (movil.matches ? 'semana' : 'seis'),
        estados: { proc: true, pend: true, ok: true },
        soloAtrasados: false,
        kpi: '',
        personas: {},
        buscar: '',
        plegados: {},
        inicio: null,
        sel: null
    };

    // ------------------------------------------------------------ utilidades
    function soloFecha(d) { return new Date(d.getFullYear(), d.getMonth(), d.getDate()); }
    function leerFecha(texto) {
        var p = String(texto || '').split('-');
        return p.length === 3 ? new Date(+p[0], +p[1] - 1, +p[2]) : soloFecha(new Date());
    }
    function lunesDe(d) { var r = soloFecha(d); var w = (r.getDay() + 6) % 7; r.setDate(r.getDate() - w); return r; }
    function sumar(d, n) { var r = new Date(d); r.setDate(r.getDate() + n); return r; }
    function dias(a, b) { return Math.round((b - a) / DIA); }
    function corta(d) { return d.getDate() + ' ' + MESES[d.getMonth()]; }
    function esc(t) {
        return String(t == null ? '' : t).replace(/[&<>"']/g, function (c) {
            return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c];
        });
    }
    function colorPersona(id, nombre) {
        if (!id && (!nombre || nombre === 'Sin asignar')) return '#94a3b8';
        var base = id || 0;
        if (!base) { for (var i = 0; i < (nombre || '').length; i++) base += nombre.charCodeAt(i); }
        return AVATAR[base % AVATAR.length];
    }
    function iniciales(nombre) {
        var p = String(nombre || '').trim().split(/\s+/).filter(Boolean);
        if (!p.length) return '?';
        return (p.length === 1 ? p[0].slice(0, 2) : p[0][0] + p[1][0]).toUpperCase();
    }
    function avatar(nombre, id, ini) {
        return '<span class="vg-av" style="--c:' + colorPersona(id, nombre) + '" title="' + esc(nombre) + '">' + esc(ini || iniciales(nombre)) + '</span>';
    }
    function leerPreferencias() {
        try { return JSON.parse(localStorage.getItem(CLAVE)) || {}; } catch (e) { return {}; }
    }
    function guardarPreferencias() {
        try { localStorage.setItem(CLAVE, JSON.stringify({ vista: est.vista, agrupar: est.agrupar, zoom: est.zoom })); } catch (e) { /* sin almacenamiento */ }
    }
    function agruparActual() {
        var opciones = AGRUPAR[est.vista];
        var v = est.agrupar[est.vista];
        return opciones.some(function (o) { return o[0] === v; }) ? v : opciones[0][0];
    }

    // ----------------------------------------------------------- normalizar
    function normalizar(lista) {
        return lista.map(function (x) {
            var ini = leerFecha(x.start);
            var fin = leerFecha(x.end);
            if (fin < ini) fin = ini;
            var r = { raw: x, ini: ini, fin: fin, prog: x.programada ? leerFecha(x.programada) : fin, tipo: x.tipo === 'ensayo' ? 'ensayo' : 'actividad' };
            if (r.tipo === 'ensayo') {
                r.grupoColor = x.grupo || 'pend';
                r.avance = +x.avance || 0;
                r.atraso = +x.atraso_dias || 0;
                r.persona = x.responsable || 'Sin asignar';
                r.personaId = x.responsable_id || 0;
                r.texto = [x.codigo_solicitud, x.muestra, x.servicio, x.cliente, x.norma].join(' ').toLowerCase();
            } else {
                var e = String(x.estado || '').toUpperCase();
                r.grupoColor = e === 'COMPLETADA' ? 'ok' : (e === 'EN_CURSO' ? 'proc' : 'pend');
                r.cancelada = e === 'CANCELADA';
                r.avance = +x.progreso_temporal || 0;
                r.atraso = x.esta_vencido ? Math.max(1, dias(fin, hoy)) : 0;
                r.persona = x.responsable || 'Sin asignar';
                r.personaId = x.responsable_id || 0;
                r.texto = [x.name, x.calendario, x.cliente, x.proyecto, x.responsable].join(' ').toLowerCase();
            }
            return r;
        });
    }

    // --------------------------------------------------------------- filtros
    function deLaVista() {
        var tipo = est.vista === 'ensayos' ? 'ensayo' : 'actividad';
        return datos.filter(function (r) { return r.tipo === tipo; });
    }
    function pasaFiltros(r, ignorarKpi) {
        if (!est.estados[r.grupoColor]) return false;
        if (est.soloAtrasados && !r.atraso) return false;
        var personas = Object.keys(est.personas);
        if (personas.length && !est.personas[r.persona]) return false;
        if (est.buscar && r.texto.indexOf(est.buscar) === -1) return false;
        if (!ignorarKpi && est.kpi) {
            if (est.kpi === 'proc' && r.grupoColor !== 'proc') return false;
            if (est.kpi === 'semana' && !r.raw.entrega_semana) return false;
            if (est.kpi === 'atraso' && !r.atraso) return false;
            if (est.kpi === 'mes' && !r.raw.terminado_mes) return false;
            if (est.kpi === 'ok' && r.grupoColor !== 'ok') return false;
            if (est.kpi === 'pend' && r.grupoColor !== 'pend') return false;
        }
        return true;
    }
    function hayFiltros() {
        return est.soloAtrasados || est.kpi || est.buscar || Object.keys(est.personas).length ||
            !est.estados.proc || !est.estados.pend || !est.estados.ok || $('vg-proyecto').value;
    }

    // ---------------------------------------------------------------- lateral
    function pintarLateral() {
        document.querySelectorAll('[data-vista]').forEach(function (b) {
            b.setAttribute('aria-selected', String(b.dataset.vista === est.vista));
        });
        var ag = agruparActual();
        $('vg-agrupar').innerHTML = AGRUPAR[est.vista].map(function (o) {
            return '<button type="button" data-agrupar="' + o[0] + '" aria-selected="' + (o[0] === ag) + '">' + o[1] + '</button>';
        }).join('');

        var base = deLaVista();
        var cuenta = { proc: 0, pend: 0, ok: 0 };
        var atrasados = 0;
        base.forEach(function (r) { cuenta[r.grupoColor]++; if (r.atraso) atrasados++; });
        var html = ESTADOS[est.vista].map(function (e) {
            return '<button type="button" class="vg-it" data-estado="' + e[0] + '" aria-pressed="' + !!est.estados[e[0]] + '">' +
                '<span class="vg-sw ' + (e[0] === 'pend' ? 'pend' : '') + '" style="--c:' + COLORES[e[0]] + '"></span>' +
                '<span class="vg-it-n">' + e[1] + '</span><small>' + cuenta[e[0]] + '</small></button>';
        }).join('');
        html += '<button type="button" class="vg-it" data-atrasados aria-pressed="' + est.soloAtrasados + '">' +
            '<span class="vg-sw" style="--c:var(--vg-venc)"></span><span class="vg-it-n">Solo atrasados</span>' +
            '<small class="vg-rojo">' + atrasados + '</small></button>';
        $('vg-estados').innerHTML = html;

        // Personas con su carga: líneas abiertas (no terminadas) de cada una.
        $('vg-personas-titulo').textContent = est.vista === 'ensayos' ? 'Técnicos' : 'Responsables';
        var carga = {};
        base.forEach(function (r) {
            if (!carga[r.persona]) carga[r.persona] = { n: 0, id: r.personaId };
            if (r.grupoColor !== 'ok') carga[r.persona].n++;
        });
        var nombres = Object.keys(carga).sort(function (a, b) { return carga[b].n - carga[a].n || a.localeCompare(b); });
        var maximo = Math.max.apply(null, nombres.map(function (n) { return carga[n].n; }).concat([1]));
        var hayPersonas = Object.keys(est.personas).length > 0;
        $('vg-personas').innerHTML = nombres.length ? nombres.map(function (n) {
            var c = colorPersona(carga[n].id, n);
            return '<button type="button" class="vg-it" data-persona="' + esc(n) + '" aria-pressed="' + (!hayPersonas || !!est.personas[n]) + '">' +
                avatar(n, carga[n].id) + '<span class="vg-it-n">' + esc(n) + '</span><small>' + carga[n].n + '</small></button>' +
                '<div class="vg-carga" style="--c:' + c + '"><i style="width:' + Math.round(carga[n].n * 100 / maximo) + '%"></i></div>';
        }).join('') : '<p class="vg-vacio" style="padding:4px 6px;text-align:left">Nadie con líneas en el rango.</p>';

        $('vg-limpiar').hidden = !hayFiltros();
    }

    // ----------------------------------------------------------------- cifras
    function pintarKpis(lista) {
        var k;
        if (est.vista === 'ensayos') {
            var proc = 0, semana = 0, atraso = 0, mes = 0, solAtraso = {};
            lista.forEach(function (r) {
                if (r.grupoColor === 'proc') proc++;
                if (r.raw.entrega_semana) semana++;
                if (r.atraso) { atraso++; solAtraso[r.raw.solicitud_id] = 1; }
                if (r.raw.terminado_mes) mes++;
            });
            var nSol = Object.keys(solAtraso).length;
            k = [
                ['proc', 'var(--vg-proc)', '▶', proc, 'en proceso'],
                ['semana', 'var(--vg-azul)', '7', semana, 'se entregan esta semana'],
                ['atraso', 'var(--vg-venc)', '!', atraso, 'atrasados' + (nSol ? ' · ' + nSol + ' solicitud' + (nSol > 1 ? 'es' : '') : '')],
                ['mes', 'var(--vg-ok)', '✓', mes, 'terminados en ' + MESES_LARGO[hoy.getMonth()].toLowerCase()]
            ];
        } else {
            var c = { proc: 0, pend: 0, ok: 0 }, v = 0;
            lista.forEach(function (r) { c[r.grupoColor]++; if (r.atraso) v++; });
            k = [
                ['proc', 'var(--vg-proc)', '▶', c.proc, 'en curso'],
                ['pend', 'var(--vg-azul)', '○', c.pend, 'programadas'],
                ['atraso', 'var(--vg-venc)', '!', v, 'vencidas'],
                ['ok', 'var(--vg-ok)', '✓', c.ok, 'completadas']
            ];
        }
        $('vg-kpis').innerHTML = k.map(function (x) {
            return '<button type="button" class="vg-k" data-kpi="' + x[0] + '" aria-pressed="' + (est.kpi === x[0]) + '" style="--c:' + x[1] + '">' +
                '<i aria-hidden="true">' + x[2] + '</i><div style="min-width:0"><b>' + x[3] + '</b><span>' + x[4] + '</span></div></button>';
        }).join('');
    }

    // ---------------------------------------------------------------- ventana
    function ventana() {
        var sem = ZOOM[est.zoom];
        if (!est.inicio) {
            // Hoy queda en la 1.ª semana (Semana) o tras 2 semanas de contexto.
            est.inicio = sumar(lunesDe(hoy), -7 * Math.min(2, Math.floor(sem / 3)));
        }
        return { ini: est.inicio, sem: sem, nd: sem * 7, fin: sumar(est.inicio, sem * 7 - 1) };
    }
    function pct(v, d) { return (dias(v.ini, d) / v.nd * 100); }

    function cabecera(v) {
        var h = '<div class="vg-fila vg-cab"><div class="vg-etq"><span>' +
            (est.vista === 'ensayos' ? 'Solicitud · muestra · ensayo' : 'Calendario · actividad') + '</span><span>' +
            (est.vista === 'ensayos' ? 'Téc.' : 'Resp.') + '</span></div>' +
            '<div class="vg-dias" style="grid-template-columns:repeat(' + v.sem + ',1fr)">';
        for (var s = 0; s < v.sem; s++) {
            var lunes = sumar(v.ini, s * 7);
            h += '<div class="vg-sem"><div class="vg-sem-t">' + (v.sem > 8 ? corta(lunes) : 'Sem ' + semanaIso(lunes) + ' · ' + corta(lunes)) + '</div><div class="vg-sem-d">';
            for (var j = 0; j < 7; j++) {
                var d = sumar(lunes, j);
                var esHoy = d.getTime() === hoy.getTime();
                var mostrar = v.sem === 1 || (v.sem <= 6 && j % 2 === 0) || (v.sem > 6 && j === 0) || esHoy;
                h += '<div class="vg-d' + (j > 4 ? ' fs' : '') + (esHoy ? ' hoy' : '') + '">' +
                    (mostrar ? '<b>' + (v.sem === 1 ? ['L', 'M', 'M', 'J', 'V', 'S', 'D'][j] + ' ' : '') + d.getDate() + '</b>' : '') + '</div>';
            }
            h += '</div></div>';
        }
        return h + '</div></div>';
    }
    function semanaIso(d) {
        var t = new Date(Date.UTC(d.getFullYear(), d.getMonth(), d.getDate()));
        var n = t.getUTCDay() || 7;
        t.setUTCDate(t.getUTCDate() + 4 - n);
        var y = new Date(Date.UTC(t.getUTCFullYear(), 0, 1));
        return Math.ceil(((t - y) / DIA + 1) / 7);
    }

    function marcaHoy(v) {
        if (hoy < v.ini || hoy > v.fin) return '';
        return '<div class="vg-hoy" style="left:' + (pct(v, hoy) + 50 / v.nd) + '%"></div>';
    }

    function barra(r, v) {
        if (r.fin < v.ini && !(r.atraso && hoy >= v.ini)) return marcaHoy(v);
        var a = r.ini < v.ini ? v.ini : r.ini;
        var b = r.fin > v.fin ? v.fin : r.fin;
        var h = '';
        var x = r.raw;
        if (r.atraso) {
            var ra = sumar(r.prog, 1) < v.ini ? v.ini : sumar(r.prog, 1);
            var rb = hoy > v.fin ? v.fin : hoy;
            if (rb >= ra) {
                h += '<div class="vg-retraso" style="left:' + pct(v, ra) + '%;width:' + ((dias(ra, rb) + 1) / v.nd * 100) + '%"></div>';
                if (hoy <= v.fin) {
                    h += '<div class="vg-flag" style="left:calc(' + (pct(v, hoy) + 100 / v.nd) + '% + 2px)">+' + r.atraso + ' d</div>';
                }
            }
        }
        if (b >= a) {
            var izq = pct(v, a), ancho = (dias(a, b) + 1) / v.nd * 100;
            var cortaIzq = r.ini < v.ini ? ' corta-izq' : '';
            var sel = est.sel === x.id ? ' sel' : '';
            if (r.tipo === 'ensayo') {
                var g = r.grupoColor;
                var etiqueta = (g === 'ok' ? '✓ ' : '') + x.muestra + (g === 'proc' ? ' · ' + r.avance + '%' : '');
                h += '<button type="button" class="vg-bar ' + g + cortaIzq + sel + '" data-id="' + esc(x.id) + '" style="--c:' + COLORES[g] +
                    ';left:' + izq + '%;width:calc(' + ancho + '% - 2px)" aria-label="' + esc(x.muestra + ', ' + x.servicio + ', ' + x.estado_texto + ', ' + r.avance + ' %' + (r.atraso ? ', atrasado ' + r.atraso + ' días' : '')) + '">' +
                    (g === 'pend' ? '' : '<i class="vg-pr" style="width:' + (g === 'ok' ? 100 : r.avance) + '%"></i>') +
                    '<span>' + esc(etiqueta) + '</span></button>';
            } else {
                var c = x.calendario_color || x.color || '#2563eb';
                h += '<button type="button" class="vg-bar act' + (r.grupoColor === 'ok' ? ' hecha' : '') + (r.atraso ? ' venc' : '') + cortaIzq + sel + '" data-id="' + esc(x.id) +
                    '" style="--c:' + esc(c) + ';left:' + izq + '%;width:calc(' + ancho + '% - 2px)" aria-label="' + esc(x.name + ', ' + (x.estado || '')) + '">' +
                    '<i class="vg-pr" style="width:' + r.avance + '%"></i><span>' + esc(x.name) + '</span></button>';
            }
        }
        return h + marcaHoy(v);
    }

    // ---------------------------------------------------------------- grupos
    function claveGrupo(r) {
        var ag = agruparActual(), x = r.raw;
        if (r.tipo === 'ensayo') {
            if (ag === 'tecnico') return 't:' + r.persona;
            if (ag === 'cliente') return 'c:' + (x.cliente || 'Sin cliente');
            return 's:' + x.solicitud_id;
        }
        if (ag === 'responsable') return 'r:' + r.persona;
        return 'k:' + (x.calendario || 'Sin calendario');
    }
    function cabeceraGrupo(clave, items, v) {
        var ag = agruparActual();
        var x0 = items[0].raw;
        var titulo, sub, extra = '';
        var listos = items.filter(function (r) { return r.grupoColor === 'ok'; }).length;
        var hayAtraso = items.some(function (r) { return r.atraso; });
        if (est.vista === 'ensayos') {
            if (ag === 'solicitud') { titulo = '<b class="vg-mono">' + esc(x0.codigo_solicitud) + '</b>'; sub = x0.cliente || '—'; }
            else if (ag === 'tecnico') { titulo = '<b>' + esc(items[0].persona) + '</b>'; sub = items.length + ' líneas · ' + (items.length - listos) + ' abiertas'; }
            else { titulo = '<b>' + esc(x0.cliente || 'Sin cliente') + '</b>'; sub = contarSolicitudes(items) + ' solicitudes'; }
        } else {
            if (ag === 'calendario') {
                titulo = '<b><span class="vg-sw" style="display:inline-block;margin-right:6px;--c:' + esc(x0.calendario_color || '#2563eb') + '"></span>' + esc(x0.calendario || 'Sin calendario') + '</b>';
            } else { titulo = '<b>' + esc(items[0].persona) + '</b>'; }
            sub = items.length + ' actividades';
        }
        var dots = items.slice(0, 12).map(function (r) {
            return '<i class="' + (r.grupoColor === 'pend' ? 'pend' : '') + '" style="--c:' + (r.atraso ? COLORES.venc : COLORES[r.grupoColor]) + '"></i>';
        }).join('');
        var plegado = !!est.plegados[clave];

        // Resumen en la línea de tiempo: un tramo por línea y la entrega.
        var ini = items.reduce(function (m, r) { return r.ini < m ? r.ini : m; }, items[0].ini);
        var fin = items.reduce(function (m, r) { return r.fin > m ? r.fin : m; }, items[0].fin);
        var a = ini < v.ini ? v.ini : ini, b = fin > v.fin ? v.fin : fin;
        if (b >= a) {
            extra += '<div class="vg-gbar" style="left:' + pct(v, a) + '%;width:calc(' + ((dias(a, b) + 1) / v.nd * 100) + '% - 2px)">' +
                items.map(function (r) {
                    return '<i style="background:' + (r.tipo === 'actividad' ? esc(r.raw.calendario_color || '#94a3b8') : COLORES[r.grupoColor]) + ';opacity:' + (r.grupoColor === 'pend' ? .4 : .85) + '"></i>';
                }).join('') + '</div>';
        }
        if (est.vista === 'ensayos' && ag === 'solicitud' && x0.entrega_solicitud) {
            var ent = leerFecha(x0.entrega_solicitud);
            if (ent >= v.ini && ent <= v.fin) {
                extra += '<span class="vg-ent' + (hayAtraso ? ' venc' : '') + '" style="left:' + (pct(v, ent) + 50 / v.nd) + '%" title="Entrega ' + corta(ent) + '"></span>';
            }
        }
        var cnt = est.vista === 'ensayos' ? listos + '/' + items.length + ' listos' : items.length;
        return '<div class="vg-fila vg-g' + (plegado ? ' vg-plegado' : '') + '" data-grupo="' + esc(clave) + '">' +
            '<div class="vg-etq" role="button" tabindex="0" aria-expanded="' + !plegado + '"><span class="vg-car" aria-hidden="true">▾</span>' +
            '<div class="vg-gt">' + titulo + '<small>' + esc(sub) + '</small></div>' +
            '<div class="vg-cnt">' + cnt + '<div class="vg-dots">' + dots + '</div></div></div>' +
            '<div class="vg-pista" style="--sem:' + v.sem + '">' + extra + marcaHoy(v) + '</div></div>';
    }
    function contarSolicitudes(items) {
        var s = {};
        items.forEach(function (r) { s[r.raw.solicitud_id] = 1; });
        return Object.keys(s).length;
    }
    function filaItem(r, v) {
        var x = r.raw, etq;
        if (r.tipo === 'ensayo') {
            var ag = agruparActual();
            etq = '<span class="vg-sw ' + (r.grupoColor === 'pend' ? 'pend' : '') + '" style="--c:' + (r.atraso ? COLORES.venc : COLORES[r.grupoColor]) + '"></span>' +
                '<span class="vg-m vg-mono">' + esc(x.muestra) + '</span>' +
                '<span class="vg-s" title="' + esc(x.servicio) + '">' + esc(ag === 'solicitud' ? x.servicio : x.codigo_solicitud + ' · ' + x.servicio) + '</span>' +
                avatar(r.persona, r.personaId, x.iniciales);
        } else {
            etq = '<span class="vg-sw" style="--c:' + esc(x.calendario_color || '#2563eb') + '"></span>' +
                '<span class="vg-s" style="color:var(--vg-tx2);font-weight:600" title="' + esc(x.name) + '">' + esc(x.name) + '</span>' +
                avatar(r.persona, r.personaId);
        }
        return '<div class="vg-fila"><div class="vg-etq">' + etq + '</div><div class="vg-pista" style="--sem:' + v.sem + '">' + barra(r, v) + '</div></div>';
    }

    // ---------------------------------------------------------------- pintar
    function pintar() {
        cerrarFicha();
        var v = ventana();
        var inicioMes = v.ini, finMes = v.fin;
        $('vg-titulo').innerHTML = inicioMes.getMonth() === finMes.getMonth()
            ? MESES_LARGO[inicioMes.getMonth()] + ' <span>' + inicioMes.getFullYear() + '</span>'
            : MESES_LARGO[inicioMes.getMonth()].slice(0, 3) + ' – ' + MESES_LARGO[finMes.getMonth()].slice(0, 3) + ' <span>' + finMes.getFullYear() + '</span>';
        document.querySelectorAll('[data-zoom]').forEach(function (b) {
            b.setAttribute('aria-selected', String(b.dataset.zoom === est.zoom));
        });
        $('vg-buscar').placeholder = est.vista === 'ensayos' ? 'Solicitud, muestra o ensayo…' : 'Actividad, calendario o cliente…';
        pintarLateral();
        if (!cargado) return;

        var base = deLaVista().filter(function (r) { return pasaFiltros(r, true) && !r.cancelada; });
        pintarKpis(base);
        // En la vista solo entra lo que toca la ventana (o un atraso que llega a ella).
        var lista = base.filter(function (r) {
            return pasaFiltros(r, false) && r.ini <= v.fin && (r.fin >= v.ini || (r.atraso && hoy >= v.ini));
        });

        if (!lista.length) {
            var vacio = deLaVista().length === 0;
            cuerpo.innerHTML = '<div class="vg-vacio"><b>' + (vacio
                ? (est.vista === 'ensayos' ? 'No hay ensayos registrados' : 'No hay actividades registradas')
                : 'Nada en estas fechas con los filtros actuales') + '</b>' +
                (vacio ? 'Cuando se asignen ensayos a una solicitud aparecerán aquí.' : 'Prueba con otra semana, «Trimestre» o quita filtros.') +
                (hayFiltros() ? '<br><button type="button" data-limpiar>Quitar filtros</button>' : '') + '</div>';
            pintarLeyenda();
            return;
        }

        var grupos = {}, orden = [];
        lista.forEach(function (r) {
            var k = claveGrupo(r);
            if (!grupos[k]) { grupos[k] = []; orden.push(k); }
            grupos[k].push(r);
        });
        // Primero los grupos con atraso, luego por fecha de inicio.
        orden.sort(function (a, b) {
            var ga = grupos[a], gb = grupos[b];
            var aa = ga.some(function (r) { return r.atraso; }) ? 0 : 1;
            var ab = gb.some(function (r) { return r.atraso; }) ? 0 : 1;
            if (aa !== ab) return aa - ab;
            return ga[0].ini - gb[0].ini;
        });

        var html = cabecera(v);
        orden.forEach(function (k) {
            var items = grupos[k];
            html += '<div class="vg-grupo">' + cabeceraGrupo(k, items, v);
            if (!est.plegados[k]) items.forEach(function (r) { html += filaItem(r, v); });
            html += '</div>';
        });
        cuerpo.innerHTML = html;
        pintarLeyenda();
    }

    function pintarLeyenda() {
        $('vg-ley').innerHTML = est.vista === 'ensayos'
            ? '<span><i class="vg-lb" style="background:var(--vg-ok)"></i>Terminado</span>' +
              '<span><i class="vg-lb" style="background:linear-gradient(90deg,var(--vg-proc) 60%,color-mix(in srgb,var(--vg-proc) 20%,var(--vg-pn)) 60%)"></i>En registro (avance real)</span>' +
              '<span><i class="vg-lb" style="border:1.5px dashed var(--vg-pend)"></i>Sin empezar</span>' +
              '<span><i class="vg-lb" style="background:repeating-linear-gradient(135deg,color-mix(in srgb,var(--vg-venc) 35%,transparent) 0 3px,transparent 3px 6px);border:1.5px solid var(--vg-venc)"></i>Atraso</span>' +
              '<span><span style="display:inline-block;width:9px;height:9px;border:2px solid var(--vg-tx2);transform:rotate(45deg);border-radius:2px"></span>Entrega de la solicitud</span>' +
              '<span class="vg-ley-fin">Clic en una barra para ver el detalle</span>'
            : '<span><i class="vg-lb" style="background:color-mix(in srgb,var(--vg-azul) 20%,var(--vg-pn));border-left:3px solid var(--vg-azul);border-radius:3px"></i>Color = calendario</span>' +
              '<span><i class="vg-lb" style="background:var(--vg-ln2);box-shadow:inset -3px 0 0 var(--vg-venc)"></i>Vencida</span>' +
              '<span class="vg-ley-fin">Clic en una barra para ver el detalle</span>';
    }

    // ----------------------------------------------------------------- ficha
    function abrirFicha(id, boton) {
        var r = datos.filter(function (d) { return d.raw.id === id; })[0];
        if (!r) return;
        var x = r.raw, h;
        est.sel = id;
        document.querySelectorAll('.vg-bar.sel').forEach(function (b) { b.classList.remove('sel'); });
        if (boton) boton.classList.add('sel');
        var fechas = corta(r.ini) + ' → ' + corta(r.fin) + ' · ' + (dias(r.ini, r.fin) + 1) + ' días';
        if (r.tipo === 'ensayo') {
            var g = r.grupoColor;
            h = '<button type="button" class="vg-pop-x" data-cerrar-ficha aria-label="Cerrar">×</button>' +
                '<div class="vg-pop-sub"><span class="vg-mono">' + esc(x.codigo_solicitud) + '</span>' + (x.cliente ? ' · ' + esc(x.cliente) : '') + '</div>' +
                '<h3 id="vg-pop-titulo">' + esc(x.servicio) + '</h3>' +
                '<div class="vg-chips"><span class="vg-chip" style="--c:' + COLORES[g] + '">● ' + esc(x.estado_texto) + '</span>' +
                (r.atraso ? '<span class="vg-chip" style="--c:var(--vg-venc)">Atrasado ' + r.atraso + ' día' + (r.atraso > 1 ? 's' : '') + '</span>' : '') + '</div>' +
                '<dl><dt>Muestra</dt><dd class="vg-mono">' + esc(x.muestra) + '</dd>' +
                (x.norma ? '<dt>Norma</dt><dd>' + esc(x.norma) + '</dd>' : '') +
                '<dt>Programado</dt><dd>' + fechas + '</dd>' +
                '<dt>Entrega</dt><dd>' + corta(leerFecha(x.entrega_solicitud)) + ' (solicitud)</dd>' +
                '<dt>Técnico</dt><dd class="vg-pop-av">' + avatar(r.persona, r.personaId, x.iniciales) + esc(r.persona) + '</dd>' +
                '<dt>Avance</dt><dd>' + r.avance + ' % de los datos y fotos<div class="vg-pbar" style="--c:' + COLORES[g === 'pend' ? 'pend' : g] + '"><i style="width:' + r.avance + '%"></i></div></dd></dl>' +
                '<div class="vg-acc"><a class="vg-btn1" href="' + esc(x.url_resultados) + '">Abrir resultados</a></div>';
        } else {
            h = '<button type="button" class="vg-pop-x" data-cerrar-ficha aria-label="Cerrar">×</button>' +
                '<div class="vg-pop-sub"><span class="vg-sw" style="--c:' + esc(x.calendario_color || '#2563eb') + '"></span>' + esc(x.calendario || '') + '</div>' +
                '<h3 id="vg-pop-titulo">' + esc(x.name) + '</h3>' +
                '<div class="vg-chips"><span class="vg-chip" style="--c:' + COLORES[r.grupoColor] + '">● ' + esc(String(x.estado || '').replace('_', ' ').toLowerCase()) + '</span>' +
                (r.atraso ? '<span class="vg-chip" style="--c:var(--vg-venc)">Vencida</span>' : '') + '</div>' +
                '<dl><dt>Fechas</dt><dd>' + fechas + '</dd>' +
                '<dt>Responsable</dt><dd class="vg-pop-av">' + avatar(r.persona, r.personaId) + esc(r.persona) + '</dd>' +
                (x.cliente ? '<dt>Cliente</dt><dd>' + esc(x.cliente) + '</dd>' : '') +
                (x.proyecto ? '<dt>Proyecto</dt><dd>' + esc(x.proyecto) + '</dd>' : '') + '</dl>' +
                '<div class="vg-acc"><a class="vg-btn1" href="' + esc(app.dataset.urlCalendario) + '">Ver en el calendario</a></div>';
        }
        pop.innerHTML = h;
        pop.hidden = false;
        colocar(boton);
        var x0 = pop.querySelector('.vg-btn1');
        if (x0) x0.focus({ preventScroll: true });
    }
    function colocar(boton) {
        if (!boton) return;
        var rb = boton.getBoundingClientRect();
        var rp = pop.getBoundingClientRect();
        var izq = Math.min(Math.max(12, rb.left + rb.width / 2 - rp.width / 2), window.innerWidth - rp.width - 12);
        var arriba = rb.bottom + 10;
        if (arriba + rp.height > window.innerHeight - 12) arriba = Math.max(12, rb.top - rp.height - 10);
        pop.style.left = izq + 'px';
        pop.style.top = arriba + 'px';
    }
    function cerrarFicha() {
        if (pop.hidden) return;
        pop.hidden = true;
        est.sel = null;
        document.querySelectorAll('.vg-bar.sel').forEach(function (b) { b.classList.remove('sel'); });
    }

    // ---------------------------------------------------------------- eventos
    function limpiar() {
        est.estados = { proc: true, pend: true, ok: true };
        est.soloAtrasados = false;
        est.kpi = '';
        est.personas = {};
        est.buscar = '';
        $('vg-buscar').value = '';
        if ($('vg-proyecto').value) { $('vg-proyecto').value = ''; cargar(); return; }
        pintar();
    }

    app.addEventListener('click', function (e) {
        var t = e.target.closest('button, [data-grupo] .vg-etq, [data-cerrar-lateral]');
        if (!t) return;
        if (t.matches('[data-cerrar-lateral]')) { app.classList.remove('lateral-abierto'); return; }
        if (t.matches('[data-abrir-lateral]')) { app.classList.add('lateral-abierto'); return; }
        if (t.dataset.vista) {
            if (est.vista !== t.dataset.vista) { est.vista = t.dataset.vista; est.kpi = ''; est.personas = {}; guardarPreferencias(); pintar(); }
            return;
        }
        if (t.dataset.agrupar) { est.agrupar[est.vista] = t.dataset.agrupar; est.plegados = {}; guardarPreferencias(); pintar(); return; }
        if (t.dataset.estado) {
            est.estados[t.dataset.estado] = !est.estados[t.dataset.estado];
            if (!est.estados.proc && !est.estados.pend && !est.estados.ok) est.estados[t.dataset.estado] = true;
            pintar(); return;
        }
        if (t.hasAttribute('data-atrasados')) { est.soloAtrasados = !est.soloAtrasados; pintar(); return; }
        if (t.dataset.persona != null) {
            var n = t.dataset.persona;
            if (est.personas[n]) delete est.personas[n]; else est.personas[n] = true;
            pintar(); return;
        }
        if (t.dataset.kpi) { est.kpi = est.kpi === t.dataset.kpi ? '' : t.dataset.kpi; pintar(); return; }
        if (t.dataset.zoom) { est.zoom = t.dataset.zoom; est.inicio = null; guardarPreferencias(); pintar(); return; }
        if (t.dataset.mover != null) {
            var m = +t.dataset.mover;
            if (m === 0) est.inicio = null;
            else { var v = ventana(); est.inicio = sumar(v.ini, m * Math.max(7, Math.round(v.nd / 2 / 7) * 7)); }
            pintar(); return;
        }
        if (t.id === 'vg-limpiar' || t.hasAttribute('data-limpiar')) { limpiar(); return; }
        if (t.classList.contains('vg-bar')) {
            e.stopPropagation();
            if (est.sel === t.dataset.id && !pop.hidden) { cerrarFicha(); return; }
            abrirFicha(t.dataset.id, t); return;
        }
        var g = t.closest('[data-grupo]');
        if (g && t.classList.contains('vg-etq')) {
            var k = g.dataset.grupo;
            est.plegados[k] = !est.plegados[k];
            pintar();
        }
    });
    app.addEventListener('keydown', function (e) {
        var t = e.target;
        if ((e.key === 'Enter' || e.key === ' ') && t.classList.contains('vg-etq') && t.closest('[data-grupo]')) {
            e.preventDefault(); t.click();
        }
    });
    pop.addEventListener('click', function (e) {
        if (e.target.closest('[data-cerrar-ficha]')) cerrarFicha();
    });
    document.addEventListener('click', function (e) {
        if (!pop.hidden && !pop.contains(e.target) && !e.target.closest('.vg-bar')) cerrarFicha();
    });
    document.addEventListener('keydown', function (e) {
        if (e.key === 'Escape') { cerrarFicha(); app.classList.remove('lateral-abierto'); }
        var escribiendo = /INPUT|TEXTAREA|SELECT/.test((document.activeElement || {}).tagName || '') || (document.activeElement || {}).isContentEditable;
        if (e.key === '/' && !escribiendo) { e.preventDefault(); $('vg-buscar').focus(); }
    });
    var temporizador;
    $('vg-buscar').addEventListener('input', function () {
        clearTimeout(temporizador);
        var valor = this.value;
        temporizador = setTimeout(function () { est.buscar = valor.trim().toLowerCase(); pintar(); }, 150);
    });
    $('vg-proyecto').addEventListener('change', cargar);
    window.addEventListener('resize', cerrarFicha);
    cuerpo.addEventListener('scroll', cerrarFicha, { passive: true });

    // ----------------------------------------------------------------- datos
    function cargar() {
        cargado = false;
        cuerpo.innerHTML = '<div class="vg-vacio">Cargando cronograma…</div>';
        var url = new URL(app.dataset.url, window.location.origin);
        url.searchParams.set('ensayos', 'true');
        if ($('vg-proyecto').value) url.searchParams.set('proyecto', $('vg-proyecto').value);
        fetch(url, { headers: { 'X-Requested-With': 'XMLHttpRequest' }, credentials: 'same-origin' })
            .then(function (r) { if (!r.ok) throw new Error(r.status); return r.json(); })
            .then(function (lista) {
                datos = normalizar(Array.isArray(lista) ? lista : []);
                cargado = true;
                pintar();
            })
            .catch(function () {
                cuerpo.innerHTML = '<div class="vg-vacio"><b>No se pudo cargar el cronograma</b>Revisa tu conexión y vuelve a intentarlo.<br><button type="button" data-reintentar>Reintentar</button></div>';
                var b = cuerpo.querySelector('[data-reintentar]');
                if (b) b.addEventListener('click', cargar);
            });
    }

    pintar();
    cargar();
})();
