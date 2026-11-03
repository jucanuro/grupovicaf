// VCF-LIMS: dashboard del LIMS y estados de la cotización
// (specs/VCF-LIMS/requirements.md). Datos de `sembrar_e2e`: COT-E2E-D01..D05,
// COT-E2E-MARCAR, SOL-E2E-V01..V06 y P-E2E-01..05. Las pruebas no fijan
// totales, para no depender de lo que ya haya en la base local.
const { test, expect } = require('@playwright/test');
const { LAB_URL, USUARIOS } = require('./datos');
const { entrarAlLab } = require('./ayudas');

const DASHBOARD = `${LAB_URL}/dashboard/`;
const SIN_DATOS = `${DASHBOARD}?periodo=rango&desde=2001-03-01&hasta=2001-03-31`;

/** Ancho renderizado de cada barra respecto de su contenedor (0-1). */
async function proporciones(page, selectorFila) {
    return page.locator(selectorFila).evaluateAll((filas) => filas.map((fila) => {
        const barra = fila.querySelector('[data-barra]');
        const contenedor = barra ? barra.parentElement.getBoundingClientRect().width : 1;
        return {
            cantidad: Number(fila.dataset.cantidad),
            ancho: barra ? barra.getBoundingClientRect().width / contenedor : 0,
        };
    }));
}

function esperarProporcional(filas) {
    const maximo = Math.max(...filas.map((f) => f.cantidad));
    expect(maximo).toBeGreaterThan(0);
    for (const fila of filas) {
        expect(fila.ancho).toBeCloseTo(fila.cantidad / maximo, 2);
    }
}

test.describe('dashboard del coordinador', () => {
    test.beforeEach(async ({ page }) => {
        await entrarAlLab(page, USUARIOS.coordinador);
    });

    test('muestra los 5 indicadores y ninguna meta inventada (REQ-LIMS-01, 04, 05)', async ({ page }) => {
        await page.goto(`${DASHBOARD}?periodo=mes`);

        for (const kpi of ['Clientes registrados', 'Cotizaciones emitidas', 'Tasa de aceptación',
            'Solicitudes vencidas', 'Informes por enviar']) {
            await expect(page.locator('[data-kpi]').filter({ hasText: kpi })).toBeVisible();
        }
        await expect(page.locator('[data-kpi="vencidas"]')).toContainText('Requieren atención');
        await expect(page.locator('[data-kpi="cotizaciones"]')).toContainText('periodo anterior');
        await expect(page.locator('[data-kpi="clientes"] svg polyline')).toHaveCount(1);
        expect(await page.content()).not.toMatch(/del objetivo/i);
        // Un solo <h1> en la página (el de la cabecera).
        await expect(page.getByRole('heading', { level: 1 })).toHaveCount(1);
    });

    test('el embudo tiene 3 etapas únicas con largo proporcional (REQ-LIMS-07, 08)', async ({ page }) => {
        await page.goto(`${DASHBOARD}?periodo=mes`);

        const etapas = page.locator('[data-embudo-etapa]');
        await expect(etapas).toHaveCount(3);
        expect(await etapas.evaluateAll((els) => els.map((e) => e.dataset.embudoEtapa)))
            .toEqual(['Emitidas', 'Enviadas al cliente', 'Aceptadas']);
        esperarProporcional(await proporciones(page, '[data-embudo-etapa]'));
        await expect(page.locator('[data-conversion-global]')).toContainText('Conversión global');
    });

    test('barras por mes y línea por semana se dibujan con Chart.js (REQ-LIMS-06, 14, 19)', async ({ page }) => {
        await page.goto(DASHBOARD);

        await expect(page.locator('#grafico-cotizaciones-mes')).toBeVisible();
        await expect(page.locator('#grafico-ensayos-semana')).toBeVisible();
        const graficos = await page.evaluate(() => ({
            chart: typeof window.Chart,
            barras: Boolean(window.Chart && window.Chart.getChart('grafico-cotizaciones-mes')),
            linea: Boolean(window.Chart && window.Chart.getChart('grafico-ensayos-semana')),
        }));
        expect(graficos).toEqual({ chart: 'function', barras: true, linea: true });
        const leyenda = page.locator('[data-grafico="cotizaciones-mes"] ul[aria-label="Leyenda"] li');
        await expect(leyenda).toHaveText(['Aceptadas', 'En gestión (pendiente o enviada)', 'Rechazadas o anuladas']);
    });

    test('solicitudes por estado y vencidas ordenadas por atraso (REQ-LIMS-12, 13)', async ({ page }) => {
        await page.goto(`${DASHBOARD}?periodo=mes`);

        await expect(page.locator('[data-segmento]').first()).toBeVisible();
        const vencidas = page.locator('[data-vencida]');
        const cantidad = await vencidas.count();
        expect(cantidad).toBeGreaterThan(0);
        expect(cantidad).toBeLessThanOrEqual(5);
        const dias = await vencidas.evaluateAll((filas) => filas.map(
            (f) => Number(f.querySelector('span').textContent.match(/\d+/)[0]),
        ));
        expect(dias).toEqual([...dias].sort((a, b) => b - a));
        await expect(vencidas.first()).toHaveAttribute('data-vencida', 'SOL-E2E-V06');
        await expect(vencidas.first().locator('a')).toHaveAttribute('href', /\/proyectos\/solicitudes\/\?q=SOL-E2E-V06$/);
    });

    test('proyectos por etapa con barras proporcionales (REQ-LIMS-16)', async ({ page }) => {
        await page.goto(`${DASHBOARD}?periodo=mes`);

        await expect(page.locator('[data-etapa]')).toHaveCount(6);
        esperarProporcional(await proporciones(page, '[data-etapa]'));
    });

    test('cambiar el periodo recalcula el dashboard (REQ-LIMS-17)', async ({ page }) => {
        await page.goto(DASHBOARD);
        await expect(page.getByRole('link', { name: 'Últimos 6 meses' })).toHaveAttribute('aria-current', 'true');

        await page.getByRole('link', { name: '12 meses' }).click();

        await expect(page).toHaveURL(/periodo=12m/);
        await expect(page.getByRole('link', { name: '12 meses' })).toHaveAttribute('aria-current', 'true');
        const texto12 = await page.locator('[data-periodo-texto]').textContent();

        await page.locator('#dash-desde').fill('2001-03-01');
        await page.locator('#dash-hasta').fill('2001-03-31');
        await page.getByRole('button', { name: 'Aplicar rango' }).click();

        await expect(page).toHaveURL(/periodo=rango/);
        await expect(page.locator('[data-periodo-texto]')).not.toHaveText(texto12);
        await expect(page.locator('[data-kpi="cotizaciones"] p.text-3xl')).toHaveText('0');
    });

    test('sin datos: mensajes en vez de gráficos y tasa "Sin datos" (REQ-LIMS-10, 11)', async ({ page }) => {
        await page.goto(SIN_DATOS);

        await expect(page.locator('[data-kpi="tasa"]')).toContainText('Sin datos');
        for (const grafico of ['cotizaciones-mes', 'embudo', 'solicitudes', 'proyectos']) {
            await expect(page.locator(`[data-grafico="${grafico}"]`)).toContainText('Sin datos en este periodo');
        }
        await expect(page.locator('canvas#grafico-cotizaciones-mes')).toHaveCount(0);
    });

    test('"Ver como tabla" muestra los datos de cada gráfico (REQ-LIMS-18)', async ({ page }) => {
        await page.goto(`${DASHBOARD}?periodo=mes`);

        const tablas = page.locator('details.dash-tabla');
        expect(await tablas.count()).toBeGreaterThanOrEqual(4);
        const embudo = page.locator('[data-grafico="embudo"] details');
        await expect(embudo.locator('table')).toBeHidden();
        await embudo.getByText('Ver como tabla').click();
        await expect(embudo.locator('table')).toBeVisible();
        await expect(embudo.locator('tbody tr')).toHaveCount(3);
    });

    test('en celular no hay desplazamiento horizontal (REQ-LIMS-20)', async ({ page }) => {
        await page.setViewportSize({ width: 390, height: 844 });
        await page.goto(DASHBOARD);

        await expect(page.locator('[data-kpi="clientes"]')).toBeVisible();
        const desborde = await page.locator('.dash').evaluate((el) => el.scrollWidth - el.clientWidth);
        expect(desborde).toBeLessThanOrEqual(0);
        const ancho = await page.locator('.dash').evaluate((el) => el.getBoundingClientRect().right);
        expect(ancho).toBeLessThanOrEqual(390);
    });
});

