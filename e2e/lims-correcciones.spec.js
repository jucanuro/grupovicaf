// Correcciones pedidas por el cliente (2026-11-22): campana de notificaciones,
// «Nueva recepción», guardar actividad del calendario tras el aviso de datos
// faltantes y menú lateral plegable (como el del correo).
const { test, expect } = require('@playwright/test');
const { LAB_URL, USUARIOS, CLIENTE } = require('./datos');
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

test('la actividad se guarda después del aviso de cliente faltante', async ({ page }) => {
    const avisos = [];
    page.on('dialog', async (d) => { avisos.push(d.message()); await d.accept(); });

    await entrarAlLab(page, USUARIOS.recepcion);
    await page.goto(`${LAB_URL}/actividades/calendario/`);

    await page.locator('#btnNuevaActividad').click();
    // Ya no abre con las fechas vacías.
    await expect(page.locator('#fecha_inicio')).not.toHaveValue('');
    await expect(page.locator('#fecha_fin')).not.toHaveValue('');
    const titulo = `Visita de obra E2E ${Date.now()}`;
    await page.locator('#titulo').fill(titulo);

    const guardar = page.getByRole('button', { name: /Guardar actividad/i });
    await guardar.click();
    await expect.poll(() => avisos.length).toBe(1);
    expect(avisos[0]).toContain('cliente');
    // El aviso lleva a la pestaña del cliente; se completa y se reintenta.
    // (Sin ensayos.ver_todos la lista de clientes viene vacía: se usa el campo manual.)
    await expect(page.locator('#cliente_nombre_manual')).toBeVisible();
    await page.locator('#cliente_nombre_manual').fill(CLIENTE.razonSocial);

    const respuesta = page.waitForResponse((r) => r.url().includes('/calendario/evento/guardar/'));
    await guardar.click();
    expect((await respuesta).status()).toBe(200);
    await expect(page.locator('#modalFormulario')).toBeHidden();
    expect(avisos).toHaveLength(1);
});

test('si falta el título estando en otra pestaña, vuelve a «General» y no se pierde el clic', async ({ page }) => {
    await entrarAlLab(page, USUARIOS.recepcion);
    await page.goto(`${LAB_URL}/actividades/calendario/`);

    await page.locator('#btnNuevaActividad').click();
    await page.locator('[data-actividad-tab="config"]').click();
    await page.getByRole('button', { name: /Guardar actividad/i }).click();
    await expect(page.locator('#titulo')).toBeVisible();
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
