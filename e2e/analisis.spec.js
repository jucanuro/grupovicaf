// VCF-LIMS: Análisis con menú de conjuntos y zonas para arrastrar
// (proc/VCF-LIMS_HU_CU_analisis_v3, HU-LIMS-06 a 10). Datos de `sembrar_e2e`:
// COT-E2E-A01..A03 en febrero de 2001 (Constructora S/ 1 770, Minera S/ 236)
// y una plantilla que no cuenta.
const fs = require('fs');
const { test, expect } = require('@playwright/test');
const { LAB_URL, USUARIOS } = require('./datos');
const { entrarAlLab } = require('./ayudas');

const ANALISIS = `${LAB_URL}/analisis/`;
const FEBRERO = `${ANALISIS}?conjunto=cotizaciones&desde=2001-02-01&hasta=2001-02-28`;

async function abrirFebrero(page) {
    await page.goto(FEBRERO);
    await expect(page.locator('#an-estado')).toContainText('registros');
}

async function pregunta(page, nombre) {
    await page.locator(`[data-vista-rapida="${nombre}"]`).click();
    await expect(page.locator('table.an-tabla, [data-grafico] canvas[data-listo]').first()).toBeVisible();
}

const fila = (page, texto) => page.locator('table.an-tabla tbody tr', { has: page.locator('td.an-fila', { hasText: texto }) });
const totalGeneral = (page) => page.locator('table.an-tabla [data-total-general]');
const campoDelMenu = (page, campo) => page.locator(`#an-menu .an-ficha[data-campo="${campo}"]`);
const zona = (page, nombre) => page.locator(`[data-zona="${nombre}"]`);

