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
