/* Editor del informe tipo Word (fase 2). Usa TipTap 2.27.1 empaquetado en
 * static/vendor/tiptap-2.27.1 (window.TiptapVicaf).
 *
 * Los «bloques de datos» son nodos atómicos: se pueden mover o quitar, pero su
 * contenido viene del servidor y no se escribe a mano. Se guarda solo
 * (1,5 s después de dejar de escribir) con control de versión: si otra persona
 * guardó antes, no se pisa su trabajo. */
(function () {
    'use strict';
    const raiz = document.querySelector('[data-editor-informe]');
    if (!raiz || !window.TiptapVicaf) return;
    const T = window.TiptapVicaf;
    const contenido = JSON.parse(document.getElementById('informe-contenido').textContent);
    const bloques = JSON.parse(document.getElementById('informe-bloques').textContent);
    const soloLectura = raiz.dataset.soloLectura === '1';
    const puedeEditarDatos = raiz.dataset.editarDatos === '1' && !soloLectura;
    const convertibles = (raiz.dataset.convertibles || '').split(',');
    const urlGuardar = raiz.dataset.guardarUrl;
    const csrfInput = document.querySelector('[name=csrfmiddlewaretoken]');
    const csrf = csrfInput ? csrfInput.value : '';
    const estado = raiz.querySelector('[data-estado]');
    const avisoFaltan = raiz.querySelector('[data-faltan]');
    const listaFaltan = raiz.querySelector('[data-faltan-lista]');
    const btnEmitir = raiz.querySelector('[data-emitir]');
    let version = parseInt(raiz.dataset.version, 10);

    const ETIQUETAS = {
        caratula: 'Dato del sistema · Datos del cliente y del ensayo',
        resultados: 'Dato del sistema · Resultados',
        fotos: 'Dato del sistema · Registro fotográfico',
        equipos: 'Dato del sistema · Equipos y condiciones',
        firmas: 'Dato del sistema · Firmas',
        notas: 'Dato del sistema · Notas del laboratorio',
    };

    const BloqueDatos = T.Node.create({
        name: 'bloqueDatos',
        group: 'block',
        atom: true,
        draggable: true,
        selectable: true,
        addAttributes: function () {
            return { tipo: { default: '' }, ref: { default: '' } };
        },
        parseHTML: function () {
            return [{
                tag: 'div[data-bloque]',
                getAttrs: function (el) { return { tipo: el.dataset.bloque, ref: el.dataset.ref || '' }; },
            }];
        },
        renderHTML: function (props) {
            return ['div', { 'data-bloque': props.HTMLAttributes.tipo, 'data-ref': props.HTMLAttributes.ref }];
        },
        addNodeView: function () {
            return function (props) {
                const caja = document.createElement('div');
                const tipo = props.node.attrs.tipo;
                const ref = props.node.attrs.ref;
                const clave = ref ? tipo + ':' + ref : tipo;
                caja.className = 'bloque-dato';
                caja.contentEditable = 'false';
                caja.dataset.clave = clave;
                // Cabecera: se arrastra o selecciona el bloque desde aquí.
                const cab = document.createElement('div');
                cab.className = 'bloque-dato__cab';
                cab.dataset.asa = '';
                const etiqueta = document.createElement('span');
                etiqueta.textContent = ETIQUETAS[tipo] || 'Dato del sistema';
                cab.appendChild(etiqueta);
                const html = bloques[clave];
                if (puedeEditarDatos && html && convertibles.indexOf(tipo) >= 0) {
                    const btn = document.createElement('button');
                    btn.type = 'button';
                    btn.className = 'bloque-dato__convertir';
                    btn.dataset.convertir = '';
                    btn.textContent = 'Convertir en texto editable';
                    btn.addEventListener('click', function (ev) {
                        ev.preventDefault();
                        ev.stopPropagation();
                        if (btn.dataset.paso !== 'confirmar') {
                            btn.dataset.paso = 'confirmar';
                            btn.textContent = '¿Seguro? Ya no se actualizará solo';
                            setTimeout(function () {
                                if (btn.isConnected) { btn.dataset.paso = ''; btn.textContent = 'Convertir en texto editable'; }
                            }, 5000);
                            return;
                        }
                        convertirEnTexto(props.getPos(), props.node, html);
                    });
                    cab.appendChild(btn);
                }
                caja.appendChild(cab);
                const cuerpo = document.createElement('div');
                cuerpo.className = 'bloque-dato__cuerpo';
                // HTML generado por el servidor desde nuestras plantillas (con autoescape).
                cuerpo.innerHTML = html || '<p class="bloque--vacio">Este dato ya no está disponible.</p>';
                caja.appendChild(cuerpo);
                // El bloque es arrastrable desde la cabecera; en el cuerpo se
                // desactiva el arrastre para que el ratón seleccione texto.
                cuerpo.addEventListener('mousedown', function () {
                    caja.draggable = false;
                    document.addEventListener('mouseup', function () { caja.draggable = true; }, { once: true });
                });
                return {
                    dom: caja,
                    // Dentro del cuerpo manda el navegador: se selecciona y copia
                    // letra por letra, como en Word, pero no se escribe.
                    stopEvent: function (ev) {
                        return !!(ev.target && ev.target.closest && ev.target.closest('.bloque-dato__cuerpo, [data-convertir]'));
                    },
                    ignoreMutation: function () { return true; },
                };
            };
        },
    });

    // Bloque de datos convertido en texto: su contenido se edita como el
    // resto, pero solo quien tiene el permiso (el servidor también lo exige).
    const BloqueEditado = T.Node.create({
        name: 'bloqueEditado',
        group: 'block',
        content: 'block+',
        defining: true,
        isolating: true,
        addAttributes: function () {
            return { tipo: { default: '' }, ref: { default: '' } };
        },
        parseHTML: function () {
            return [{
                tag: 'div[data-bloque-editado]',
                getAttrs: function (el) { return { tipo: el.dataset.bloqueEditado, ref: el.dataset.ref || '' }; },
            }];
        },
        renderHTML: function (props) {
            return ['div', {
                'data-bloque-editado': props.HTMLAttributes.tipo, 'data-ref': props.HTMLAttributes.ref,
                'class': 'bloque-editado', 'contenteditable': puedeEditarDatos ? 'true' : 'false',
            }, 0];
        },
    });

    function convertirEnTexto(pos, nodo, html) {
        if (typeof pos !== 'number') return;
        const envoltura = document.createElement('div');
        envoltura.dataset.bloqueEditado = nodo.attrs.tipo;
        envoltura.dataset.ref = nodo.attrs.ref || '';
        envoltura.innerHTML = html;
        // Las imágenes no se convierten (fotos y firmas no son convertibles).
        envoltura.querySelectorAll('img').forEach(function (i) { i.remove(); });
        editor.chain().focus().insertContentAt({ from: pos, to: pos + nodo.nodeSize }, envoltura.outerHTML).run();
    }

    const editor = new T.Editor({
        element: raiz.querySelector('[data-hoja]'),
        editable: !soloLectura,
        content: contenido,
        extensions: [
            T.StarterKit.configure({ heading: { levels: [1, 2, 3] }, code: false, codeBlock: false, blockquote: false }),
            T.Underline,
            T.TextAlign.configure({ types: ['heading', 'paragraph'] }),
            T.Table.configure({ resizable: false }),
            T.TableRow, T.TableHeader, T.TableCell,
            T.Placeholder.configure({ placeholder: 'Escribe aquí…' }),
            BloqueDatos,
            BloqueEditado,
        ],
    });

    // ---------- Pantalla completa (como Word) ----------
    // El editor se abre a pantalla completa; «Salir» vuelve a la vista con el menú.
    const btnPantalla = raiz.querySelector('[data-pantalla]');
    const hoja = raiz.querySelector('[data-hoja]');
    function pantallaCompleta(activar) {
        raiz.classList.toggle('ed-completo', activar);
        document.documentElement.style.overflow = activar ? 'hidden' : '';
        if (!activar && document.fullscreenElement) document.exitFullscreen().catch(function () {});
    }
    if (btnPantalla) {
        btnPantalla.addEventListener('click', function () {
            const activar = !raiz.classList.contains('ed-completo');
            pantallaCompleta(activar);
            // Con el clic del usuario también se puede pedir la pantalla completa del navegador.
            if (activar && raiz.requestFullscreen) raiz.requestFullscreen().catch(function () {});
        });
    }
    pantallaCompleta(true);

    const selZoom = raiz.querySelector('[data-zoom]');
    function aplicarZoom(valor) {
        hoja.style.zoom = valor === '1' ? '' : valor;
        try { localStorage.setItem('informe-zoom', valor); } catch (e) { /* sin almacenamiento */ }
    }
    if (selZoom) {
        try {
            const guardado = localStorage.getItem('informe-zoom');
            if (guardado && selZoom.querySelector('option[value="' + guardado + '"]')) selZoom.value = guardado;
        } catch (e) { /* sin almacenamiento */ }
        aplicarZoom(selZoom.value);
        selZoom.addEventListener('change', function () { aplicarZoom(selZoom.value); });
    }

    const txtPalabras = raiz.querySelector('[data-palabras]');
    const txtPaginas = raiz.querySelector('[data-paginas]');
    const ALTO_A4 = 297 * 96 / 25.4;
    function contar() {
        const texto = editor.state.doc.textBetween(0, editor.state.doc.content.size, ' ', ' ');
        const n = (texto.match(/\S+/g) || []).length;
        if (txtPalabras) txtPalabras.textContent = n.toLocaleString('es-PE') + (n === 1 ? ' palabra' : ' palabras');
        if (txtPaginas) {
            const paginas = Math.max(1, Math.ceil(hoja.scrollHeight / ALTO_A4));
            txtPaginas.textContent = '≈ ' + paginas + (paginas === 1 ? ' página' : ' páginas');
        }
    }
    let temporizadorConteo = null;
    editor.on('update', function () { clearTimeout(temporizadorConteo); temporizadorConteo = setTimeout(contar, 300); });
    contar();

    if (soloLectura) return;

    // ---------- Barra de herramientas ----------
    const ACCIONES = {
        'deshacer': function (c) { return c.undo(); },
        'rehacer': function (c) { return c.redo(); },
        'negrita': function (c) { return c.toggleBold(); },
        'cursiva': function (c) { return c.toggleItalic(); },
        'subrayado': function (c) { return c.toggleUnderline(); },
        'tachado': function (c) { return c.toggleStrike(); },
        'vinetas': function (c) { return c.toggleBulletList(); },
        'numerada': function (c) { return c.toggleOrderedList(); },
        'izquierda': function (c) { return c.setTextAlign('left'); },
        'centro': function (c) { return c.setTextAlign('center'); },
        'derecha': function (c) { return c.setTextAlign('right'); },
        'justificar': function (c) { return c.setTextAlign('justify'); },
        'tabla': function (c) { return c.insertTable({ rows: 3, cols: 3, withHeaderRow: true }); },
        'fila': function (c) { return c.addRowAfter(); },
        'columna': function (c) { return c.addColumnAfter(); },
        'quitar-fila': function (c) { return c.deleteRow(); },
        'quitar-columna': function (c) { return c.deleteColumn(); },
        'quitar-tabla': function (c) { return c.deleteTable(); },
        'linea': function (c) { return c.setHorizontalRule(); },
    };
    const ACTIVOS = {
        negrita: 'bold', cursiva: 'italic', subrayado: 'underline', tachado: 'strike',
        vinetas: 'bulletList', numerada: 'orderedList',
    };
    const botones = raiz.querySelectorAll('[data-cmd]');
    botones.forEach(function (b) {
        b.addEventListener('mousedown', function (ev) { ev.preventDefault(); });
        b.addEventListener('click', function () {
            ACCIONES[b.dataset.cmd](editor.chain().focus()).run();
        });
    });
    const selEstilo = raiz.querySelector('[data-estilo]');
    selEstilo.addEventListener('change', function () {
        const v = selEstilo.value;
        const c = editor.chain().focus();
        (v === 'p' ? c.setParagraph() : c.setHeading({ level: parseInt(v, 10) })).run();
    });
    const selBloque = raiz.querySelector('[data-insertar-bloque]');
    selBloque.addEventListener('change', function () {
        if (!selBloque.value) return;
        const partes = selBloque.value.split('|');
        editor.chain().focus().insertContent({ type: 'bloqueDatos', attrs: { tipo: partes[0], ref: partes[1] || '' } }).run();
        selBloque.value = '';
    });

    function refrescarBarra() {
        botones.forEach(function (b) {
            const cmd = b.dataset.cmd;
            if (ACTIVOS[cmd]) b.classList.toggle('activo', editor.isActive(ACTIVOS[cmd]));
            if (b.hasAttribute('data-tabla')) b.disabled = !editor.isActive('table');
            if (cmd === 'deshacer') b.disabled = !editor.can().undo();
            if (cmd === 'rehacer') b.disabled = !editor.can().redo();
            if (['izquierda', 'centro', 'derecha', 'justificar'].indexOf(cmd) >= 0) {
                const alin = { izquierda: 'left', centro: 'center', derecha: 'right', justificar: 'justify' }[cmd];
                b.classList.toggle('activo', editor.isActive({ textAlign: alin }));
            }
        });
        let nivel = 'p';
        [1, 2, 3].forEach(function (n) { if (editor.isActive('heading', { level: n })) nivel = String(n); });
        selEstilo.value = nivel;
    }
    editor.on('selectionUpdate', refrescarBarra);
    editor.on('transaction', refrescarBarra);
    refrescarBarra();

    // ---------- Autoguardado ----------
    let pendiente = false;
    let guardando = false;
    let conflicto = false;
    let temporizador = null;
    let reintento = 2000;

    function mostrar(texto, tipo) {
        estado.textContent = texto;
        estado.dataset.tipo = tipo || '';
    }

    function actualizarFaltan(faltan) {
        if (!Array.isArray(faltan)) return;
        avisoFaltan.classList.toggle('hidden', faltan.length === 0);
        listaFaltan.textContent = faltan.join(', ');
        if (btnEmitir) btnEmitir.disabled = faltan.length > 0 || conflicto;
    }

    function guardar() {
        if (guardando || conflicto || !pendiente) return Promise.resolve();
        guardando = true;
        pendiente = false;
        mostrar('Guardando…');
        return fetch(urlGuardar, {
            method: 'POST',
            credentials: 'same-origin',
            headers: { 'Content-Type': 'application/json', 'X-CSRFToken': csrf },
            body: JSON.stringify({ version: version, contenido: editor.getJSON() }),
        }).then(function (r) {
            return r.json().catch(function () { return { ok: false, error: 'Respuesta inesperada (' + r.status + ').' }; });
        }).then(function (res) {
            guardando = false;
            if (res.ok) {
                version = res.version;
                reintento = 2000;
                mostrar('Guardado ' + res.guardado_en, 'ok');
                actualizarFaltan(res.faltan);
                if (pendiente) programar();
                return;
            }
            if (res.conflicto) {
                conflicto = true;
                if (btnEmitir) btnEmitir.disabled = true;
            } else {
                pendiente = true;
            }
            mostrar(res.error || 'No se pudo guardar.', 'error');
        }).catch(function () {
            guardando = false;
            pendiente = true;
            mostrar('Sin conexión. Reintentando…', 'error');
            clearTimeout(temporizador);
            temporizador = setTimeout(guardar, reintento);
            reintento = Math.min(reintento * 2, 30000);
        });
    }

    function programar() {
        clearTimeout(temporizador);
        temporizador = setTimeout(guardar, 1500);
    }

    // Al cargar, el editor puede normalizar el documento (p. ej. tablas): eso
    // no es un cambio de la persona y no debe guardarse ni crear versiones.
    let listo = false;
    setTimeout(function () { listo = true; }, 0);
    editor.on('update', function () {
        if (!listo) return;
        pendiente = true;
        if (!conflicto) mostrar('Cambios sin guardar…');
        programar();
    });

    raiz.querySelector('[data-guardar]').addEventListener('click', function () {
        clearTimeout(temporizador);
        pendiente = true;
        guardar();
    });
    document.addEventListener('keydown', function (ev) {
        if ((ev.ctrlKey || ev.metaKey) && ev.key.toLowerCase() === 's') {
            ev.preventDefault();
            clearTimeout(temporizador);
            pendiente = true;
            guardar();
        }
    });
    window.addEventListener('beforeunload', function (ev) {
        if (pendiente || guardando) { ev.preventDefault(); ev.returnValue = ''; }
    });

    // ---------- Emitir: guarda lo pendiente y pide confirmación en dos pasos ----------
    const formEmitir = raiz.querySelector('[data-form-emitir]');
    if (formEmitir && btnEmitir) {
        let confirmado = false;
        const textoOriginal = btnEmitir.innerHTML;
        formEmitir.addEventListener('submit', function (ev) {
            if (confirmado) return;
            ev.preventDefault();
            if (btnEmitir.dataset.paso !== 'confirmar') {
                btnEmitir.dataset.paso = 'confirmar';
                btnEmitir.textContent = '¿Emitir? Ya no se podrá editar';
                setTimeout(function () {
                    if (!confirmado) { btnEmitir.dataset.paso = ''; btnEmitir.innerHTML = textoOriginal; }
                }, 5000);
                return;
            }
            clearTimeout(temporizador);
            guardar().then(function () {
                if (pendiente || conflicto) return;
                confirmado = true;
                btnEmitir.disabled = true;
                btnEmitir.textContent = 'Emitiendo…';
                formEmitir.submit();
            });
        });
    }

    // ---------- Historial ----------
    const btnHistorial = raiz.querySelector('[data-abrir-historial]');
    const historial = raiz.querySelector('[data-historial]');
    btnHistorial.addEventListener('click', function () {
        const abierto = historial.classList.toggle('hidden') === false;
        btnHistorial.setAttribute('aria-expanded', abierto ? 'true' : 'false');
    });

    window.EditorInforme = editor;
})();
