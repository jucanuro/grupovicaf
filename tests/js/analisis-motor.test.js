// Pruebas del motor de la pantalla Análisis (VCF-LIMS, HU-LIMS-06 a 10).
// Ejecutar con: node --test 'tests/js/*.test.js'
const test = require('node:test');
const assert = require('node:assert/strict');

const motor = require('../../static/js/analisis-motor.js');

const CAMPOS = [
    { etiqueta: 'Cliente', tipo: 'texto' },
    { etiqueta: 'Mes', tipo: 'periodo' },
    { etiqueta: 'Estado', tipo: 'texto' },
    { etiqueta: 'Total (con IGV)', tipo: 'moneda' },
    { etiqueta: 'Días de atraso', tipo: 'dias' },
];
const CONTEO = 'N.º de cotizaciones';
const DATOS = {
    encabezado: ['Cliente', 'Mes', 'Estado', 'Total (con IGV)', 'Días de atraso'],
    filas: [
        ['Constructora', '2001-02', 'Aceptada', 1180, 2],
        ['Constructora', '2001-02', 'Aceptada', 590, null],
        ['Minera', '2001-01', 'Pendiente', 236, 5],
    ],
};

test('los números se muestran según lo que son', () => {
    assert.equal(motor.formatear('moneda', 'suma', 1770), 'S/ 1,770.00');
    assert.equal(motor.formatear('moneda', 'suma', 12500, true), 'S/ 12.5 mil');
    assert.equal(motor.formatear('conteo', 'conteo', 30), '30');
    assert.equal(motor.formatear('cantidad', 'suma', 30), '30');
    assert.equal(motor.formatear('cantidad', 'suma', 2.5), '2.5');
    assert.equal(motor.formatear('dias', 'promedio', 3.456), '3.5');
    assert.equal(motor.formatear('porcentaje', 'promedio', 45), '45 %');
    assert.equal(motor.formatear('moneda', 'suma', null), '—');
});

test('al soltar un campo se elige el cálculo que tiene sentido', () => {
    assert.equal(motor.calculoPorDefecto('moneda'), 'suma');
    assert.equal(motor.calculoPorDefecto('cantidad'), 'suma');
    assert.equal(motor.calculoPorDefecto('dias'), 'promedio');
    assert.equal(motor.calculoPorDefecto('conteo'), 'conteo');
});

test('los meses se leen como "feb 2001"', () => {
    assert.equal(motor.etiquetaDimension('periodo', '2001-02'), 'feb 2001');
    assert.equal(motor.etiquetaDimension('periodo', '2001-02-03'), '3 feb 2001');
    assert.equal(motor.etiquetaDimension('texto', ''), '(vacío)');
});

test('la disposición conserva solo lo que existe en el conjunto (CA-06.5)', () => {
    const disp = motor.disposicionValida({
        filas: ['Cliente', 'Técnico', 'Cliente'], columnas: ['Estado'],
        valores: [['Total (con IGV)', 'suma'], ['N.º de ensayos', 'conteo'], ['Cliente', 'suma']],
        solo: { Estado: ['Aceptada'], Técnico: ['A'] }, vista: 'pastel',
    }, CAMPOS, CONTEO);
    assert.deepEqual(disp.filas, ['Cliente']);
    assert.deepEqual(disp.columnas, ['Estado']);
    assert.deepEqual(disp.valores, [['Total (con IGV)', 'suma'], [CONTEO, 'conteo']]);
    assert.deepEqual(disp.solo, { Estado: ['Aceptada'] });
    assert.equal(disp.vista, 'tabla');
});

test('calcula totales por fila, columna y general', () => {
    const disp = motor.disposicionValida({
        filas: ['Cliente'], columnas: ['Estado'],
        valores: [['Total (con IGV)', 'suma'], [CONTEO, 'conteo'], ['Días de atraso', 'promedio']],
    }, CAMPOS, CONTEO);
    const r = motor.calcular(DATOS, disp, CAMPOS);
    assert.equal(r.registros, 3);
    assert.deepEqual(r.filas, [['Constructora'], ['Minera']]);  // mayor monto primero
    assert.deepEqual(r.columnas, [['Aceptada'], ['Pendiente']]);
    assert.equal(r.celda(['Constructora'], ['Aceptada'], 0), 1770);
    assert.equal(r.celda(['Constructora'], ['Pendiente'], 0), null);
    assert.equal(r.celda(['Constructora'], ['Pendiente'], 1), 0);
    assert.equal(r.celda(null, null, 0), 2006);
    assert.equal(r.celda(null, null, 1), 3);
    // El promedio ignora los vacíos: (2 + 5) / 2.
    assert.equal(r.celda(null, null, 2), 3.5);
});

test('filtra con "solo" y "excluir" y ordena el tiempo cronológicamente', () => {
    const disp = motor.disposicionValida({
        filas: ['Mes'], valores: [[CONTEO, 'conteo']], excluir: { Estado: ['Pendiente'] },
    }, CAMPOS, CONTEO);
    let r = motor.calcular(DATOS, disp, CAMPOS);
    assert.deepEqual(r.filas, [['2001-02']]);
    disp.excluir = {};
    r = motor.calcular(DATOS, disp, CAMPOS);
    assert.deepEqual(r.filas, [['2001-01'], ['2001-02']]);
    disp.solo = { Cliente: ['Minera'] };
    r = motor.calcular(DATOS, disp, CAMPOS);
    assert.equal(r.celda(null, null, 0), 1);
});
