/* Correo VICAF: editor (Quill 2), autoguardado, destinatarios, adjuntos,
   cotizaciones del LIMS y firmas. Sirve también al formulario de firmas. */
(function () {
    'use strict';

    var form = document.getElementById('form-redactar') || document.querySelector('[data-form-firma]');
    if (!form) { return; }
    var esCorreo = form.id === 'form-redactar';
    var respaldo = document.getElementById('cuerpo-html');
    var contenedor = form.querySelector('[data-editor]');
    var csrf = form.querySelector('input[name="csrfmiddlewaretoken"]').value;
    var quill = null;
    var sucio = false;
    var $ = function (sel) { return form.querySelector(sel) || document.querySelector(sel); };

    var pedir = function (url, opciones) {
        opciones = opciones || {};
        opciones.headers = Object.assign({ 'X-CSRFToken': csrf, 'x-requested-with': 'fetch' }, opciones.headers || {});
        opciones.credentials = 'same-origin';
        return fetch(url, opciones).then(function (r) {
            return r.json().catch(function () { return {}; }).then(function (datos) {
                if (!r.ok) { throw new Error(datos.error || 'No se pudo completar la acción (' + r.status + ').'); }
                return datos;
            });
        });
    };
    var peso = function (n) {
        if (n < 1024) { return n + ' B'; }
        if (n < 1048576) { return (n / 1024).toFixed(0) + ' KB'; }
        return (n / 1048576).toFixed(1) + ' MB';
    };
    var crear = function (etiqueta, atributos, texto) {
        var el = document.createElement(etiqueta);
        Object.keys(atributos || {}).forEach(function (k) { el.setAttribute(k, atributos[k]); });
        if (texto) { el.textContent = texto; }
        return el;
    };

    // ------------------------------------------------------------ editor
    var FUENTES = [['', 'Plus Jakarta Sans'], ['Arial', 'Arial'], ['Verdana', 'Verdana'], ['Tahoma', 'Tahoma'],
        ['Georgia', 'Georgia'], ['Times New Roman', 'Times New Roman'], ['Courier New', 'Courier New']];
    var TAMANOS = [['12px', 'Pequeño'], ['', 'Normal'], ['18px', 'Grande'], ['24px', 'Muy grande'], ['32px', 'Enorme']];

    var barra = function () {
        var t = crear('div', { 'class': 'editor__barra', role: 'toolbar', 'aria-label': 'Formato' });
        var grupo = function () { var g = crear('span', { 'class': 'ql-formats' }); t.appendChild(g); return g; };
        var selector = function (g, clase, opciones, etiqueta) {
            var s = crear('select', { 'class': clase, 'aria-label': etiqueta });
            opciones.forEach(function (o) {
                var op = crear('option', o[0] ? { value: o[0] } : { selected: 'selected' }, o[1]);
                s.appendChild(op);
            });
            g.appendChild(s);
        };
        var boton = function (g, clase, valor, etiqueta) {
            var b = crear('button', { type: 'button', 'class': clase, 'aria-label': etiqueta, title: etiqueta });
            if (valor) { b.value = valor; }
            g.appendChild(b);
        };
        var g = grupo();
        selector(g, 'ql-font', FUENTES, 'Fuente');
        selector(g, 'ql-size', TAMANOS, 'Tamaño');
        g = grupo();
        boton(g, 'ql-bold', '', 'Negrita'); boton(g, 'ql-italic', '', 'Cursiva');
        boton(g, 'ql-underline', '', 'Subrayado'); boton(g, 'ql-strike', '', 'Tachado');
        g = grupo();
        var s = crear('select', { 'class': 'ql-color', 'aria-label': 'Color de texto' }); g.appendChild(s);
        s = crear('select', { 'class': 'ql-background', 'aria-label': 'Resaltado' }); g.appendChild(s);
        g = grupo();
        boton(g, 'ql-list', 'ordered', 'Lista numerada'); boton(g, 'ql-list', 'bullet', 'Lista con viñetas');
        selector(g, 'ql-align', [['', 'Izquierda'], ['center', 'Centro'], ['right', 'Derecha'], ['justify', 'Justificado']], 'Alineación');
        g = grupo();
        boton(g, 'ql-link', '', 'Enlace'); boton(g, 'ql-image', '', 'Insertar imagen');
        boton(g, 'ql-clean', '', 'Quitar formato');
        return t;
    };

    var html = function () {
        if (!quill) { return respaldo.value; }
        var salida = quill.getSemanticHTML();
        // Quill 2.0.3 convierte todos los espacios en &nbsp;: se devuelven a espacios normales.
        salida = salida.replace(/&nbsp;/g, ' ').replace(/<p><\/p>/g, '<p><br></p>');
        return salida;
    };
    var sincronizar = function () { respaldo.value = html(); };

    var subirImagen = function () {
        var input = crear('input', { type: 'file', accept: 'image/png,image/jpeg,image/gif,image/webp' });
        input.addEventListener('change', function () {
            var archivo = input.files[0];
            if (!archivo) { return; }
            var rango = quill.getSelection(true);
            if (!esCorreo) {
                // Firma: la imagen va dentro del HTML (data:), sin adjunto.
                if (archivo.size > 200 * 1024) { window.alert('Usa una imagen de menos de 200 KB para la firma.'); return; }
                var lector = new FileReader();
                lector.onload = function () { quill.insertEmbed(rango.index, 'image', lector.result, 'user'); };
                lector.readAsDataURL(archivo);
                return;
            }
            var datos = new FormData();
            datos.append('archivo', archivo);
            datos.append('incrustado', '1');
            pedir(form.dataset.adjuntos, { method: 'POST', body: datos }).then(function (r) {
                quill.insertEmbed(rango.index, 'image', r.url, 'user');
                pintarPeso(r);
            }).catch(function (err) { avisar(err.message); });
        });
        input.click();
    };

    if (window.Quill && contenedor) {
        var Quill = window.Quill;
        var Fuente = Quill.import('attributors/style/font');
        Fuente.whitelist = FUENTES.map(function (f) { return f[0]; }).filter(Boolean);
        Quill.register(Fuente, true);
        var Tamano = Quill.import('attributors/style/size');
        Tamano.whitelist = TAMANOS.map(function (t) { return t[0]; }).filter(Boolean);
        Quill.register(Tamano, true);
        Quill.register(Quill.import('attributors/style/align'), true);
        Quill.register(Quill.import('attributors/style/color'), true);
        Quill.register(Quill.import('attributors/style/background'), true);

        var herramientas = barra();
        contenedor.parentNode.insertBefore(herramientas, contenedor);
        quill = new Quill(contenedor, {
            theme: 'snow',
            placeholder: esCorreo ? 'Escribe tu mensaje…' : 'Nombre, cargo, teléfono…',
            modules: { toolbar: { container: herramientas, handlers: { image: subirImagen } } }
        });
        quill.clipboard.dangerouslyPasteHTML(0, respaldo.value || '', 'silent');
        quill.setSelection(0, 0, 'silent');
        quill.root.setAttribute('aria-label', esCorreo ? 'Cuerpo del mensaje' : 'Firma');
        quill.root.setAttribute('role', 'textbox');
        quill.root.setAttribute('aria-multiline', 'true');
        respaldo.hidden = true;
        respaldo.classList.add('oculto');
        quill.on('text-change', function () { sucio = true; });
    }

    form.addEventListener('submit', function () { sincronizar(); sucio = false; });

    if (!esCorreo) { return; }

    // ------------------------------------------------------- autoguardado
    var estado = document.querySelector('[data-estado-guardado]');
    form.addEventListener('input', function () { sucio = true; });
    var guardar = function (alSalir) {
        if (!sucio) { return; }
        sincronizar();
        sucio = false;
        if (estado) { estado.textContent = 'Guardando…'; }
        pedir(form.dataset.guardar, { method: 'POST', body: new FormData(form), keepalive: !!alSalir })
            .then(function (r) {
                if (estado) { estado.textContent = 'Guardado ' + r.guardado; }
            })
            .catch(function () {
                sucio = true;
                if (estado) { estado.textContent = 'Sin guardar'; }
            });
    };
    window.setInterval(guardar, 15000);
    document.addEventListener('visibilitychange', function () { if (document.visibilityState === 'hidden') { guardar(true); } });

    // ---------------------------------------------------------- adjuntos
    var aviso = document.querySelector('[data-aviso-adjuntos]');
    var avisar = function (texto) { if (aviso) { aviso.textContent = texto || ''; } };
    var barraPeso = document.querySelector('[data-peso]');
    var textoPeso = document.querySelector('[data-peso-texto]');
    var listaAdj = document.querySelector('[data-lista-adjuntos]');
    var estadoAdj = { total: barraPeso ? Number(barraPeso.value) : 0, maximo: barraPeso ? Number(barraPeso.max) : 0, n: 0 };

    var pintarPeso = function (r) {
        estadoAdj.total = r.total; estadoAdj.maximo = r.maximo;
        if (barraPeso) { barraPeso.max = r.maximo; barraPeso.value = r.total; }
        if (textoPeso) { textoPeso.textContent = peso(r.total) + ' de ' + peso(r.maximo); }
    };
    var pintarAdjuntos = function (r) {
        pintarPeso(r);
        estadoAdj.n = r.adjuntos.length;
        listaAdj.textContent = '';
        r.adjuntos.forEach(function (a) {
            var li = crear('li', { 'class': 'adjunto', 'data-id': a.id });
            var enlace = crear('a', { 'class': 'adjunto__nombre', href: a.url, download: '' }, a.nombre);
            var pesoEl = crear('span', { 'class': 'adjunto__peso mono' }, peso(a.tamano));
            var quitar = crear('button', { type: 'button', 'class': 'boton-icono boton-icono--chico', 'aria-label': 'Quitar ' + a.nombre, title: 'Quitar' }, '×');
            quitar.addEventListener('click', function () {
                pedir(form.dataset.quitar.replace('/0/', '/' + a.id + '/'), { method: 'POST' })
                    .then(pintarAdjuntos).catch(function (err) { avisar(err.message); });
            });
            li.appendChild(enlace); li.appendChild(pesoEl); li.appendChild(quitar);
            listaAdj.appendChild(li);
        });
    };
    if (listaAdj) {
        pedir(form.dataset.adjuntos).then(pintarAdjuntos).catch(function () { /* queda la lista del servidor */ });
    }

    var subir = document.querySelector('[data-subir]');
    var subirArchivos = function (archivos) {
            var siguiente = function () {
                var archivo = archivos.shift();
                if (!archivo) { avisar(''); return; }
                if (estadoAdj.total + archivo.size > estadoAdj.maximo) {
                    avisar('«' + archivo.name + '» no cabe: el límite es ' + peso(estadoAdj.maximo) + ' por correo.');
                    return;
                }
                avisar('Subiendo «' + archivo.name + '»…');
                var datos = new FormData();
                datos.append('archivo', archivo);
                pedir(form.dataset.adjuntos, { method: 'POST', body: datos })
                    .then(function (r) { pintarAdjuntos(r); siguiente(); })
                    .catch(function (err) { avisar(err.message); });
            };
            siguiente();
    };
    if (subir) {
        subir.addEventListener('change', function () {
            var archivos = Array.prototype.slice.call(subir.files);
            subir.value = '';
            subirArchivos(archivos);
        });
        // Arrastrar archivos sobre el correo los adjunta (también sobre el editor).
        var zona = document.querySelector('[data-zona-soltar]');
        var conArchivos = function (e) { return e.dataTransfer && Array.prototype.indexOf.call(e.dataTransfer.types, 'Files') >= 0; };
        var profundidad = 0;
        form.addEventListener('dragenter', function (e) {
            if (!conArchivos(e)) { return; }
            profundidad += 1;
            if (zona) { zona.hidden = false; }
        }, true);
        form.addEventListener('dragleave', function (e) {
            if (!conArchivos(e)) { return; }
            profundidad = Math.max(0, profundidad - 1);
            if (zona && !profundidad) { zona.hidden = true; }
        }, true);
        form.addEventListener('dragover', function (e) { if (conArchivos(e)) { e.preventDefault(); } }, true);
        form.addEventListener('drop', function (e) {
            if (!conArchivos(e)) { return; }
            e.preventDefault();
            e.stopPropagation();
            profundidad = 0;
            if (zona) { zona.hidden = true; }
            subirArchivos(Array.prototype.slice.call(e.dataTransfer.files));
        }, true);
    }

    // ------------------------------------------------------ cotizaciones
    var dialogo = document.querySelector('[data-dialogo-cotizaciones]');
    var abrirCot = document.querySelector('[data-abrir-cotizaciones]');
    if (dialogo && abrirCot) {
        var buscador = dialogo.querySelector('[data-buscar-cotizacion]');
        var resultados = dialogo.querySelector('[data-resultados-cotizacion]');
        var espera = null;
        var buscarCot = function () {
            pedir(form.dataset.cotizaciones + '?q=' + encodeURIComponent(buscador.value.trim())).then(function (r) {
                resultados.textContent = '';
                if (!r.resultados.length) { resultados.appendChild(crear('li', { 'class': 'nota' }, 'Sin resultados.')); }
                r.resultados.forEach(function (c) {
                    var li = crear('li');
                    var b = crear('button', { type: 'button', 'class': 'resultado-cot' });
                    b.appendChild(crear('strong', {}, c.numero));
                    b.appendChild(crear('span', {}, c.cliente + (c.asunto ? ' · ' + c.asunto : '')));
                    b.appendChild(crear('small', { 'class': 'mono' }, c.fecha + ' · ' + c.estado));
                    b.addEventListener('click', function () { adjuntarCot(c); });
                    li.appendChild(b);
                    resultados.appendChild(li);
                });
            }).catch(function (err) { resultados.textContent = err.message; });
        };
        var adjuntarCot = function (c) {
            dialogo.close();
            var antes = estadoAdj.n;
            var datos = new FormData();
            datos.append('cotizacion', c.id);
            avisar('Generando el PDF de la cotización ' + c.numero + '…');
            pedir(form.dataset.cotizacion, { method: 'POST', body: datos }).then(function () {
                var intentos = 0;
                var revisar = function () {
                    intentos += 1;
                    pedir(form.dataset.adjuntos).then(function (r) {
                        if (r.adjuntos.length > antes) { pintarAdjuntos(r); avisar('Cotización ' + c.numero + ' adjunta.'); }
                        else if (intentos < 20) { window.setTimeout(revisar, 2000); }
                        else { avisar('La cotización tarda más de lo normal; revisa en un momento.'); }
                    });
                };
                window.setTimeout(revisar, 1500);
            }).catch(function (err) { avisar(err.message); });
        };
        abrirCot.addEventListener('click', function () {
            dialogo.showModal();
            buscador.focus();
            buscarCot();
        });
        buscador.addEventListener('input', function () {
            window.clearTimeout(espera);
            espera = window.setTimeout(buscarCot, 250);
        });
        dialogo.querySelector('[data-cerrar]').addEventListener('click', function () { dialogo.close(); });
    }

    // ------------------------------------------------------------- firmas
    var selFirma = document.querySelector('[data-insertar-firma]');
    if (selFirma && quill) {
        selFirma.addEventListener('change', function () {
            var fuente = document.querySelector('textarea[data-firma-html="' + selFirma.value + '"]');
            if (fuente) {
                var rango = quill.getSelection() || { index: quill.getLength() };
                quill.clipboard.dangerouslyPasteHTML(rango.index, fuente.value, 'user');
            }
            selFirma.value = '';
        });
    }

    // ------------------------------- destinatarios como «chips» + autocompletado
    // El campo visible solo sirve para escribir; lo que se envía y autoguarda es
    // un input oculto con el mismo `name` («Nombre <correo>, …»). Sin JS, el
    // campo de texto sigue funcionando como antes.
    var CORREO = /^[^\s@<>(),;:"]+@[^\s@<>(),;:"]+\.[^\s@<>(),;:"]+$/;
    var trocear = function (texto) {
        return (String(texto || '').match(/(?:"[^"]*"|<[^>]*>|[^,;"<])+/g) || [])
            .map(function (t) { return t.trim(); }).filter(Boolean);
    };
    var leer = function (t) {
        var m = t.match(/^(.*)<([^>]*)>\s*$/);
        var nombre = m ? m[1].replace(/"/g, '').trim() : '';
        var correo = (m ? m[2] : t.replace(/"/g, '')).trim().toLowerCase();
        return { nombre: nombre, correo: correo };
    };
    var formatear = function (p) {
        var nombre = (p.nombre || '').replace(/"/g, '').trim();
        if (!nombre) { return p.correo; }
        return (/[,;<>@]/.test(nombre) ? '"' + nombre + '"' : nombre) + ' <' + p.correo + '>';
    };
    var campos = [];
    var elegidos = function () {
        var todos = [];
        campos.forEach(function (c) { c.personas.forEach(function (p) { todos.push(p.correo); }); });
        return todos;
    };
    var iniciales = function (p) {
        var base = (p.nombre || p.correo.split('@')[0]).replace(/[^\p{L}\p{N} ._-]/gu, ' ');
        var partes = base.split(/[\s._-]+/).filter(Boolean);
        return ((partes[0] || '?').charAt(0) + (partes.length > 1 ? partes[partes.length - 1].charAt(0) : '')).toUpperCase();
    };

    document.querySelectorAll('[data-autocompletar]').forEach(function (input) {
        var caja = input.closest('.autocompletar');
        var lista = document.getElementById(input.getAttribute('aria-controls'));
        var oculto = crear('input', { type: 'hidden', name: input.name });
        input.removeAttribute('name');
        caja.appendChild(oculto);
        caja.classList.add('destinatarios');
        var fichas = crear('span', { 'class': 'destinatarios__fichas' });
        caja.insertBefore(fichas, input);
        var campo = { input: input, personas: [] };
        campos.push(campo);
        var etiqueta = (document.querySelector('label[for="' + input.id + '"]') || {}).textContent || '';
        var opciones = [];
        var activa = -1;
        var espera = null;
        var ultimaConsulta = null;

        var volcar = function () {
            var textos = campo.personas.map(formatear);
            if (input.value.trim()) { textos.push(input.value.trim()); }
            oculto.value = textos.join(', ');
            input.placeholder = campo.personas.length ? '' : (input.dataset.placeholder || '');
        };
        var pintar = function () {
            fichas.textContent = '';
            campo.personas.forEach(function (p, i) {
                var valido = CORREO.test(p.correo);
                var ficha = crear('span', {
                    'class': 'ficha' + (valido ? '' : ' ficha--invalida'), tabindex: '-1', 'data-correo': p.correo,
                    title: valido ? p.correo : p.correo + ' no es un correo válido',
                });
                ficha.appendChild(crear('span', { 'class': 'ficha__texto' }, p.nombre || p.correo));
                var quitar = crear('button', {
                    type: 'button', 'class': 'ficha__quitar', tabindex: '-1',
                    'aria-label': 'Quitar ' + (p.nombre ? p.nombre + ' (' + p.correo + ')' : p.correo) + ' de ' + etiqueta,
                }, '×');
                quitar.addEventListener('click', function () { borrar(i); input.focus(); });
                ficha.appendChild(quitar);
                ficha.addEventListener('keydown', function (e) {
                    if (e.key === 'Backspace' || e.key === 'Delete') {
                        e.preventDefault(); borrar(i);
                        var resto = fichas.children;
                        if (resto.length) { resto[Math.min(i, resto.length - 1)].focus(); } else { input.focus(); }
                    } else if (e.key === 'ArrowLeft' && ficha.previousSibling) { e.preventDefault(); ficha.previousSibling.focus(); }
                    else if (e.key === 'ArrowRight') { e.preventDefault(); (ficha.nextSibling || input).focus(); }
                    else if (e.key === 'Enter' || e.key === 'F2') { e.preventDefault(); editar(i); }
                });
                ficha.addEventListener('dblclick', function () { editar(i); });
                fichas.appendChild(ficha);
            });
            volcar();
        };
        var cambio = function () { sucio = true; pintar(); };
        var borrar = function (i) { campo.personas.splice(i, 1); cambio(); };
        var editar = function (i) {
            var p = campo.personas.splice(i, 1)[0];
            if (input.value.trim()) { agregarTexto(input.value); }
            input.value = formatear(p);
            cambio();
            input.focus();
            input.select();
        };
        var agregar = function (p) {
            if (!p.correo) { return; }
            var ya = campo.personas.some(function (q) { return q.correo === p.correo; });
            if (!ya) { campo.personas.push(p); }
        };
        var agregarTexto = function (texto) {
            trocear(texto).forEach(function (t) { agregar(leer(t)); });
        };
        var confirmar = function () {
            if (!input.value.trim()) { return false; }
            agregarTexto(input.value);
            input.value = '';
            cambio();
            return true;
        };
        campo.confirmar = confirmar;

        var cerrar = function () {
            lista.hidden = true; activa = -1;
            input.setAttribute('aria-expanded', 'false');
            input.removeAttribute('aria-activedescendant');
        };
        var elegir = function (o) {
            agregar({ nombre: o.nombre, correo: o.correo });
            input.value = '';
            cambio();
            cerrar();
            input.focus();
        };
        var buscar = function () {
            var q = input.value.trim();
            var url = form.dataset.contactos + '?q=' + encodeURIComponent(q) + '&excluir=' + encodeURIComponent(elegidos().join(','));
            ultimaConsulta = url;
            pedir(url).then(function (r) {
                if (url !== ultimaConsulta || document.activeElement !== input) { return; }
                opciones = r.resultados || [];
                lista.textContent = '';
                if (!opciones.length) { cerrar(); return; }
                if (!q) { lista.appendChild(crear('li', { role: 'presentation', 'class': 'sugerencias__titulo' }, 'Contactos recientes')); }
                opciones.forEach(function (o, i) {
                    var li = crear('li', { role: 'option', id: lista.id + '-' + i, 'aria-selected': 'false', 'class': 'sugerencia' });
                    li.appendChild(crear('span', { 'class': 'avatar avatar--' + (o.tipo || 'reciente'), 'aria-hidden': 'true' }, iniciales(o)));
                    var texto = crear('span', { 'class': 'sugerencia__texto' });
                    texto.appendChild(crear('strong', {}, o.nombre || o.correo));
                    texto.appendChild(crear('span', { 'class': 'mono' }, o.correo));
                    li.appendChild(texto);
                    if (o.detalle) { li.appendChild(crear('small', { 'class': 'sugerencia__detalle' }, o.detalle)); }
                    li.addEventListener('mousedown', function (e) { e.preventDefault(); elegir(o); });
                    lista.appendChild(li);
                });
                // El título no es una opción: los índices de `opciones` van tras él.
                if (!q) { lista.firstChild.id = lista.id + '-t'; }
                lista.hidden = false;
                input.setAttribute('aria-expanded', 'true');
                marcar(q ? 0 : -1);
            }).catch(cerrar);
        };
        var opcionLi = function (i) { return lista.querySelector('#' + lista.id + '-' + i); };
        var marcar = function (i) {
            activa = i;
            Array.prototype.forEach.call(lista.querySelectorAll('[role="option"]'), function (li) { li.setAttribute('aria-selected', 'false'); });
            var li = i >= 0 ? opcionLi(i) : null;
            if (li) {
                li.setAttribute('aria-selected', 'true');
                input.setAttribute('aria-activedescendant', li.id);
                li.scrollIntoView({ block: 'nearest' });
            } else { input.removeAttribute('aria-activedescendant'); }
        };
        var programar = function () { window.clearTimeout(espera); espera = window.setTimeout(buscar, 150); };

        input.addEventListener('input', function () {
            if (/[,;]/.test(input.value) && !/"[^"]*$/.test(input.value)) {
                var partes = trocear(input.value);
                var cola = /[,;]\s*$/.test(input.value) ? '' : partes.pop() || '';
                partes.forEach(function (t) { agregar(leer(t)); });
                input.value = cola;
                cambio();
            } else { volcar(); }
            programar();
        });
        input.addEventListener('focus', function () { caja.classList.add('destinatarios--foco'); if (!input.value.trim()) { programar(); } });
        input.addEventListener('paste', function (e) {
            var texto = (e.clipboardData || window.clipboardData).getData('text');
            if (trocear(texto).length > 1) { e.preventDefault(); agregarTexto(input.value + ',' + texto); input.value = ''; cambio(); cerrar(); }
        });
        input.addEventListener('keydown', function (e) {
            var abierta = !lista.hidden && opciones.length;
            if (e.key === 'ArrowDown' && abierta) { e.preventDefault(); marcar(Math.min(activa + 1, opciones.length - 1)); }
            else if (e.key === 'ArrowUp' && abierta) { e.preventDefault(); marcar(Math.max(activa - 1, 0)); }
            else if ((e.key === 'Enter' || e.key === 'Tab') && abierta && activa >= 0) { e.preventDefault(); elegir(opciones[activa]); }
            else if (e.key === 'Enter') { e.preventDefault(); if (confirmar()) { cerrar(); programar(); } }
            else if (e.key === 'Escape' && abierta) { e.preventDefault(); cerrar(); }
            else if ((e.key === 'Backspace' || e.key === 'ArrowLeft') && !input.value && fichas.lastChild) {
                e.preventDefault(); fichas.lastChild.focus();
            }
        });
        input.addEventListener('blur', function () {
            caja.classList.remove('destinatarios--foco');
            window.setTimeout(function () { cerrar(); }, 150);
            confirmar();
        });
        caja.addEventListener('mousedown', function (e) {
            if (e.target === caja || e.target === fichas) { e.preventDefault(); input.focus(); }
        });

        input.dataset.placeholder = input.getAttribute('placeholder') || '';
        agregarTexto(input.value);
        input.value = '';
        pintar();
    });
    form.addEventListener('submit', function () { campos.forEach(function (c) { c.confirmar(); }); }, true);

    // CC y CCO ocultos hasta pedirlos (o si ya traen direcciones), como en Outlook.
    document.querySelectorAll('[data-mostrar-campo]').forEach(function (boton) {
        var campo = boton.dataset.mostrarCampo;
        var partes = form.querySelectorAll('[data-fila-campo="' + campo + '"]');
        var oculto = form.querySelector('input[type="hidden"][name="' + campo + '"]');
        var mostrar = function (enfocar) {
            partes.forEach(function (el) { el.hidden = false; });
            boton.hidden = true;
            if (enfocar) { document.getElementById('r-' + campo).focus(); }
        };
        if (oculto && oculto.value.trim()) { mostrar(false); }
        else { partes.forEach(function (el) { el.hidden = true; }); }
        boton.addEventListener('click', function () { mostrar(true); });
    });

    // Ctrl+Enter envía (como Outlook).
    form.addEventListener('keydown', function (e) {
        if (e.key === 'Enter' && (e.ctrlKey || e.metaKey)) {
            e.preventDefault();
            if (form.requestSubmit) { form.requestSubmit(); } else { form.submit(); }
        }
    });
})();