test.describe('análisis del coordinador', () => {
    test.beforeEach(async ({ page }) => {
        await entrarAlLab(page, USUARIOS.coordinador);
    });

    test('pregunta frecuente por cliente con montos en soles y sin plantillas (CA-06.1, 06.7, 08.1)', async ({ page }) => {
        await abrirFebrero(page);
        await pregunta(page, '¿Cuánto cotizamos por cliente?');
        await expect(fila(page, 'Constructora E2E SAC')).toContainText('S/ 1,770.00');
        await expect(fila(page, 'Minera E2E SAC')).toContainText('S/ 236.00');
        await expect(totalGeneral(page)).toHaveText('S/ 2,006.00');
        await expect(page.locator('[data-frase]')).toContainText('Total (con IGV) por Cliente');
        await expect(page.locator('[data-kpi="registros"] .an-kpi-valor')).toHaveText('3');
        await expect(page.locator('#an-estado')).toContainText('3 registros');
    });

    test('el menú muestra los campos del conjunto para agrupar y medir', async ({ page }) => {
        await abrirFebrero(page);
        const campos = page.locator('[data-campos-de="cotizaciones"]');
        await expect(campos.locator('.an-ficha[data-campo="Cliente"][data-tipo="texto"]')).toBeVisible();
        await expect(campos.locator('.an-ficha[data-campo="Total (con IGV)"][data-tipo="moneda"]')).toBeVisible();
        await expect(campos.locator('.an-ficha[data-campo="N.º de cotizaciones"][data-tipo="conteo"]')).toBeVisible();
    });

    test('arrastrar al centro, tocar para agregar y cambiar el cálculo (CA-06.2, 06.3)', async ({ page }) => {
        await abrirFebrero(page);
        await pregunta(page, '¿Cuánto cotizamos por cliente?');
        await campoDelMenu(page, 'Estado').dragTo(zona(page, 'columnas'));
        await expect(zona(page, 'columnas').locator('.an-ficha[data-campo="Estado"]')).toBeVisible();
        await expect(page.locator('table.an-tabla thead th', { hasText: 'Aceptada' })).toBeVisible();
        await expect(page.locator('table.an-tabla thead th', { hasText: 'Pendiente' })).toBeVisible();

        // Tocar un número lo lleva a Valores con su cálculo por defecto.
        await campoDelMenu(page, 'N.º de cotizaciones').click();
        await expect(page.locator('[data-kpi="N.º de cotizaciones"] .an-kpi-valor')).toHaveText('3');

        await zona(page, 'valores').locator('select[data-calculo="0"]').selectOption('promedio');
        await expect(page.locator('[data-kpi="Total (con IGV)"] .an-kpi-valor')).toHaveText('S/ 668.67');
        // La disposición queda en el enlace (CA-06.2).
        expect(decodeURIComponent(page.url())).toContain('"columnas":["Estado"]');

        // Quitar un campo con la ×.
        await zona(page, 'columnas').locator('[data-quitar="Estado"]').click();
        await expect(page.locator('table.an-tabla thead th', { hasText: 'Pendiente' })).toHaveCount(0);
    });

    test('filtra arrastrando un campo a Filtros', async ({ page }) => {
        await abrirFebrero(page);
        await pregunta(page, '¿Cuánto cotizamos por cliente?');
        await campoDelMenu(page, 'Estado').dragTo(zona(page, 'filtros'));
        const emergente = page.locator('[data-emergente="Estado"]');
        await expect(emergente).toBeVisible();
        await emergente.locator('input[value="Pendiente"]').uncheck();
        await expect(totalGeneral(page)).toHaveText('S/ 1,770.00');
        await expect(zona(page, 'filtros').locator('[data-abrir-filtro="Estado"]')).toContainText('Aceptada');
    });

    test('el enlace abre la misma tabla (CA-08.3)', async ({ page }) => {
        await abrirFebrero(page);
        await pregunta(page, '¿Cuánto falta cobrar y de quién?');
        await expect(totalGeneral(page)).toHaveText('S/ 590.00');
        const enlace = page.url();

        await page.goto(`${ANALISIS}?conjunto=items`);
        await page.goto(enlace);
        await expect(totalGeneral(page)).toHaveText('S/ 590.00');
        await expect(page.locator('#an-desde')).toHaveValue('2001-02-01');
    });

    test('ver como barras, líneas y dona (CA-07.1, 07.4)', async ({ page }) => {
        await abrirFebrero(page);
        await pregunta(page, '¿Cuántas cotizaciones por mes y estado?');
        await expect(page.locator('[data-grafico][data-tipo="barras"] canvas[data-listo]')).toBeVisible();

        await page.locator('[data-vista="lineas"]').click();
        await expect(page.locator('[data-grafico][data-tipo="lineas"] canvas[data-listo]')).toBeVisible();

        await page.locator('[data-vista="dona"]').click();
        await expect(page.locator('[data-grafico][data-tipo="dona"] canvas[data-listo]')).toBeVisible();
        await expect(page.locator('[data-aviso-grafico]')).toContainText('total por fila');

        await page.locator('[data-vista="tabla"]').click();
        await expect(page.locator('table.an-tabla')).toBeVisible();
    });

    test('exporta a Excel con montos como números (CA-09.1, 09.2)', async ({ page }) => {
        await abrirFebrero(page);
        await pregunta(page, '¿Cuánto cotizamos por cliente?');
        const [descarga] = await Promise.all([
            page.waitForEvent('download'),
            page.locator('#an-exportar').click(),
        ]);
        expect(descarga.suggestedFilename()).toMatch(/^analisis-cotizaciones-tabla-.*\.xlsx$/);
        const base64 = fs.readFileSync(await descarga.path()).toString('base64');
        const hoja = await page.evaluate((b64) => {
            const libro = window.XLSX.read(b64, { type: 'base64' });
            const h = libro.Sheets[libro.SheetNames[0]];
            return window.XLSX.utils.sheet_to_json(h, { header: 1, raw: true });
        }, base64);
        expect(hoja[1]).toEqual(['Conjunto', 'Cotizaciones']);
        const constructora = hoja.find((f) => f[0] === 'Constructora E2E SAC');
        expect(constructora[1]).toBe(1770);
        const totales = hoja.find((f) => f[0] === 'Total' && typeof f[1] === 'number');
        expect(totales[1]).toBe(2006);

        const [datos] = await Promise.all([
            page.waitForEvent('download'),
            page.locator('#an-exportar-datos').click(),
        ]);
        expect(datos.suggestedFilename()).toMatch(/^analisis-cotizaciones-datos-.*\.xlsx$/);
    });

    test('guarda, abre y elimina una vista propia (CA-08.2)', async ({ page }) => {
        const nombre = `Vista E2E ${Date.now()}`;
        await abrirFebrero(page);
        await pregunta(page, '¿Cuánto hay en cada estado?');
        await page.locator('#an-nombre-vista').fill(nombre);
        await page.locator('#an-guardar-vista').click();
        await expect(page.locator('#an-aviso')).toContainText('guardada');

        await pregunta(page, '¿Cuánto cotizamos por cliente?');
        await page.locator('#an-mis-vistas').selectOption({ label: nombre });
        await expect(fila(page, 'Aceptada')).toBeVisible();

        page.once('dialog', (d) => d.accept());
        await page.locator('#an-eliminar-vista').click();
        await expect(page.locator('#an-aviso')).toContainText('eliminada');
        await expect(page.locator('#an-mis-vistas option', { hasText: nombre })).toHaveCount(0);
    });

    test('avisa rango invertido y periodo sin datos (CA-06.6, 06.7)', async ({ page }) => {
        await abrirFebrero(page);
        await page.locator('#an-desde').fill('2001-03-31');
        await page.locator('#an-hasta').fill('2001-03-01');
        await page.locator('#an-aplicar').click();
        await expect(page.locator('#an-aviso[data-tipo="error"]')).toContainText('posterior');

        await page.locator('#an-desde').fill('2001-03-01');
        await page.locator('#an-hasta').fill('2001-03-31');
        await page.locator('#an-aplicar').click();
        await expect(page.locator('#an-aviso')).toContainText('Sin datos para estos filtros');
    });

    test('cambia a un conjunto del laboratorio desde el menú y conserva lo compatible (CA-06.1b, 06.5)', async ({ page }) => {
        await abrirFebrero(page);
        await pregunta(page, '¿Cuánto hay en cada estado?');
        const claves = await page.locator('#an-menu [data-conjunto]').evaluateAll((bs) => bs.map((b) => b.dataset.conjunto));
        expect(claves).toEqual(expect.arrayContaining(['cotizaciones', 'clientes', 'solicitudes', 'ensayos', 'bandeja-web']));
        // Sin muestras.ver, informes.ver, proyectos.ver ni calendario.ver.
        expect(claves).not.toEqual(expect.arrayContaining(['muestras']));
        expect(claves.join('|')).not.toMatch(/informes|proyectos|actividades/);

        await page.locator('[data-conjunto="solicitudes"]').click();
        await expect(page.locator('[data-conjunto="solicitudes"]')).toHaveAttribute('aria-expanded', 'true');
        await page.locator('[data-periodo="todo"]').click();
        // "Estado" existe también en Solicitudes: la fila se conserva.
        await expect(fila(page, 'En proceso')).toBeVisible();
        expect(decodeURIComponent(page.url())).toContain('conjunto=solicitudes');

        await page.locator('[data-conjunto="ensayos"]').click();
        await pregunta(page, '¿Quién va a tiempo y quién atrasado?');
        await expect(page.locator('[data-grafico][data-tipo="barras"] canvas[data-listo]')).toBeVisible();
        await page.locator('[data-vista="tabla"]').click();
        await expect(fila(page, 'Técnico E2E A')).toBeVisible();
    });

    test('el menú de inicio lleva a Análisis', async ({ page }) => {
        await expect(page.locator('a[href="/analisis/"]').first()).toBeAttached();
    });
});

