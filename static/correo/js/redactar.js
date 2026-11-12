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
    if (subir) {
        subir.addEventListener('change', function () {
            var archivos = Array.prototype.slice.call(subir.files);
            subir.value = '';
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
        });
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

    // --------------------------------------------- autocompletar direcciones
    document.querySelectorAll('[data-autocompletar]').forEach(function (input) {
        var lista = document.getElementById(input.getAttribute('aria-controls'));
        var opciones = [];
        var activa = -1;
        var espera = null;
        var cerrar = function () {
            lista.hidden = true; activa = -1;
            input.setAttribute('aria-expanded', 'false');
            input.removeAttribute('aria-activedescendant');
        };
        var marcar = function (i) {
            activa = i;
            Array.prototype.forEach.call(lista.children, function (li, j) { li.setAttribute('aria-selected', j === i ? 'true' : 'false'); });
            if (i >= 0) { input.setAttribute('aria-activedescendant', lista.children[i].id); }
        };
        var elegir = function (o) {
            var partes = input.value.split(/[,;]/);
            partes.pop();
            var texto = o.nombre ? o.nombre.replace(/[<>,;]/g, '') + ' <' + o.correo + '>' : o.correo;
            partes.push(' ' + texto);
            input.value = partes.map(function (p) { return p.trim(); }).filter(Boolean).join(', ') + ', ';
            sucio = true;
            cerrar();
            input.focus();
        };
        var actual = function () { return (input.value.split(/[,;]/).pop() || '').trim(); };
        input.addEventListener('input', function () {
            window.clearTimeout(espera);
            var q = actual();
            if (q.length < 2) { cerrar(); return; }
            espera = window.setTimeout(function () {
                pedir(form.dataset.contactos + '?q=' + encodeURIComponent(q)).then(function (r) {
                    opciones = r.resultados;
                    lista.textContent = '';
                    if (!opciones.length) { cerrar(); return; }
                    opciones.forEach(function (o, i) {
                        var li = crear('li', { role: 'option', id: lista.id + '-' + i, 'aria-selected': 'false' });
                        li.appendChild(crear('strong', {}, o.nombre || o.correo));
                        li.appendChild(crear('span', { 'class': 'mono' }, o.correo));
                        if (o.detalle) { li.appendChild(crear('small', {}, o.detalle)); }
                        li.addEventListener('mousedown', function (e) { e.preventDefault(); elegir(o); });
                        lista.appendChild(li);
                    });
                    lista.hidden = false;
                    input.setAttribute('aria-expanded', 'true');
                    marcar(0);
                }).catch(cerrar);
            }, 200);
        });
        input.addEventListener('keydown', function (e) {
            if (lista.hidden) { return; }
            if (e.key === 'ArrowDown') { e.preventDefault(); marcar(Math.min(activa + 1, opciones.length - 1)); }
            else if (e.key === 'ArrowUp') { e.preventDefault(); marcar(Math.max(activa - 1, 0)); }
            else if ((e.key === 'Enter' || e.key === 'Tab') && activa >= 0) { e.preventDefault(); elegir(opciones[activa]); }
            else if (e.key === 'Escape') { cerrar(); }
        });
        input.addEventListener('blur', function () { window.setTimeout(cerrar, 150); });
    });
})();
