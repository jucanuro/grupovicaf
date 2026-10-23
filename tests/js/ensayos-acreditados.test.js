// Pruebas de las funciones puras del buscador de ensayos acreditados (specs/WEB v5, T21).
// Ejecutar con: node --test 'tests/js/*.test.js'
const test = require('node:test');
const assert = require('node:assert/strict');

const ensayos = require('../../static/web/js/ensayos-acreditados.js');

test('normalizar quita tildes, mayúsculas y espacios de más', () => {
    assert.equal(ensayos.normalizar('  Relación   de SOPORTE  '), 'relacion de soporte');
    assert.equal(ensayos.normalizar('Pingüino Ñandú'), 'pinguino nandu');
    assert.equal(ensayos.normalizar(null), '');
});

test('coincide sin distinguir tildes ni mayúsculas (REQ-WEB-56)', () => {
    const texto = 'Relación de soporte de California NTP 339.145 Compactación Mecánica de Suelos';
    assert.equal(ensayos.coincide(texto, 'relacion'), true);
    assert.equal(ensayos.coincide(texto, 'MECANICA'), true);
    assert.equal(ensayos.coincide(texto, 'ntp 339.145'), true);
    assert.equal(ensayos.coincide(texto, 'proctor'), false);
});

test('todas las palabras deben estar, en cualquier orden', () => {
    const texto = 'Ensayo de compresión de testigos de concreto';
    assert.equal(ensayos.coincide(texto, 'concreto compresion'), true);
    assert.equal(ensayos.coincide(texto, 'concreto suelos'), false);
});

test('consulta vacía o solo espacios coincide siempre', () => {
    assert.equal(ensayos.coincide('cualquier cosa', ''), true);
    assert.equal(ensayos.coincide('cualquier cosa', '   '), true);
    assert.equal(ensayos.coincide('', undefined), true);
});

test('visible combina buscador y filtro por línea (REQ-WEB-57)', () => {
    const item = { linea: 'mecanica-de-suelos', buscar: 'Contenido de humedad ASTM D2216' };
    assert.equal(ensayos.visible(item, '', ''), true);
    assert.equal(ensayos.visible(item, 'humedad', 'mecanica-de-suelos'), true);
    assert.equal(ensayos.visible(item, 'humedad', 'concreto'), false);
    assert.equal(ensayos.visible(item, 'cbr', ''), false);
});

test('texto del contador anunciado (REQ-WEB-56 y 58)', () => {
    assert.equal(ensayos.textoResultados(99, 99), 'Se muestran los 99 ensayos acreditados.');
    assert.equal(ensayos.textoResultados(12, 99), '12 ensayos acreditados coinciden.');
    assert.equal(ensayos.textoResultados(1, 99), '1 ensayo acreditado coincide.');
    assert.equal(ensayos.textoResultados(0, 99), 'Ningún ensayo acreditado coincide.');
});

test('Tab y Shift+Tab ciclan dentro del modal (REQ-WEB-59)', () => {
    assert.equal(ensayos.siguienteFoco(3, 2, false), 0);
    assert.equal(ensayos.siguienteFoco(3, 0, true), 2);
    assert.equal(ensayos.siguienteFoco(3, -1, false), 0);
    assert.equal(ensayos.siguienteFoco(0, -1, false), -1);
});