test.describe('permisos de Análisis', () => {
    test('el técnico no ve el menú ni entra (CA-10.1)', async ({ page }) => {
        await entrarAlLab(page, USUARIOS.tecnicoAsignado);
        await expect(page.locator('a[href="/analisis/"]')).toHaveCount(0);
        const resp = await page.goto(ANALISIS);
        expect(resp.status()).toBe(403);
    });

    test('sin cotizaciones.ver solo ve Clientes y sin montos (CA-10.1b, DP-LIMS-12)', async ({ page }) => {
        await entrarAlLab(page, USUARIOS.analista);
        await page.goto(ANALISIS);
        await expect(page.locator('#an-menu [data-conjunto]')).toHaveCount(1);
        await expect(page.locator('#an-menu [data-conjunto="clientes"]')).toBeVisible();
        // Abre con su primera pregunta permitida (la de montos no se ofrece).
        await expect(page.locator('[data-vista-rapida]').first()).toHaveText('¿Cuántos clientes nuevos por mes?');
        await expect(page.locator('[data-vista-rapida="¿Cuánto le cotizamos a cada cliente?"]')).toHaveCount(0);
        await expect(campoDelMenu(page, 'N.º cotizaciones')).toHaveCount(1);
        await expect(page.locator('#an-menu .an-ficha', { hasText: 'Monto' })).toHaveCount(0);
        const resp = await page.request.get(`${LAB_URL}/analisis/datos/cotizaciones/`);
        expect(resp.status()).toBe(403);
    });
});
