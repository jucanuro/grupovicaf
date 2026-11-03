// VCF-LIMS: Análisis con tabla dinámica (proc/VCF-LIMS_HU_CU_analisis_v3,
// HU-LIMS-06 a 10). Datos de `sembrar_e2e`: COT-E2E-A01..A03 en febrero de
// 2001 (Constructora S/ 1 770, Minera S/ 236) y una plantilla que no cuenta.
const fs = require('fs');
const { test, expect } = require('@playwright/test');
const { LAB_URL, USUARIOS } = require('./datos');
const { entrarAlLab } = require('./ayudas');

const ANALISIS = `${LAB_URL}/analisis/`;
const FEBRERO = `${ANALISIS}?conjunto=cotizaciones&desde=2001-02-01&hasta=2001-02-28`;

async function abrirFebrero(page) {
    await page.goto(FEBRERO);
    await expect(page.locator('table.pvtTable')).toBeVisible();
}

async function vistaRapida(page, nombre) {
    await page.locator(`[data-vista-rapida="${nombre}"]`).click();
    await expect(page.locator('table.pvtTable, [data-grafico]').first()).toBeVisible();
}

/** Arrastra un campo (jQuery UI sortable necesita movimientos intermedios). */
async function arrastrar(page, campo, destino) {
    const origen = page.locator('.pvtAxisContainer li span.pvtAttr', { hasText: new RegExp(`^${campo}`) }).first();
    const a = await origen.boundingBox();
    const b = await page.locator(destino).boundingBox();
    await page.mouse.move(a.x + a.width / 2, a.y + a.height / 2);
    await page.mouse.down();
    await page.mouse.move(a.x + a.width / 2 + 10, a.y + a.height / 2 + 10, { steps: 5 });
    await page.mouse.move(b.x + 30, b.y + b.height / 2, { steps: 15 });
    await page.mouse.up();
}

test.describe('análisis del coordinador', () => {
    test.beforeEach(async ({ page }) => {
        await entrarAlLab(page, USUARIOS.coordinador);
    });

    test('vista rápida por cliente con montos y sin plantillas (CA-06.1, 06.7, 08.1)', async ({ page }) => {
        await abrirFebrero(page);
        await vistaRapida(page, 'Total por cliente');
        const tabla = page.locator('table.pvtTable');
        await expect(tabla.locator('tr', { hasText: 'Constructora E2E SAC' })).toContainText('1,770.00');
        await expect(tabla.locator('tr', { hasText: 'Minera E2E SAC' })).toContainText('236.00');
        await expect(tabla.locator('.pvtGrandTotal')).toHaveText('2,006.00');
        await expect(page.locator('#an-estado')).toContainText('3 registros');
    });

    test('arrastrar un campo a columnas y cambiar el cálculo (CA-06.2, 06.3)', async ({ page }) => {
        await abrirFebrero(page);
        await vistaRapida(page, 'Total por cliente');
        await arrastrar(page, 'Estado', 'td.pvtCols');
        const tabla = page.locator('table.pvtTable');
        await expect(tabla.locator('th.pvtColLabel', { hasText: 'Aceptada' })).toBeVisible();
        await expect(tabla.locator('th.pvtColLabel', { hasText: 'Pendiente' })).toBeVisible();

        await page.locator('select.pvtAggregator').selectOption('Cantidad');
        await expect(tabla.locator('.pvtGrandTotal')).toHaveText('3');
        // La disposición queda en el enlace (CA-06.2).
        expect(decodeURIComponent(page.url())).toContain('"cols":["Estado"]');
    });

    test('el enlace abre la misma tabla (CA-08.3)', async ({ page }) => {
        await abrirFebrero(page);
        await vistaRapida(page, 'Saldo referencial por cliente');
        await expect(page.locator('table.pvtTable .pvtGrandTotal')).toHaveText('590.00');
        const enlace = page.url();

        await page.goto(`${ANALISIS}?conjunto=items`);
        await page.goto(enlace);
        await expect(page.locator('table.pvtTable .pvtGrandTotal')).toHaveText('590.00');
        await expect(page.locator('#an-desde')).toHaveValue('2001-02-01');
    });

    test('ver como gráfico de barras y dona (CA-07.1, 07.4)', async ({ page }) => {
        await abrirFebrero(page);
        await vistaRapida(page, 'Cantidad por mes y estado');
        await expect(page.locator('[data-grafico][data-tipo="apiladas"] canvas[data-listo]')).toBeVisible();

        await page.locator('select.pvtRenderer').selectOption('Dona');
        await expect(page.locator('[data-grafico][data-tipo="dona"] canvas[data-listo]')).toBeVisible();
        await expect(page.locator('[data-aviso-grafico]')).toContainText('total por fila');

        await page.locator('select.pvtRenderer').selectOption('Tabla');
        await expect(page.locator('table.pvtTable')).toBeVisible();
    });

    test('exporta a Excel con montos como números (CA-09.1, 09.2)', async ({ page }) => {
        await abrirFebrero(page);
        await vistaRapida(page, 'Total por cliente');
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
        const constructora = hoja.find((fila) => fila[0] === 'Constructora E2E SAC');
        expect(constructora[1]).toBe(1770);
        const totales = hoja.find((fila) => fila[0] === 'Totales' && typeof fila[1] === 'number');
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
        await vistaRapida(page, 'Monto por estado');
        await page.locator('#an-nombre-vista').fill(nombre);
        await page.locator('#an-guardar-vista').click();
        await expect(page.locator('#an-aviso')).toContainText('guardada');

        await vistaRapida(page, 'Total por cliente');
        await page.locator('#an-mis-vistas').selectOption({ label: nombre });
        await expect(page.locator('table.pvtTable th.pvtRowLabel', { hasText: 'Aceptada' })).toBeVisible();

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

    test('el menú de inicio lleva a Análisis', async ({ page }) => {
        await expect(page.locator(`a[href="/analisis/"]`).first()).toBeAttached();
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
        await expect(page.locator('#an-conjunto option')).toHaveText(['Clientes · Clientes']);
        // Abre con su primera vista rápida permitida (la de montos no se ofrece).
        await expect(page.locator('[data-vista-rapida]').first()).toHaveText('Clientes nuevos por mes');
        await expect(page.locator('[data-vista-rapida="Cotizado por cliente"]')).toHaveCount(0);
        await expect(page.locator('.pvtAttr', { hasText: 'N.º cotizaciones' })).toHaveCount(1);
        await expect(page.locator('.pvtAttr', { hasText: 'Monto' })).toHaveCount(0);
        const resp = await page.request.get(`${LAB_URL}/analisis/datos/cotizaciones/`);
        expect(resp.status()).toBe(403);
    });
});
