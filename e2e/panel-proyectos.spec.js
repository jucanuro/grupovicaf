// Panel de proyectos con avance por muestra (HU-LIMS-19, REQ-LIMS-44 a 51).
// Datos: P-E2E-AVANCE de `sembrar_e2e` (8 previstas → 5 por ingresar,
// 2 recibidas, 1 en ensayo, 0 con informe).
const { test, expect } = require('@playwright/test');
const { LAB_URL, USUARIOS, PROYECTO_AVANCE, SOLICITUD } = require('./datos');
const { entrarAlLab, cdnLocal } = require('./ayudas');

const PANEL = `${LAB_URL}/proyectos/pendientes/?q=${PROYECTO_AVANCE.codigo}`;

test.beforeEach(async ({ context }) => {
    await cdnLocal(context);
});

async function abrirTarjeta(page, usuario = USUARIOS.jefe) {
    await entrarAlLab(page, usuario);
    await page.goto(PANEL);
    const tarjeta = page.locator('article[data-proyecto]', { hasText: PROYECTO_AVANCE.codigo });
    await expect(tarjeta).toHaveCount(1);
    return tarjeta;
}

test('la tarjeta muestra el % de avance y cuántas muestras hay en cada etapa (REQ-LIMS-44, 45)', async ({ page }) => {
    const tarjeta = await abrirTarjeta(page);
    await expect(tarjeta.getByRole('heading', { name: PROYECTO_AVANCE.nombre })).toBeVisible();

    for (const [clave, cantidad] of Object.entries(PROYECTO_AVANCE.etapas)) {
        await expect(tarjeta.locator(`[data-etapa="${clave}"] [data-cantidad]`)).toHaveText(String(cantidad));
    }
    // RN-10: (2 recibidas × 1 + 1 en ensayo × 2) / (8 × 3) = 17 %
    await expect(tarjeta.locator('[data-porcentaje]')).toHaveText(/^17\s*%$/);
    await expect(tarjeta.getByRole('progressbar')).toHaveAttribute('aria-valuenow', '17');
    await expect(tarjeta.locator('[data-accion]')).toHaveText(/Registrar 5 muestras/);
});

test('cada número abre su pantalla filtrada al proyecto (REQ-LIMS-46)', async ({ page }) => {
    const tarjeta = await abrirTarjeta(page);
    const id = await tarjeta.getAttribute('data-proyecto');

    // Por ingresar → formulario de recepción del proyecto.
    await tarjeta.locator('[data-etapa="por_ingresar"]').click();
    await expect(page).toHaveURL(new RegExp(`/proyectos/recepcion/nueva/${id}/$`));
    await expect(page.locator('body')).toContainText('Recepción');

    // Recibidas → recepciones del proyecto.
    await page.goto(PANEL);
    await tarjeta.locator('[data-etapa="recibida"]').click();
    await expect(page).toHaveURL(new RegExp(`/proyectos/recepciones/\\?proyecto=${id}$`));
    await expect(page.locator(`[data-filtro-proyecto="${id}"]`)).toContainText(PROYECTO_AVANCE.codigo);

    // En ensayo → solicitudes del proyecto, sin las de otros proyectos.
    await page.goto(PANEL);
    await tarjeta.locator('[data-etapa="en_ensayo"]').click();
    await expect(page).toHaveURL(new RegExp(`/proyectos/solicitudes/\\?proyecto=${id}$`));
    await expect(page.locator(`[data-filtro-proyecto="${id}"]`)).toBeVisible();
    const lista = page.locator('[data-lista-contenedor]');
    await expect(lista).toContainText(PROYECTO_AVANCE.solicitud);
    await expect(lista).not.toContainText(SOLICITUD);

    // «Ver todos» quita el filtro.
    await page.locator('[data-quitar-filtro]').click();
    await expect(page).toHaveURL(/\/proyectos\/solicitudes\/$/);
    await expect(page.locator('[data-lista-contenedor]')).toContainText(SOLICITUD);

    // Con informe → informes del proyecto (todavía ninguno).
    await page.goto(PANEL);
    await tarjeta.locator('[data-etapa="informe"]').click();
    await expect(page).toHaveURL(new RegExp(`/proyectos/informes/\\?proyecto=${id}$`));
    await expect(page.locator(`[data-filtro-proyecto="${id}"]`)).toBeVisible();
});

test('el botón grande lleva a la acción más urgente (REQ-LIMS-47)', async ({ page }) => {
    const tarjeta = await abrirTarjeta(page);
    const id = await tarjeta.getAttribute('data-proyecto');
    await tarjeta.locator('a[data-accion="registrar"]').click();
    await expect(page).toHaveURL(new RegExp(`/proyectos/recepcion/nueva/${id}/$`));
});

test('sin permiso, la etapa no es un enlace (REQ-LIMS-51)', async ({ page }) => {
    // e2e.recepcion ve proyectos y muestras, pero no ensayos ni informes.
    const tarjeta = await abrirTarjeta(page, USUARIOS.recepcion);
    await expect(tarjeta.locator('a[data-etapa="recibida"]')).toHaveCount(1);
    await expect(tarjeta.locator('a[data-etapa="en_ensayo"]')).toHaveCount(0);
    await expect(tarjeta.locator('span[data-etapa="en_ensayo"]')).toHaveText(/1/);
    await expect(tarjeta.locator('a[data-etapa="informe"]')).toHaveCount(0);
});

test('en el celular la tarjeta entra completa, sin scroll horizontal', async ({ page }) => {
    await page.setViewportSize({ width: 390, height: 844 });
    const tarjeta = await abrirTarjeta(page);
    await expect(tarjeta.locator('[data-etapa="informe"]')).toBeInViewport();
    const desborde = await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth);
    expect(desborde).toBeLessThanOrEqual(1);
    await expect(tarjeta.locator('[data-accion]')).toBeVisible();
});
