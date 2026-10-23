// Pruebas de las funciones puras del asistente de WhatsApp (specs/WEB, T5).
// Ejecutar con: node --test 'tests/js/*.test.js'
const test = require('node:test');
const assert = require('node:assert/strict');

const asistente = require('../../static/web/js/asistente-whatsapp.js');

test('validarCantidad acepta enteros de 1 a 999 (REQ-WEB-12)', () => {
    for (const valido of ['1', '3', ' 12 ', '999', 7]) {
        assert.equal(asistente.validarCantidad(valido), true, String(valido));
    }
    for (const invalido of ['', '0', '1000', '-2', '2.5', 'tres', '3a', null]) {
        assert.equal(asistente.validarCantidad(invalido), false, String(invalido));
    }
});

test('ubicacionExcluida detecta las provincias de D-VCF-002 sin importar tildes (REQ-WEB-13)', () => {
    assert.equal(asistente.ubicacionExcluida('Jaén'), true);
    assert.equal(asistente.ubicacionExcluida('obra en CELENDIN'), true);
    assert.equal(asistente.ubicacionExcluida('Hualgayoc - Bambamarca'), true);
    assert.equal(asistente.ubicacionExcluida('Baños del Inca'), false);
    assert.equal(asistente.ubicacionExcluida('Cajamarca'), false);
});

test('el mensaje de cotización usa la plantilla aprobada (REQ-WEB-16)', () => {
    const mensaje = asistente.armarMensajeCotizacion('Buenas tardes', {
        nombre: 'Ana Pérez', empresa: '', servicio: 'Ensayo CBR', cantidad: '3', ubicacion: 'Baños del Inca',
    });
    assert.equal(mensaje, [
        'Buenas tardes, Grupo VICAF. Solicito una cotización:',
        '• Nombre: Ana Pérez',
        '• Empresa: Persona natural',
        '• Servicio: Ensayo CBR',
        '• Cantidad de muestras: 3',
        '• Ubicación: Baños del Inca, Cajamarca',
    ].join('\n'));
});

test('no duplica "Cajamarca" si el visitante ya la escribió', () => {
    const mensaje = asistente.armarMensajeCotizacion('Buenos días', {
        nombre: 'A', empresa: 'Constructora X', servicio: 'S', cantidad: '1', ubicacion: 'Cajamarca centro',
    });
    assert.match(mensaje, /• Ubicación: Cajamarca centro$/);
    assert.match(mensaje, /• Empresa: Constructora X/);
});

test('mensajes de servicio y asesor empiezan con el saludo (CA-01.7)', () => {
    assert.equal(asistente.armarMensajeServicio('Buenas noches', 'Ensayo CBR'),
        'Buenas noches, Grupo VICAF. Quisiera información sobre Ensayo CBR.');
    assert.equal(asistente.armarMensajeAsesor('Buenos días'),
        'Buenos días, Grupo VICAF. Quisiera conversar con un asesor.');
});

test('urlWhatsapp usa solo dígitos y codifica tildes, ñ y saltos de línea (REQ-WEB-16)', () => {
    const url = asistente.urlWhatsapp('+51 964-326-364', 'Señal: año\ncompresión');
    assert.equal(url, 'https://wa.me/51964326364?text=Se%C3%B1al%3A%20a%C3%B1o%0Acompresi%C3%B3n');
    assert.equal(decodeURIComponent(url.split('?text=')[1]), 'Señal: año\ncompresión');
});

// ---------- v2: estado entre páginas (HU v1.5, REQ-WEB-20 a 29) ----------

const CATALOGO = [
    {
        nombre: 'Mecánica de Suelos', slug: 'mecanica-de-suelos', url: '/servicios/mecanica-de-suelos/',
        ensayos: [{ titulo: 'Ensayo CBR', slug: 'ensayo-cbr', url: '/servicios/ensayo-cbr/' }],
    },
    { nombre: 'Estudio de Canteras', slug: 'estudio-de-canteras', url: '/servicios/estudio-de-canteras/', ensayos: [] },
];

test('el estado inicial empieza en el menú y con el panel cerrado (REQ-WEB-27)', () => {
    assert.deepEqual(asistente.estadoInicial(), { v: 1, abierto: false, pila: [{ p: 'menu' }], respuestas: {} });
});

