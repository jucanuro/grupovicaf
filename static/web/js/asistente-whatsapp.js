// Asistente de WhatsApp de la web (VCF-WEB, D-VCF-004; specs/WEB/).
//
// Widget guiado que termina en wa.me con el mensaje armado (opción A). Los
// textos son los aprobados en G1 (docs/proc/VCF-WEB_HU_CU_v1.md, sección 7).
// Saludo, horario, número y catálogo llegan de web_contacto:asistente_datos,
// que los lee de NegocioConfig, LineaServicio y ServicioPublicado.
//
// Preparado para la opción C: todas las respuestas de la cotización viven en
// un solo objeto (`respuestas`); guardar el lead sería un fetch más en
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

    var api = {
        validarCantidad: validarCantidad,
        ubicacionExcluida: ubicacionExcluida,
        armarMensajeCotizacion: armarMensajeCotizacion,
        armarMensajeServicio: armarMensajeServicio,
        armarMensajeAsesor: armarMensajeAsesor,
        urlWhatsapp: urlWhatsapp,
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
        var enlaceDirecto = abrirBtn.getAttribute('href');

        var datos = null;
        var respuestas = {};
        var pila = [];

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
            cuerpo.scrollTop = 0;
        }

        // ---------- navegación ----------

        function mostrar(paso) {
            limpiar();
            paso();
            enfocarPrimero();
        }

        function ir(paso) {
            pila.push(paso);
            mostrar(paso);
        }

        function volver() {
            pila.pop();
            if (!pila.length) pila.push(pasoMenu);
            mostrar(pila[pila.length - 1]);
        }

        function botonVolver(grupo) {
            boton(grupo || grupoBotones(), 'Volver', volver, CLASE_SECUNDARIA);
        }

        // Abre WhatsApp con un <a> real (el clic es del visitante, así no lo
        // bloquea el navegador). Fuera de horario muestra antes el aviso T-40.
        function botonWhatsapp(grupo, texto, mensaje, despues) {
            var href = urlWhatsapp(datos.whatsapp, mensaje);
            if (datos.abierto) {
                enlace(grupo, texto, href, CLASE_PRINCIPAL, despues);
                return;
            }
            boton(grupo, texto, function () {
                ir(function pasoFueraDeHorario() {
                    burbuja([
                        'Nuestro horario de atención es ' + datos.horario + '.',
                        'Puede dejarnos su mensaje y le responderemos el siguiente día hábil.',
                    ]);
                    var g = grupoBotones();
                    enlace(g, 'Continuar a WhatsApp', href, CLASE_PRINCIPAL, despues);
                    botonVolver(g);
                });
            }, CLASE_PRINCIPAL);
        }

        // ---------- pasos ----------

        function pasoMenu() {
            pila = [pasoMenu];
            burbuja([
                datos.saludo + ', bienvenido a Grupo VICAF 👋',
                'Somos un laboratorio de suelos acreditado por INACAL en Cajamarca.',
                '¿En qué podemos ayudarle?',
            ]);
            var g = grupoBotones();
            boton(g, '1) Ver nuestros servicios', function () { ir(pasoLineas); });
            boton(g, '2) Solicitar una cotización', function () { iniciarCotizacion(null); });
            boton(g, '3) Conversar con un asesor', function () { ir(pasoAsesor); });
        }

        function pasoLineas() {
            burbuja([
                'Con gusto le mostramos nuestros servicios.',
                'Elija una línea para ver los ensayos que realizamos.',
            ]);
            var g = grupoBotones();
            datos.lineas.forEach(function (linea) {
                boton(g, linea.nombre, function () {
                    ir(function pasoEnsayos() { mostrarLinea(linea); });
                }, null, linea.resumen);
            });
            botonVolver(g);
        }

        function mostrarLinea(linea) {
            var g;
            if (!linea.ensayos.length) {
                burbuja([
                    'Pronto publicaremos el detalle de esta línea.',
                    'Mientras tanto, puede consultarnos directamente.',
                ]);
                g = grupoBotones();
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
                    ir(function pasoEnsayo() { mostrarEnsayo(ensayo); });
                });
            });
            botonVolver(g);
        }

        function mostrarEnsayo(ensayo) {
            burbuja(ensayo.resumen ? ensayo.titulo + ': ' + ensayo.resumen : ensayo.titulo);
            var g = grupoBotones();
            enlace(g, 'Ver página del servicio', ensayo.url);
            botonWhatsapp(g, 'Consultar por WhatsApp', armarMensajeServicio(datos.saludo, ensayo.titulo));
            burbuja([
                '¿Desea que le preparemos una cotización para este servicio?',
                'Solo le tomará un minuto.',
            ]);
            var g2 = grupoBotones();
            boton(g2, 'Sí, cotizar', function () { iniciarCotizacion(ensayo.titulo); }, CLASE_PRINCIPAL);
            boton(g2, 'Volver a servicios', function () {
                pila = [pasoMenu];
                ir(pasoLineas);
            }, CLASE_SECUNDARIA);
        }

        function pasoAsesor() {
            burbuja([
                'Le comunicamos con uno de nuestros asesores por WhatsApp al ' + formatearNumero(datos.whatsapp) + '.',
                'El chat se abrirá en una nueva ventana.',
            ]);
            var g = grupoBotones();
            botonWhatsapp(g, 'Abrir WhatsApp', armarMensajeAsesor(datos.saludo));
            botonVolver(g);
        }

        function formatearNumero(digitos) {
            // 51964326364 -> +51 964 326 364
            var m = /^(51)(\d{3})(\d{3})(\d{3})$/.exec(digitos);
            return m ? '+' + m[1] + ' ' + m[2] + ' ' + m[3] + ' ' + m[4] : '+' + digitos;
        }

        // ---------- cotización (una pregunta por vez) ----------

        function iniciarCotizacion(servicioElegido) {
            respuestas = {
                nombre: respuestas.nombre || '',
                empresa: respuestas.empresa || '',
                servicio: servicioElegido || '',
                servicioPreelegido: Boolean(servicioElegido),
                cantidad: '',
                ubicacion: '',
            };
            ir(pasoNombre);
        }

        function pregunta(lineas, etiqueta, clave, validar, siguiente, opciones) {
            burbuja(lineas);
            var c = campo(etiqueta, respuestas[clave], opciones);
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
                respuestas[clave] = valor;
                ir(siguiente);
            });
            var g = grupoBotones();
            if (opciones && opciones.omitir) {
                boton(g, 'Omitir', function () {
                    respuestas[clave] = '';
                    ir(siguiente);
                }, CLASE_OPCION);
            }
            botonVolver(g);
        }

        function requerido(valor) {
            return valor ? null : 'Por favor, complete este dato.';
        }

        function pasoNombre() {
            burbuja([
                'Con gusto le preparamos una cotización.',
                'Le haremos cinco preguntas breves.',
            ]);
            pregunta(['¿Cuál es su nombre?'], 'Nombre y apellido', 'nombre', requerido, pasoEmpresa, { autocomplete: 'name' });
        }

        function pasoEmpresa() {
            pregunta(
                ['Gracias, ' + respuestas.nombre + '. ¿A qué empresa representa?', 'Si es persona natural, toque «Omitir».'],
                'Empresa', 'empresa', function () { return null; },
                respuestas.servicioPreelegido ? pasoCantidad : pasoServicio,
                { omitir: true, autocomplete: 'organization' }
            );
        }

        function pasoServicio() {
            burbuja('¿Qué servicio necesita?');
            var g = grupoBotones();
            datos.lineas.forEach(function (linea) {
                var opciones = linea.ensayos.length ? linea.ensayos.map(function (e) { return e.titulo; }) : [linea.nombre];
                opciones.forEach(function (nombre) {
                    boton(g, nombre, function () {
                        respuestas.servicio = nombre;
                        ir(pasoCantidad);
                    });
                });
            });
            boton(g, 'Otro / no estoy seguro', function () { ir(pasoServicioOtro); });
            botonVolver(g);
        }

        function pasoServicioOtro() {
            pregunta(['Cuéntenos brevemente qué necesita ensayar.'], 'Describa lo que necesita', 'servicio', requerido, pasoCantidad);
        }

        function pasoCantidad() {
            pregunta(['¿Cuántas muestras desea ensayar?'], 'Ej.: 3', 'cantidad', function (valor) {
                return validarCantidad(valor) ? null : 'Por favor, ingrese un número entero mayor que cero.';
            }, pasoUbicacion, { numerico: true });
        }

        function pasoUbicacion() {
            pregunta(['¿En qué lugar de Cajamarca se encuentra su obra o proyecto?'], 'Distrito o referencia', 'ubicacion', function (valor) {
                if (!valor) return 'Por favor, complete este dato.';
                if (ubicacionExcluida(valor)) {
                    return 'Por ahora atendemos solo proyectos en Cajamarca. Si su proyecto está en Cajamarca, indíquenos el distrito o una referencia.';
                }
                return null;
            }, pasoResumen, { autocomplete: 'address-level2' });
        }

        function pasoResumen() {
            burbuja('Revise sus datos, por favor:');
            var lista = document.createElement('dl');
            lista.className = 'grid grid-cols-[auto,1fr] gap-x-3 gap-y-1 rounded-xl bg-white px-3 py-2 shadow-sm ring-1 ring-slate-900/5';
            [
                ['Nombre', respuestas.nombre],
                ['Empresa', respuestas.empresa || 'Persona natural'],
                ['Servicio', respuestas.servicio],
                ['Muestras', respuestas.cantidad],
                ['Ubicación', ubicacionConRegion(respuestas.ubicacion)],
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
            botonWhatsapp(g, 'Enviar por WhatsApp', armarMensajeCotizacion(datos.saludo, respuestas), alEnviarCotizacion);
            boton(g, 'Corregir', function () {
                respuestas.servicioPreelegido = false;
                pila = [pasoMenu];
                ir(pasoNombre);
            }, CLASE_SECUNDARIA);
        }

        function alEnviarCotizacion() {
            // Opción C (pendiente): aquí se enviaría `respuestas` al servidor.
            raiz.setTimeout(function () {
                ir(function pasoEnviado() {
                    burbuja([
                        'Listo, abrimos WhatsApp con su solicitud; solo tiene que enviarla.',
                        'Un asesor le responderá a la brevedad.',
                    ]);
                    var g = grupoBotones();
                    boton(g, 'Volver al inicio', function () { ir(pasoMenu); }, CLASE_SECUNDARIA);
                });
            }, 0);
        }

        // ---------- abrir / cerrar ----------

        function errorDeCarga() {
            limpiar();
            burbuja('No pudimos cargar el asistente en este momento.');
            enlace(grupoBotones(), 'Escribir por WhatsApp', enlaceDirecto, CLASE_PRINCIPAL);
            enfocarPrimero();
        }

        function abrir() {
            panel.classList.remove('hidden');
            abrirBtn.setAttribute('aria-expanded', 'true');
            if (datos) {
                ir(pasoMenu);
                return;
            }
            limpiar();
            burbuja('Cargando…');
            raiz.fetch(panel.getAttribute('data-endpoint'), { headers: { Accept: 'application/json' } })
                .then(function (r) {
                    if (!r.ok) throw new Error(String(r.status));
                    return r.json();
                })
                .then(function (json) {
                    datos = json;
                    ir(pasoMenu);
                })
                .catch(errorDeCarga);
        }

        function cerrar() {
            panel.classList.add('hidden');
            abrirBtn.setAttribute('aria-expanded', 'false');
            abrirBtn.focus();
            // El saludo y el horario se recalculan en la próxima apertura.
            datos = null;
        }

        abrirBtn.addEventListener('click', function (evento) {
            evento.preventDefault();
            if (panel.classList.contains('hidden')) abrir();
            else cerrar();
        });
        cerrarBtn.addEventListener('click', cerrar);
        document.addEventListener('keydown', function (evento) {
            if (evento.key === 'Escape' && !panel.classList.contains('hidden')) cerrar();
        });
    });
})(typeof window !== 'undefined' ? window : null);