test('el técnico sin ensayos.ver_todos solo ve sus vencidas (REQ-LIMS-15)', async ({ page }) => {
    await entrarAlLab(page, USUARIOS.tecnicoAsignado);
    await page.goto(`${DASHBOARD}?periodo=mes`);

    const codigos = await page.locator('[data-vencida]').evaluateAll((f) => f.map((e) => e.dataset.vencida));
    expect(codigos).toEqual(expect.arrayContaining(['SOL-E2E-V03', 'SOL-E2E-V02', 'SOL-E2E-V01']));
    for (const ajena of ['SOL-E2E-V04', 'SOL-E2E-V05', 'SOL-E2E-V06']) {
        expect(codigos).not.toContain(ajena);
    }
});

test('marcar una cotización como enviada y luego como rechazada (REQ-LIMS-22 a 24)', async ({ page }) => {
    await entrarAlLab(page, USUARIOS.coordinador);
    const lista = `${LAB_URL}/servicios/cotizaciones/?q=COT-E2E-MARCAR`;
    await page.goto(lista);
    const fila = page.locator('tr').filter({ hasText: 'COT-E2E-MARCAR' });
    const enviar = fila.getByRole('button', { name: 'Marcar como enviada COT-E2E-MARCAR' });
    const rechazar = fila.getByRole('button', { name: 'Marcar como rechazada COT-E2E-MARCAR' });

    await expect(fila.locator('.status-pill')).toHaveText(/Pendiente/);
    await enviar.click();

    await expect(page.getByText('marcada como enviada al cliente')).toBeVisible();
    await page.goto(lista);
    await expect(fila.locator('.status-pill')).toHaveText(/Enviada/);
    await expect(enviar).toHaveCount(0);

    page.once('dialog', (dialogo) => dialogo.accept());
    await rechazar.click();

    await expect(page.getByText('marcada como rechazada')).toBeVisible();
    await page.goto(lista);
    await expect(fila.locator('.status-pill')).toHaveText(/Rechazada/);
    await expect(enviar).toHaveCount(0);
    await expect(rechazar).toHaveCount(0);
});
