// Gantt de ensayos (HU-LIMS-22, REQ-LIMS-74 a 84): agrupado por solicitud,
// avance real, atraso en rojo con «+N d», cifras que filtran, ficha de
// detalle y vista del técnico. Datos: `python manage.py sembrar_e2e`
// (SOL-E2E-G01 terminada, G02 con una línea atrasada 4 días, G03 sin empezar).
const { test, expect } = require('@playwright/test');
const { LAB_URL, USUARIOS } = require('./datos');
const { entrarAlLab, cdnLocal } = require('./ayudas');

test.beforeEach(async ({ context, page }) => {
    await cdnLocal(context);
    await page.setViewportSize({ width: 1440, height: 900 });
});

async function abrirGantt(page, usuario, grupos = 3) {
    await entrarAlLab(page, usuario);
    await page.goto(`${LAB_URL}/actividades/gantt/`);
    await page.evaluate(() => { try { localStorage.clear(); } catch (e) { /* sin almacenamiento */ } });
    await page.reload();
    await expect(page.locator('#vg-cuerpo .vg-grupo').first()).toBeVisible();
    // Solo las solicitudes sembradas para el Gantt.
    await page.locator('#vg-buscar').fill('sol-e2e-g');
    await expect(page.locator('#vg-cuerpo .vg-grupo')).toHaveCount(grupos);
}

const grupo = (page, codigo) => page.locator('#vg-cuerpo .vg-grupo', { has: page.locator('.vg-gt', { hasText: codigo }) });
const linea = (page, ensayo) => page.locator('#vg-cuerpo .vg-fila', { has: page.locator('.vg-s', { hasText: ensayo }) });

test('agrupa por solicitud, pone primero la atrasada y marca el atraso', async ({ page }) => {
    await abrirGantt(page, USUARIOS.gantt);
    await expect(page.locator('#vg-cuerpo .vg-grupo').first().locator('.vg-gt')).toContainText('SOL-E2E-G02');
    await expect(grupo(page, 'SOL-E2E-G01').locator('.vg-cnt')).toContainText('2/2 listos');
    await expect(grupo(page, 'SOL-E2E-G02').locator('.vg-cnt')).toContainText('1/3 listos');
    await expect(linea(page, 'Análisis granulométrico').locator('.vg-flag')).toHaveText('+4 d');
    await expect(linea(page, 'Corte directo').locator('.vg-bar')).toHaveClass(/pend/);
});

test('la cifra de atrasados filtra las líneas', async ({ page }) => {
    await abrirGantt(page, USUARIOS.gantt);
    await page.locator('#vg-kpis [data-kpi="atraso"]').click();
    await expect(page.locator('#vg-kpis [data-kpi="atraso"]')).toHaveAttribute('aria-pressed', 'true');
    await expect(page.locator('#vg-cuerpo .vg-bar')).toHaveCount(1);
    await expect(linea(page, 'Análisis granulométrico')).toBeVisible();
});

test('la ficha de una línea lleva a sus resultados', async ({ page }) => {
    await abrirGantt(page, USUARIOS.gantt);
    await linea(page, 'Corte directo').locator('.vg-bar').click();
    const ficha = page.locator('#vg-pop');
    await expect(ficha).toBeVisible();
    await expect(ficha).toContainText('SOL-E2E-G03');
    await expect(ficha).toContainText('Sin empezar');
    await expect(ficha.getByRole('link', { name: 'Abrir resultados' })).toHaveAttribute('href', /\/proyectos\/resultados\/solicitud\/\d+\//);
    await page.keyboard.press('Escape');
    await expect(ficha).toBeHidden();
});

test('el técnico solo ve sus líneas', async ({ page }) => {
    await entrarAlLab(page, USUARIOS.tecnicoGanttC);
    await page.goto(`${LAB_URL}/actividades/gantt/`);
    await page.evaluate(() => { try { localStorage.clear(); } catch (e) { /* sin almacenamiento */ } });
    await page.reload();
    await expect(linea(page, 'Corte directo')).toBeVisible();
    await expect(linea(page, 'Análisis granulométrico')).toHaveCount(0);  // es de Carlos
});

test('en el celular cada solicitud es una tarjeta', async ({ page }) => {
    await page.setViewportSize({ width: 390, height: 844 });
    // En el celular se abre la semana: G01 ya terminó antes y queda fuera.
    await abrirGantt(page, USUARIOS.gantt, 2);
    const tarjeta = grupo(page, 'SOL-E2E-G02');
    await expect(tarjeta).toBeVisible();
    const caja = await tarjeta.boundingBox();
    expect(caja.width).toBeLessThanOrEqual(390);
    expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(390);
});