test('serializar y leer conservan paso, panel abierto y respuestas (REQ-WEB-22, 23, 26)', () => {
    const estado = {
        v: 1,
        abierto: true,
        pila: [{ p: 'menu' }, { p: 'lineas' }, { p: 'linea', linea: 'mecanica-de-suelos' },
            { p: 'ensayo', linea: 'mecanica-de-suelos', ensayo: 'ensayo-cbr' }],
        respuestas: { nombre: 'Ana', empresa: '', servicio: 'Ensayo CBR', servicioPreelegido: true, cantidad: '', ubicacion: '' },
    };
    assert.deepEqual(asistente.leerEstado(asistente.serializarEstado(estado)), estado);
});

test('el cierre queda guardado: un estado cerrado no se reabre (REQ-WEB-27)', () => {
    const texto = asistente.serializarEstado({ abierto: false, pila: [{ p: 'menu' }, { p: 'lineas' }], respuestas: {} });
    const leido = asistente.leerEstado(texto);
    assert.equal(leido.abierto, false);
    assert.deepEqual(leido.pila, [{ p: 'menu' }, { p: 'lineas' }]);
});

test('leerEstado descarta datos rotos, de otra versión o con pasos desconocidos (REQ-WEB-29)', () => {
    for (const malo of [null, '', '{', '[]', '{"v":2,"pila":[{"p":"menu"}]}', '{"v":1,"pila":[]}',
        '{"v":1,"pila":[{"p":"inventado"}]}', '{"v":1,"pila":[{"p":"linea","linea":{"x":1}}]}']) {
        assert.equal(asistente.leerEstado(malo), null, String(malo));
    }
});

test('leerEstado solo se queda con las respuestas conocidas y de texto', () => {
    const leido = asistente.leerEstado(JSON.stringify({
        v: 1, abierto: 'sí', pila: [{ p: 'menu', extra: '<script>' }],
        respuestas: { nombre: 'Ana', cantidad: 3, precio: '100', servicioPreelegido: 'true' },
    }));
    assert.equal(leido.abierto, false);
    assert.deepEqual(leido.pila, [{ p: 'menu' }]);
    assert.deepEqual(leido.respuestas, { nombre: 'Ana', servicioPreelegido: false });
});

test('podarPila mantiene los pasos que siguen publicados', () => {
    const pila = [{ p: 'menu' }, { p: 'lineas' }, { p: 'linea', linea: 'mecanica-de-suelos' },
        { p: 'ensayo', linea: 'mecanica-de-suelos', ensayo: 'ensayo-cbr' }];
    assert.deepEqual(asistente.podarPila(pila, CATALOGO), pila);
});

test('podarPila cae al paso válido más cercano si algo se despublicó (REQ-WEB-24)', () => {
    const base = [{ p: 'menu' }, { p: 'lineas' }];
    assert.deepEqual(
        asistente.podarPila(base.concat([{ p: 'linea', linea: 'ya-no-existe' }, { p: 'asesor' }]), CATALOGO), base,
    );
    assert.deepEqual(
        asistente.podarPila(base.concat([{ p: 'linea', linea: 'mecanica-de-suelos' },
            { p: 'ensayo', linea: 'mecanica-de-suelos', ensayo: 'ensayo-retirado' }]), CATALOGO),
        base.concat([{ p: 'linea', linea: 'mecanica-de-suelos' }]),
    );
    assert.deepEqual(asistente.podarPila([{ p: 'linea', linea: 'x' }], CATALOGO), [{ p: 'menu' }]);
    assert.deepEqual(asistente.podarPila([{ p: 'asesor' }], CATALOGO), [{ p: 'menu' }, { p: 'asesor' }]);
});

test('enlaceWeb solo acepta páginas del catálogo de la propia web (REQ-WEB-20, 21)', () => {
    assert.equal(asistente.enlaceWeb('/servicios/ensayo-cbr/'), '/servicios/ensayo-cbr/');
    assert.equal(asistente.enlaceWeb('/servicios/mecanica-de-suelos/'), '/servicios/mecanica-de-suelos/');
    for (const malo of [null, undefined, '', '/servicios/', 'https://otro.com/servicios/x/',
        '//otro.com/servicios/x/', 'javascript:alert(1)', '/servicios/../admin/', '/contacto/']) {
        assert.equal(asistente.enlaceWeb(malo), null, String(malo));
    }
});
