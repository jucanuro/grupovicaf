// Correcciones pedidas por el cliente (2026-11-22): campana de notificaciones,
// «Nueva recepción», actividad interna del calendario sin cliente y menú
// lateral plegable (como el del correo).
const { test, expect } = require('@playwright/test');
const { LAB_URL, USUARIOS } = require('./datos');
const { entrarAlLab, cdnLocal } = require('./ayudas');

test.beforeEach(async ({ context }) => {
    await cdnLocal(context);
});

test('la campana abre la lista de pendientes y cada aviso lleva a su pantalla', async ({ page }) => {
    await entrarAlLab(page, USUARIOS.recepcion);
    await page.goto(`${LAB_URL}/proyectos/recepciones/`);

    const campana = page.locator('#notif-trigger');
    const contador = page.locator('#notif-badge');
    await expect(contador).toBeVisible();
    await expect(contador).toHaveText(/^\d+\+?$/);

    await campana.click();
    const panel = page.locator('#notif-panel');
    await expect(panel).toBeVisible();
    await expect(campana).toHaveAttribute('aria-expanded', 'true');
    const aviso = panel.locator('[data-aviso="cotizaciones_pendientes"]');
    await expect(aviso).toBeVisible();

    // Escape cierra; un nuevo clic vuelve a abrir.
    await page.keyboard.press('Escape');
    await expect(panel).toBeHidden();
    await campana.click();
    await aviso.click();
    await expect(page).toHaveURL(/\/servicios\/cotizaciones\/\?estado=Pendiente$/);
});

test('«Nueva recepción» pide el proyecto y abre el formulario de recepción', async ({ page }) => {
    await entrarAlLab(page, USUARIOS.recepcion);
    await page.goto(`${LAB_URL}/proyectos/recepciones/`);

    await page.getByTestId('nueva-recepcion').click();
    await expect(page).toHaveURL(/\/proyectos\/recepcion\/nueva\/$/);
    await expect(page.getByRole('heading', { name: '¿De qué proyecto son las muestras?' })).toBeVisible();

    await page.getByPlaceholder(/Buscar por código/).fill('P-E2E-01');
    await page.getByRole('button', { name: 'Buscar' }).click();
    const proyecto = page.getByTestId('proyectos-recepcion').getByRole('link').first();
    await expect(proyecto).toContainText('P-E2E-01');
    await proyecto.click();
    await expect(page).toHaveURL(/\/proyectos\/recepcion\/nueva\/\d+\/$/);
});

test('una actividad interna se guarda sin cliente', async ({ page }) => {
    const avisos = [];
    page.on('dialog', async (d) => { avisos.push(d.message()); await d.accept(); });

    await entrarAlLab(page, USUARIOS.recepcion);
    await page.goto(`${LAB_URL}/actividades/calendario/`);

    await page.locator('#btnNuevaActividad').click();
    // Abre con las fechas llenas.
    await expect(page.locator('#fecha_inicio')).not.toHaveValue('');
    await expect(page.locator('#fecha_fin')).not.toHaveValue('');
    await page.locator('#titulo').fill(`Visita de obra E2E ${Date.now()}`);
    // El cliente es opcional (HU-LIMS-21): no hay aviso ni pestaña de cliente.
    await page.locator('#form_calendarios').getByText('Laboratorio E2E').click();

    const respuesta = page.waitForResponse((r) => r.url().includes('/calendario/evento/guardar/'));
    await page.getByRole('button', { name: /Guardar actividad/i }).click();
    expect((await respuesta).status()).toBe(200);
    await expect(page.locator('#modalFormulario')).toBeHidden();
    expect(avisos).toHaveLength(0);
});

test('si falta el título, el formulario lo dice y vuelve al título', async ({ page }) => {
    await entrarAlLab(page, USUARIOS.recepcion);
    await page.goto(`${LAB_URL}/actividades/calendario/`);

    await page.locator('#btnNuevaActividad').click();
    await page.locator('#masOpciones summary').click();
    await page.locator('#descripcion').fill('Sin título');
    await page.getByRole('button', { name: /Guardar actividad/i }).click();
    await expect(page.locator('#form_error')).toContainText('título');
    await expect(page.locator('#titulo')).toBeFocused();
});

test('el menú lateral se pliega, se despliega y lo recuerda al navegar', async ({ page }) => {
    await page.setViewportSize({ width: 1440, height: 900 });
    await entrarAlLab(page, USUARIOS.recepcion);
    await page.goto(`${LAB_URL}/proyectos/recepciones/`);

    const menu = page.locator('#menu-lateral');
    await expect(menu).toBeVisible();
    await expect(menu.getByRole('link', { name: 'Muestras' })).toHaveAttribute('aria-current', 'page');
    await expect(menu.getByText('Muestras', { exact: true })).toBeVisible();
    // Solo lo que su rol permite.
    await expect(menu.getByRole('link', { name: 'Trabajadores' })).toHaveCount(0);

    await page.locator('#menu-lateral-plegar').click();
    await expect(menu).toHaveAttribute('data-plegado', '1');
    await expect(menu.getByText('Muestras', { exact: true })).toBeHidden();
    await expect.poll(async () => (await menu.boundingBox()).width).toBeLessThan(100);

    await menu.getByRole('link', { name: 'Calendario' }).click();
    await expect(page).toHaveURL(/\/actividades\/calendario\/$/);
    await expect(page.locator('#menu-lateral')).toHaveAttribute('data-plegado', '1');

    await page.locator('#menu-lateral-plegar').click();
    await expect(page.locator('#menu-lateral')).toHaveAttribute('data-plegado', '0');

    // Buscar módulo filtra la lista.
    await page.locator('#menu-lateral-buscar').fill('cotiz');
    await expect(menu.getByRole('link', { name: 'Cotizaciones' })).toBeVisible();
    await expect(menu.getByRole('link', { name: 'Muestras' })).toBeHidden();
});

test('en el celular el menú lateral no ocupa la pantalla y sigue el botón de menú', async ({ page }) => {
    await page.setViewportSize({ width: 390, height: 844 });
    await entrarAlLab(page, USUARIOS.recepcion);
    await page.goto(`${LAB_URL}/proyectos/recepciones/`);

    await expect(page.locator('#menu-lateral')).toBeHidden();
    await page.locator('#mobile-menu-btn').click();
    await expect(page.locator('#mobile-menu').getByText('Muestras').first()).toBeInViewport();
});
