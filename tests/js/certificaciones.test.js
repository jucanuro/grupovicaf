// Pruebas de las funciones puras del modal de certificaciones (specs/WEB v4, T18; v3, T14).
// Ejecutar con: node --test 'tests/js/*.test.js'
const test = require('node:test');
const assert = require('node:assert/strict');

const visor = require('../../static/web/js/certificaciones.js');

function medios(coincide) {
    const consultas = [];
    const matchMedia = (consulta) => {
        consultas.push(consulta);
        return { matches: coincide };
    };
    matchMedia.consultas = consultas;
    return matchMedia;
}

test('escritorio con visor de PDF usa el modal (REQ-WEB-46)', () => {
    const matchMedia = medios(true);
    assert.equal(visor.debeUsarModal({ pdfViewerEnabled: true }, matchMedia), true);
    assert.deepEqual(matchMedia.consultas, ['(min-width: 768px) and (hover: hover) and (pointer: fine)']);
});

test('navegador que no conoce pdfViewerEnabled se trata como con visor', () => {
    assert.equal(visor.debeUsarModal({}, medios(true)), true);
});

test('móvil, tableta o pantalla chica abre pestaña nueva (REQ-WEB-46)', () => {
    // Android/iOS: puntero táctil o menos de 768 px → la consulta no coincide.
    assert.equal(visor.debeUsarModal({ pdfViewerEnabled: true }, medios(false)), false);
});

test('sin visor de PDF abre pestaña nueva aunque sea escritorio (REQ-WEB-46)', () => {
    assert.equal(visor.debeUsarModal({ pdfViewerEnabled: false }, medios(true)), false);
});

test('sin matchMedia no arriesga el modal', () => {
    assert.equal(visor.debeUsarModal({ pdfViewerEnabled: true }, undefined), false);
});

test('Tab cicla hacia adelante y vuelve al primero (REQ-WEB-48)', () => {
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

test('imagen siempre en el modal, también en móvil y sin visor de PDF (REQ-WEB-45)', () => {
    assert.equal(visor.modoApertura('imagen', { pdfViewerEnabled: true }, medios(true)), 'imagen');
    assert.equal(visor.modoApertura('imagen', { pdfViewerEnabled: false }, medios(false)), 'imagen');
    assert.equal(visor.modoApertura('imagen', {}, undefined), 'imagen');
});

test('PDF en el modal solo en escritorio con visor (REQ-WEB-46)', () => {
    assert.equal(visor.modoApertura('pdf', { pdfViewerEnabled: true }, medios(true)), 'pdf');
    assert.equal(visor.modoApertura('pdf', { pdfViewerEnabled: true }, medios(false)), 'pestana');
    assert.equal(visor.modoApertura('pdf', { pdfViewerEnabled: false }, medios(true)), 'pestana');
});

test('tipo desconocido o vacío no intercepta el enlace', () => {
    assert.equal(visor.modoApertura('', {}, medios(true)), 'pestana');
    assert.equal(visor.modoApertura(null, {}, medios(true)), 'pestana');
});
