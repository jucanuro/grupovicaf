// Asistente de WhatsApp de la web (VCF-WEB, D-VCF-004; specs/WEB/).
//
// Widget guiado que termina en wa.me con el mensaje armado (opción A). Los
// textos son los aprobados en G1 (docs/proc/VCF-WEB_HU_CU_v1.md, sección 7).
// Saludo, horario, número y catálogo llegan de web_contacto:asistente_datos,
// que los lee de NegocioConfig, LineaServicio y ServicioPublicado.
//
// v2 (HU v1.5, REQ-WEB-20 a 29): la conversación es una pila de pasos
// serializables ({p: 'ensayo', linea: slug, ensayo: slug}) que se guarda en
// sessionStorage. Así, al abrir "Ver en la web" o cualquier otra página, el
// panel vuelve abierto en el mismo paso; si el visitante lo cerró, sigue
// cerrado. Nada de este estado sale del navegador (RN-12).
//
// Preparado para la opción C: todas las respuestas de la cotización viven en
// un solo objeto (`estado.respuestas`); guardar el lead sería un fetch más en
// alEnviarCotizacion().
//
// Las funciones puras se exponen en window.VicafAsistente y en module.exports
// para probarlas con `node --test 'tests/js/*.test.js'`.
(function (raiz) {
    'use strict';

    // Provincias que el laboratorio no atiende (D-VCF-002). Solo para validar;
    // nunca se muestran al visitante.
    var ZONAS_NO_ATENDIDAS = ['jaen', 'chota', 'celendin', 'bambamarca', 'cajabamba', 'cutervo'];
    var CANTIDAD_MAXIMA = 999;

    var CLAVE_ESTADO = 'vicaf:asistente-wa';
    var VERSION_ESTADO = 1;
    var PASOS_CONOCIDOS = [
        'menu', 'lineas', 'linea', 'ensayo', 'asesor', 'fuera',
        'nombre', 'empresa', 'servicio', 'servicioOtro', 'cantidad', 'ubicacion', 'resumen', 'enviado',
    ];
    var CAMPOS_RESPUESTA = ['nombre', 'empresa', 'servicio', 'cantidad', 'ubicacion'];

    function normalizar(texto) {
        return String(texto || '')
            .normalize('NFD')
            .replace(/[̀-ͯ]/g, '')
            .toLowerCase()
            .trim();
    }

    function validarCantidad(valor) {
        var texto = String(valor == null ? '' : valor).trim();
        if (!/^\d+$/.test(texto)) return false;
        var numero = parseInt(texto, 10);
        return numero >= 1 && numero <= CANTIDAD_MAXIMA;
    }

    function ubicacionExcluida(valor) {
        var texto = normalizar(valor);
        return ZONAS_NO_ATENDIDAS.some(function (zona) {
            return texto.indexOf(zona) !== -1;
        });
    }

    function ubicacionConRegion(valor) {
        var texto = String(valor || '').trim();
        return /cajamarca/i.test(texto) ? texto : texto + ', Cajamarca';
    }

    function armarMensajeCotizacion(saludo, r) {
        return [
            saludo + ', Grupo VICAF. Solicito una cotización:',
            '• Nombre: ' + r.nombre,
            '• Empresa: ' + (r.empresa ? r.empresa : 'Persona natural'),
            '• Servicio: ' + r.servicio,
            '• Cantidad de muestras: ' + r.cantidad,
            '• Ubicación: ' + ubicacionConRegion(r.ubicacion),
        ].join('\n');
    }

    function armarMensajeServicio(saludo, servicio) {
        return saludo + ', Grupo VICAF. Quisiera información sobre ' + servicio + '.';
    }

    function armarMensajeAsesor(saludo) {
        return saludo + ', Grupo VICAF. Quisiera conversar con un asesor.';
    }

    function urlWhatsapp(digitos, mensaje) {
        return 'https://wa.me/' + String(digitos).replace(/\D/g, '') + '?text=' + encodeURIComponent(mensaje);
    }

    // ---------- estado persistente (REQ-WEB-22 a 24, 27, 29) ----------

    function estadoInicial() {
        return { v: VERSION_ESTADO, abierto: false, pila: [{ p: 'menu' }], respuestas: {} };
    }

    function serializarEstado(estado) {
        return JSON.stringify({
            v: VERSION_ESTADO,
            abierto: Boolean(estado.abierto),
            pila: estado.pila,
            respuestas: estado.respuestas,
        });
    }

    function esTexto(valor) {
        return typeof valor === 'string';
    }

    // Lee lo guardado en sessionStorage. Ante JSON roto, otra versión o un
    // paso desconocido devuelve null: mejor empezar de cero que pintar algo raro.
    function leerEstado(texto) {
        var crudo;
        try {
            crudo = JSON.parse(texto);
        } catch (e) {
            return null;
        }
        if (!crudo || crudo.v !== VERSION_ESTADO || !Array.isArray(crudo.pila) || !crudo.pila.length) return null;
        var pilaValida = crudo.pila.every(function (paso) {
            return paso && PASOS_CONOCIDOS.indexOf(paso.p) !== -1
                && ['linea', 'ensayo', 'mensaje'].every(function (clave) {
                    return paso[clave] === undefined || esTexto(paso[clave]);
                });
        });
        if (!pilaValida) return null;
        var respuestas = {};
        var origen = crudo.respuestas || {};
        CAMPOS_RESPUESTA.forEach(function (clave) {
            if (esTexto(origen[clave])) respuestas[clave] = origen[clave];
        });
        respuestas.servicioPreelegido = origen.servicioPreelegido === true;
        return {
            v: VERSION_ESTADO,
            abierto: crudo.abierto === true,
            pila: crudo.pila.map(function (paso) {
                var copia = { p: paso.p };
                ['linea', 'ensayo', 'mensaje'].forEach(function (clave) {
                    if (paso[clave] !== undefined) copia[clave] = paso[clave];
                });
                if (paso.cotizacion === true) copia.cotizacion = true;
                return copia;
            }),
            respuestas: respuestas,
        };
    }

    function buscarLinea(lineas, slug) {
        for (var i = 0; i < lineas.length; i++) {
            if (lineas[i].slug === slug) return lineas[i];
        }
        return null;
    }

    function buscarEnsayo(linea, slug) {
        for (var i = 0; i < linea.ensayos.length; i++) {
            if (linea.ensayos[i].slug === slug) return linea.ensayos[i];
        }
        return null;
    }

    // REQ-WEB-24: corta la pila en el primer paso cuya línea o ensayo ya no
    // está en el catálogo, y deja siempre el menú en la base.
    function podarPila(pila, lineas) {
        var resultado = [];
        for (var i = 0; i < pila.length; i++) {
            var paso = pila[i];
            var linea = paso.linea === undefined ? null : buscarLinea(lineas, paso.linea);
            if (paso.p === 'linea' && !linea) break;
            if (paso.p === 'ensayo' && !(linea && buscarEnsayo(linea, paso.ensayo))) break;
            resultado.push(paso);
        }
        if (!resultado.length || resultado[0].p !== 'menu') resultado.unshift({ p: 'menu' });
        return resultado;
    }

    // REQ-WEB-20/21: solo páginas del catálogo de esta misma web.
    function enlaceWeb(url) {
        return esTexto(url) && /^\/servicios\/[A-Za-z0-9_-]+\/$/.test(url) ? url : null;
    }

    var api = {
        validarCantidad: validarCantidad,
        ubicacionExcluida: ubicacionExcluida,
        armarMensajeCotizacion: armarMensajeCotizacion,
        armarMensajeServicio: armarMensajeServicio,
        armarMensajeAsesor: armarMensajeAsesor,
        urlWhatsapp: urlWhatsapp,
        estadoInicial: estadoInicial,
        serializarEstado: serializarEstado,
        leerEstado: leerEstado,
        podarPila: podarPila,
        enlaceWeb: enlaceWeb,
    };

    if (typeof module !== 'undefined' && module.exports) {
        module.exports = api;
    }
    if (!raiz || !raiz.document) return;
    raiz.VicafAsistente = api;

    raiz.document.addEventListener('DOMContentLoaded', function () {
        var document = raiz.document;
        var contenedor = document.querySelector('[data-asistente-wa]');
        if (!contenedor) return;

        var panel = contenedor.querySelector('#asistente-wa');
        var cuerpo = panel.querySelector('[data-asistente-cuerpo]');
        var abrirBtn = contenedor.querySelector('[data-asistente-abrir]');
        var cerrarBtn = panel.querySelector('[data-asistente-cerrar]');
        var menuBtn = panel.querySelector('[data-asistente-menu]');
        var enlaceDirecto = abrirBtn.getAttribute('href');
        var movil = raiz.matchMedia ? raiz.matchMedia('(max-width: 639px)') : null;

        var datos = null;
        var estado = cargarEstado() || estadoInicial();

        // sessionStorage puede no existir o lanzar (modo privado, cookies
        // bloqueadas): entonces el asistente funciona como en v1 (REQ-WEB-29).
        function cargarEstado() {
            try {
                return leerEstado(raiz.sessionStorage.getItem(CLAVE_ESTADO));
            } catch (e) {
                return null;
            }
        }

        function guardar() {
            try {
                raiz.sessionStorage.setItem(CLAVE_ESTADO, serializarEstado(estado));
            } catch (e) { /* sin persistencia */ }
        }

        // ---------- helpers de DOM (textContent siempre: nada de innerHTML) ----------

        function burbuja(lineas) {
            var div = document.createElement('div');
            div.className = 'rounded-xl rounded-tl-sm bg-white px-3 py-2 leading-relaxed shadow-sm ring-1 ring-slate-900/5';
            [].concat(lineas).forEach(function (linea, i) {
                if (i) div.appendChild(document.createElement('br'));
                div.appendChild(document.createTextNode(linea));
            });
            cuerpo.appendChild(div);
            return div;
        }

        function aviso(texto) {
            var p = document.createElement('p');
            p.className = 'text-xs font-medium text-red-700';
            p.setAttribute('role', 'alert');
            p.textContent = texto;
            cuerpo.appendChild(p);
        }

        function grupoBotones() {
            var div = document.createElement('div');
            div.className = 'flex flex-col gap-2';
            cuerpo.appendChild(div);
            return div;
        }

        var CLASE_OPCION = 'w-full rounded-lg border border-emerald-600 bg-white px-3 py-2 text-left font-medium text-emerald-700 transition hover:bg-emerald-50 focus:outline-none focus-visible:ring-2 focus-visible:ring-emerald-500';
        var CLASE_PRINCIPAL = 'w-full rounded-lg bg-emerald-600 px-3 py-2 text-center font-semibold text-white transition hover:bg-emerald-700 focus:outline-none focus-visible:ring-2 focus-visible:ring-emerald-500 focus-visible:ring-offset-2';
        var CLASE_SECUNDARIA = 'w-full rounded-lg px-3 py-2 text-center text-slate-600 underline-offset-2 transition hover:text-slate-900 hover:underline focus:outline-none focus-visible:ring-2 focus-visible:ring-slate-400';
        var CLASE_WEB = 'w-full rounded-lg border border-blue-700 bg-white px-3 py-2 text-center font-medium text-blue-700 transition hover:bg-blue-50 focus:outline-none focus-visible:ring-2 focus-visible:ring-blue-500';

        function boton(grupo, texto, alClic, clase, subtitulo) {
            var b = document.createElement('button');
            b.type = 'button';
            b.className = clase || CLASE_OPCION;
            var titulo = document.createElement('span');
            titulo.className = 'block';
            titulo.textContent = texto;
            b.appendChild(titulo);
            if (subtitulo) {
                var sub = document.createElement('span');
                sub.className = 'mt-0.5 block text-xs font-normal text-slate-500';
                sub.textContent = subtitulo;
                b.appendChild(sub);
            }
            b.addEventListener('click', alClic);
            grupo.appendChild(b);
            return b;
        }

        function enlace(grupo, texto, href, clase, alClic) {
            var a = document.createElement('a');
            a.href = href;
            a.className = 'block ' + (clase || CLASE_OPCION);
            a.textContent = texto;
            if (/^https:\/\/wa\.me\//.test(href)) {
                a.target = '_blank';
                a.rel = 'noopener noreferrer';
            }
            if (alClic) a.addEventListener('click', alClic);
            grupo.appendChild(a);
            return a;
        }

        // "Ver en la web" (REQ-WEB-20/21): misma pestaña, así el panel se
        // restaura en la página de destino. Sin página publicada, no hay enlace.
        function enlaceVerEnLaWeb(grupo, url, nombre) {
            var href = enlaceWeb(url);
            if (!href) return;
            var a = enlace(grupo, 'Ver en la web', href, CLASE_WEB);
            a.setAttribute('aria-label', 'Ver en la web: ' + nombre);
            a.setAttribute('data-asistente-web', '');
            if (raiz.location && raiz.location.pathname === href) a.setAttribute('aria-current', 'page');
        }

        function campo(etiqueta, valor, opciones) {
            var form = document.createElement('form');
            form.className = 'flex flex-col gap-2';
            form.noValidate = true;
            var label = document.createElement('label');
            label.className = 'sr-only';
            label.textContent = etiqueta;
            var input = document.createElement('input');
            input.className = 'w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-slate-900 focus:border-emerald-600 focus:outline-none focus:ring-2 focus:ring-emerald-500/40';
            input.placeholder = etiqueta;
            input.value = valor || '';
            input.id = 'asistente-wa-campo';
            label.htmlFor = input.id;
            if (opciones && opciones.numerico) {
                input.inputMode = 'numeric';
                input.pattern = '[0-9]*';
            }
            input.autocomplete = (opciones && opciones.autocomplete) || 'off';
            var enviar = document.createElement('button');
            enviar.type = 'submit';
            enviar.className = CLASE_PRINCIPAL;
            enviar.textContent = 'Continuar';
            form.appendChild(label);
            form.appendChild(input);
            form.appendChild(enviar);
            cuerpo.appendChild(form);
            return { form: form, input: input };
        }

        function limpiar() {
            cuerpo.textContent = '';
        }

        function enfocarPrimero() {
            var primero = cuerpo.querySelector('input, button, a');
            if (primero) primero.focus();
        }

        // ---------- navegación ----------

        function pasoActual() {
            return estado.pila[estado.pila.length - 1];
        }

        // enfocar = false al restaurar tras cambiar de página: el foco y el
        // scroll son de la página nueva, no del panel (REQ-WEB-22).
        function mostrar(enfocar) {
            limpiar();
            var paso = pasoActual();
            PASOS[paso.p](paso);
            menuBtn.classList.toggle('hidden', paso.p === 'menu');
            cuerpo.scrollTop = 0;
            guardar();
            ajustarEspacioMovil();
            if (enfocar !== false) enfocarPrimero();
        }

        function ir(p, parametros) {
            var paso = { p: p };
            Object.keys(parametros || {}).forEach(function (clave) {
                paso[clave] = parametros[clave];
            });
            estado.pila.push(paso);
            mostrar();
        }

        function volver() {
            estado.pila.pop();
            if (!estado.pila.length) estado.pila.push({ p: 'menu' });
            mostrar();
        }

        function irAlMenu() {
            estado.pila = [{ p: 'menu' }];
            mostrar();
        }

        function botonVolver(grupo) {
            boton(grupo || grupoBotones(), 'Volver', volver, CLASE_SECUNDARIA);
        }

        // Abre WhatsApp con un <a> real (el clic es del visitante, así no lo
        // bloquea el navegador). Fuera de horario muestra antes el aviso T-40.
        function botonWhatsapp(grupo, texto, mensaje, esCotizacion) {
            if (datos.abierto) {
                enlace(grupo, texto, urlWhatsapp(datos.whatsapp, mensaje), CLASE_PRINCIPAL,
                    esCotizacion ? alEnviarCotizacion : null);
                return;
            }
            boton(grupo, texto, function () {
                ir('fuera', esCotizacion ? { mensaje: mensaje, cotizacion: true } : { mensaje: mensaje });
            }, CLASE_PRINCIPAL);
        }

        // ---------- pasos ----------

        var PASOS = {};

        PASOS.menu = function () {
            estado.pila = [{ p: 'menu' }];
            burbuja([
                datos.saludo + ', bienvenido a Grupo VICAF 👋',
                'Somos un laboratorio de suelos acreditado por INACAL en Cajamarca.',
                '¿En qué podemos ayudarle?',
            ]);
            var g = grupoBotones();
            boton(g, '1) Ver nuestros servicios', function () { ir('lineas'); });
            boton(g, '2) Solicitar una cotización', function () { iniciarCotizacion(null); });
            boton(g, '3) Conversar con un asesor', function () { ir('asesor'); });
        };

        PASOS.lineas = function () {
            burbuja([
                'Con gusto le mostramos nuestros servicios.',
                'Elija una línea para ver los ensayos que realizamos.',
            ]);
            var g = grupoBotones();
            datos.lineas.forEach(function (linea) {
                boton(g, linea.nombre, function () { ir('linea', { linea: linea.slug }); }, null, linea.resumen);
            });
            botonVolver(g);
        };

        PASOS.linea = function (paso) {
            var linea = buscarLinea(datos.lineas, paso.linea);
            var g;
            if (!linea.ensayos.length) {
                burbuja([
                    'Pronto publicaremos el detalle de esta línea.',
                    'Mientras tanto, puede consultarnos directamente.',
                ]);
                g = grupoBotones();
                enlaceVerEnLaWeb(g, linea.url, linea.nombre);
                botonWhatsapp(g, 'Consultar por WhatsApp', armarMensajeServicio(datos.saludo, linea.nombre));
                boton(g, 'Solicitar una cotización', function () { iniciarCotizacion(linea.nombre); });
                botonVolver(g);
                return;
            }
            burbuja([
                'Estos son los ensayos de ' + linea.nombre + '.',
                'Toque uno para ver su detalle.',
            ]);
            g = grupoBotones();
            linea.ensayos.forEach(function (ensayo) {
                boton(g, ensayo.titulo, function () {
                    ir('ensayo', { linea: linea.slug, ensayo: ensayo.slug });
                });
            });
            enlaceVerEnLaWeb(g, linea.url, linea.nombre);
            botonVolver(g);
        };

        PASOS.ensayo = function (paso) {
            var ensayo = buscarEnsayo(buscarLinea(datos.lineas, paso.linea), paso.ensayo);
            burbuja(ensayo.resumen ? ensayo.titulo + ': ' + ensayo.resumen : ensayo.titulo);
            var g = grupoBotones();
            enlaceVerEnLaWeb(g, ensayo.url, ensayo.titulo);
            botonWhatsapp(g, 'Consultar por WhatsApp', armarMensajeServicio(datos.saludo, ensayo.titulo));
            burbuja([
                '¿Desea que le preparemos una cotización para este servicio?',
                'Solo le tomará un minuto.',
            ]);
            var g2 = grupoBotones();
            boton(g2, 'Sí, cotizar', function () { iniciarCotizacion(ensayo.titulo); }, CLASE_PRINCIPAL);
            boton(g2, 'Volver a servicios', function () {
                estado.pila = [{ p: 'menu' }];
                ir('lineas');
            }, CLASE_SECUNDARIA);
        };

        PASOS.asesor = function () {
            burbuja([
                'Le comunicamos con uno de nuestros asesores por WhatsApp al ' + formatearNumero(datos.whatsapp) + '.',
                'El chat se abrirá en una nueva ventana.',
            ]);
            var g = grupoBotones();
            botonWhatsapp(g, 'Abrir WhatsApp', armarMensajeAsesor(datos.saludo));
            botonVolver(g);
        };

        PASOS.fuera = function (paso) {
            burbuja([
                'Nuestro horario de atención es ' + datos.horario + '.',
                'Puede dejarnos su mensaje y le responderemos el siguiente día hábil.',
            ]);
            var g = grupoBotones();
            enlace(g, 'Continuar a WhatsApp', urlWhatsapp(datos.whatsapp, paso.mensaje), CLASE_PRINCIPAL,
                paso.cotizacion ? alEnviarCotizacion : null);
            botonVolver(g);
        };

        function formatearNumero(digitos) {
            // 51964326364 -> +51 964 326 364
            var m = /^(51)(\d{3})(\d{3})(\d{3})$/.exec(digitos);
            return m ? '+' + m[1] + ' ' + m[2] + ' ' + m[3] + ' ' + m[4] : '+' + digitos;
        }

        // ---------- cotización (una pregunta por vez) ----------

        function iniciarCotizacion(servicioElegido) {
            var previas = estado.respuestas;
            estado.respuestas = {
                nombre: previas.nombre || '',
                empresa: previas.empresa || '',
                servicio: servicioElegido || '',
                servicioPreelegido: Boolean(servicioElegido),
                cantidad: '',
                ubicacion: '',
            };
            ir('nombre');
        }

        function pregunta(lineas, etiqueta, clave, validar, siguiente, opciones) {
            burbuja(lineas);
            var c = campo(etiqueta, estado.respuestas[clave], opciones);
            c.form.addEventListener('submit', function (evento) {
                evento.preventDefault();
                var valor = c.input.value.trim();
                var error = validar(valor);
                var previo = cuerpo.querySelector('[role="alert"]');
                if (previo) previo.remove();
                if (error) {
                    aviso(error);
                    c.input.setAttribute('aria-invalid', 'true');
                    c.input.focus();
                    return;
                }
                estado.respuestas[clave] = valor;
                ir(siguiente);
            });
            var g = grupoBotones();
            if (opciones && opciones.omitir) {
                boton(g, 'Omitir', function () {
                    estado.respuestas[clave] = '';
                    ir(siguiente);
                }, CLASE_OPCION);
            }
            botonVolver(g);
        }

        function requerido(valor) {
            return valor ? null : 'Por favor, complete este dato.';
        }

        PASOS.nombre = function () {
            burbuja([
                'Con gusto le preparamos una cotización.',
                'Le haremos cinco preguntas breves.',
            ]);
            pregunta(['¿Cuál es su nombre?'], 'Nombre y apellido', 'nombre', requerido, 'empresa', { autocomplete: 'name' });
        };

        PASOS.empresa = function () {
            pregunta(
                ['Gracias, ' + estado.respuestas.nombre + '. ¿A qué empresa representa?', 'Si es persona natural, toque «Omitir».'],
                'Empresa', 'empresa', function () { return null; },
                estado.respuestas.servicioPreelegido ? 'cantidad' : 'servicio',
                { omitir: true, autocomplete: 'organization' }
            );
        };

        PASOS.servicio = function () {
            burbuja('¿Qué servicio necesita?');
            var g = grupoBotones();
            datos.lineas.forEach(function (linea) {
                var opciones = linea.ensayos.length ? linea.ensayos.map(function (e) { return e.titulo; }) : [linea.nombre];
                opciones.forEach(function (nombre) {
                    boton(g, nombre, function () {
                        estado.respuestas.servicio = nombre;
                        ir('cantidad');
                    });
                });
            });
            boton(g, 'Otro / no estoy seguro', function () { ir('servicioOtro'); });
            botonVolver(g);
        };

        PASOS.servicioOtro = function () {
            pregunta(['Cuéntenos brevemente qué necesita ensayar.'], 'Describa lo que necesita', 'servicio', requerido, 'cantidad');
        };

        PASOS.cantidad = function () {
            pregunta(['¿Cuántas muestras desea ensayar?'], 'Ej.: 3', 'cantidad', function (valor) {
                return validarCantidad(valor) ? null : 'Por favor, ingrese un número entero mayor que cero.';
            }, 'ubicacion', { numerico: true });
        };

        PASOS.ubicacion = function () {
            pregunta(['¿En qué lugar de Cajamarca se encuentra su obra o proyecto?'], 'Distrito o referencia', 'ubicacion', function (valor) {
                if (!valor) return 'Por favor, complete este dato.';
                if (ubicacionExcluida(valor)) {
                    return 'Por ahora atendemos solo proyectos en Cajamarca. Si su proyecto está en Cajamarca, indíquenos el distrito o una referencia.';
                }
                return null;
            }, 'resumen', { autocomplete: 'address-level2' });
        };

        PASOS.resumen = function () {
            var r = estado.respuestas;
            burbuja('Revise sus datos, por favor:');
            var lista = document.createElement('dl');
            lista.className = 'grid grid-cols-[auto,1fr] gap-x-3 gap-y-1 rounded-xl bg-white px-3 py-2 shadow-sm ring-1 ring-slate-900/5';
            [
                ['Nombre', r.nombre],
                ['Empresa', r.empresa || 'Persona natural'],
                ['Servicio', r.servicio],
                ['Muestras', r.cantidad],
                ['Ubicación', ubicacionConRegion(r.ubicacion)],
            ].forEach(function (fila) {
                var dt = document.createElement('dt');
                dt.className = 'font-medium text-slate-500';
                dt.textContent = fila[0];
                var dd = document.createElement('dd');
                dd.className = 'text-slate-900';
                dd.textContent = fila[1];
                lista.appendChild(dt);
                lista.appendChild(dd);
            });
            cuerpo.appendChild(lista);
            burbuja('¿Está todo correcto?');
            var g = grupoBotones();
            botonWhatsapp(g, 'Enviar por WhatsApp', armarMensajeCotizacion(datos.saludo, r), true);
            boton(g, 'Corregir', function () {
                estado.respuestas.servicioPreelegido = false;
                estado.pila = [{ p: 'menu' }];
                ir('nombre');
            }, CLASE_SECUNDARIA);
        };

        PASOS.enviado = function () {
            burbuja([
                'Listo, abrimos WhatsApp con su solicitud; solo tiene que enviarla.',
                'Un asesor le responderá a la brevedad.',
            ]);
            boton(grupoBotones(), 'Volver al inicio', irAlMenu, CLASE_SECUNDARIA);
        };

        function alEnviarCotizacion() {
            // Opción C (pendiente): aquí se enviaría `estado.respuestas` al servidor.
            raiz.setTimeout(function () { ir('enviado'); }, 0);
        }

        // ---------- móvil (REQ-WEB-28) ----------

        // Con el panel abierto en pantallas chicas se reserva su alto al final
        // de la página, así todo el contenido se puede leer por encima de él.
        function ajustarEspacioMovil() {
            var abierto = !panel.classList.contains('hidden');
            document.body.style.paddingBottom = abierto && movil && movil.matches
                ? (panel.offsetHeight + 16) + 'px'
                : '';
        }

        if (movil) {
            if (movil.addEventListener) movil.addEventListener('change', ajustarEspacioMovil);
            else if (movil.addListener) movil.addListener(ajustarEspacioMovil);
        }
        if (raiz.ResizeObserver) new raiz.ResizeObserver(ajustarEspacioMovil).observe(panel);

        // ---------- abrir / cerrar ----------

        function errorDeCarga() {
            limpiar();
            menuBtn.classList.add('hidden');
            burbuja('No pudimos cargar el asistente en este momento.');
            enlace(grupoBotones(), 'Escribir por WhatsApp', enlaceDirecto, CLASE_PRINCIPAL);
            ajustarEspacioMovil();
            if (estado.abierto) enfocarPrimero();
        }

        function abrir(enfocar) {
            panel.classList.remove('hidden');
            contenedor.setAttribute('data-abierto', 'true');
            abrirBtn.setAttribute('aria-expanded', 'true');
            estado.abierto = true;
            guardar();
            if (datos) {
                mostrar(enfocar);
                return;
            }
            limpiar();
            menuBtn.classList.add('hidden');
            burbuja('Cargando…');
            ajustarEspacioMovil();
            raiz.fetch(panel.getAttribute('data-endpoint'), { headers: { Accept: 'application/json' } })
                .then(function (r) {
                    if (!r.ok) throw new Error(String(r.status));
                    return r.json();
                })
                .then(function (json) {
                    datos = json;
                    estado.pila = podarPila(estado.pila, datos.lineas);
                    mostrar(enfocar && estado.abierto);
                })
                .catch(errorDeCarga);
        }

        function cerrar() {
            panel.classList.add('hidden');
            contenedor.setAttribute('data-abierto', 'false');
            abrirBtn.setAttribute('aria-expanded', 'false');
            estado.abierto = false;
            guardar();
            ajustarEspacioMovil();
            abrirBtn.focus();
            // El saludo y el horario se recalculan en la próxima apertura; el
            // paso se conserva para retomar donde quedó (CA-07.5).
            datos = null;
        }

        abrirBtn.addEventListener('click', function (evento) {
            evento.preventDefault();
            if (panel.classList.contains('hidden')) abrir(true);
            else cerrar();
        });
        cerrarBtn.addEventListener('click', cerrar);
        menuBtn.addEventListener('click', irAlMenu);
        document.addEventListener('keydown', function (evento) {
            if (evento.key === 'Escape' && !panel.classList.contains('hidden')) cerrar();
        });

        // Solo se reabre si el visitante lo dejó abierto (RN-13, REQ-WEB-27).
        if (estado.abierto) abrir(false);
    });
})(typeof window !== 'undefined' ? window : null);
