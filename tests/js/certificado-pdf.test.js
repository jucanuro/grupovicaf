// Pruebas de las funciones puras del visor de certificados (specs/WEB v3, T14).
// Ejecutar con: node --test 'tests/js/*.test.js'
const test = require('node:test');
const assert = require('node:assert/strict');

const visor = require('../../static/web/js/certificado-pdf.js');

function medios(coincide) {
    const consultas = [];
    const matchMedia = (consulta) => {
        consultas.push(consulta);
        return { matches: coincide };
    };
    matchMedia.consultas = consultas;
    return matchMedia;
}

test('escritorio con visor de PDF usa el modal (REQ-WEB-32)', () => {
    const matchMedia = medios(true);
    assert.equal(visor.debeUsarModal({ pdfViewerEnabled: true }, matchMedia), true);
    assert.deepEqual(matchMedia.consultas, ['(min-width: 768px) and (hover: hover) and (pointer: fine)']);
});

test('navegador que no conoce pdfViewerEnabled se trata como con visor', () => {
    assert.equal(visor.debeUsarModal({}, medios(true)), true);
});

test('móvil, tableta o pantalla chica abre pestaña nueva (REQ-WEB-35)', () => {
    // Android/iOS: puntero táctil o menos de 768 px → la consulta no coincide.
    assert.equal(visor.debeUsarModal({ pdfViewerEnabled: true }, medios(false)), false);
});

test('sin visor de PDF abre pestaña nueva aunque sea escritorio (REQ-WEB-35)', () => {
    assert.equal(visor.debeUsarModal({ pdfViewerEnabled: false }, medios(true)), false);
});

test('sin matchMedia no arriesga el modal', () => {
    assert.equal(visor.debeUsarModal({ pdfViewerEnabled: true }, undefined), false);
});

test('Tab cicla hacia adelante y vuelve al primero (REQ-WEB-34)', () => {
    assert.equal(visor.siguienteFoco(4, 0, false), 1);
    assert.equal(visor.siguienteFoco(4, 2, false), 3);
    assert.equal(visor.siguienteFoco(4, 3, false), 0);
});

test('Shift+Tab cicla hacia atrás y salta al último', () => {
    assert.equal(visor.siguienteFoco(4, 3, true), 2);
    assert.equal(visor.siguienteFoco(4, 0, true), 3);
});

test('foco fuera del modal entra por el primero o el último', () => {
    assert.equal(visor.siguienteFoco(4, -1, false), 0);
    assert.equal(visor.siguienteFoco(4, -1, true), 3);
    assert.equal(visor.siguienteFoco(0, -1, false), -1);
    assert.equal(visor.siguienteFoco(1, 0, false), 0);
});
