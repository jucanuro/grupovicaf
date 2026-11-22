// Formulario de cotización (VCF-LIMS): pasos en forma de "pills" y el detalle
// del paso Servicios en un modal (estado vacío → «Agregar detalle» → modal;
// «Editar» reabre el modal con los datos cargados). La lógica de negocio del
// detalle (addItem / editItem / total) no cambia.
const { test, expect } = require('@playwright/test');
const { LAB_URL, USUARIOS, CLIENTE } = require('./datos');
const { entrarAlLab, cdnLocal } = require('./ayudas');

const SERVICIO = 'Proctor Modificado (E2E)';
const CATEGORIA = 'E2E Mecánica de Suelos';

test.beforeEach(async ({ context }) => {
    await cdnLocal(context);
});

/** Escribe en un buscador TomSelect y elige la opción que contiene `texto`. */
async function elegirEnBuscador(page, selectId, texto) {
    const input = page.locator(`#${selectId}-ts-control`);
    await input.click();
    await input.fill(texto);
    const opcion = page.locator(`#${selectId}-ts-dropdown .option`, { hasText: texto }).first();
    await expect(opcion).toBeVisible();
    await opcion.click();
}

async function abrirFormulario(page) {
    await entrarAlLab(page, USUARIOS.comercial);
    await page.goto(`${LAB_URL}/servicios/cotizaciones/crear/`);
    await expect(page.locator('.cot-tabs')).toBeVisible();
}

/** Desde el paso Servicios vacío: agrega categoría + servicio con el modal y lo guarda. */
async function agregarServicioDesdeModal(page, { cantidad, precio }) {
    await page.locator('#btn-agregar-detalle').click();
    const modal = page.locator('#modalDetalle');
    await expect(modal).toBeVisible();
    await expect(modal.locator('#detalle-modal-modo')).toHaveText('Agregar ítem');

    await elegirEnBuscador(page, 'reg_categoria', CATEGORIA);
    await expect(modal.locator('#detalle-modal-aviso')).toContainText(CATEGORIA.toUpperCase());

    await elegirEnBuscador(page, 'reg_servicio', SERVICIO);
    await modal.locator('#reg_cantidad').fill(String(cantidad));
    await modal.locator('#reg_precio').fill(String(precio));
    await modal.locator('#btn-detalle-agregar').click();
    // La tabla se ve dentro del modal, que sigue abierto.
    await expect(modal.locator('#cotizacion-detalles tr', { hasText: SERVICIO })).toBeVisible();
    await modal.locator('#btn-detalle-guardar').click();
    await expect(modal).toBeHidden();
}

test('los 4 pasos se ven como pills y el activo lleva el degradado (REQ-LIMS-53)', async ({ page }) => {
    await abrirFormulario(page);
    const tabs = page.locator('.cot-tab-btn');
    await expect(tabs).toHaveCount(4);
    await expect(tabs).toHaveText([/Cliente/, /Servicios/, /Condiciones/, /Contenido/]);

    for (const [i, paso] of ['cliente', 'servicios', 'resumen', 'contenido'].entries()) {
        const tab = tabs.nth(i);
        await tab.click();
        await expect(tab).toHaveClass(/active/);
        await expect(tab).toHaveAttribute('aria-selected', 'true');
        await expect(page.locator(`#tab-panel-${paso}`)).toBeVisible();
        await expect(tab.locator('.cot-tab-num')).toHaveText(String(i + 1));

        const estilo = await tab.evaluate((el) => {
            const cs = getComputedStyle(el);
            return { fondo: cs.backgroundImage, radio: parseFloat(cs.borderTopLeftRadius) };
        });
        expect(estilo.fondo).toContain('linear-gradient');
        expect(estilo.radio).toBeGreaterThanOrEqual(20);
        // El color cambia con una transición corta: esperar a que termine.
        await expect.poll(() => tab.evaluate((el) => getComputedStyle(el).color)).toBe('rgb(255, 255, 255)');

        // Los demás pasos: sin degradado.
        const otro = tabs.nth((i + 1) % 4);
        await expect(otro).not.toHaveClass(/active/);
        expect(await otro.evaluate((el) => getComputedStyle(el).backgroundImage)).toBe('none');
    }
});

test('Servicios vacío muestra solo «Agregar detalle» y el modal agrega el ítem (REQ-LIMS-54 a 56, 58, 60)', async ({ page }) => {
    await abrirFormulario(page);
    await page.locator('.cot-tab-btn[data-tab="servicios"]').click();

    // Estado vacío: un botón, sin el panel de selección ni la tabla.
    await expect(page.locator('#detalle-vacio')).toBeVisible();
    await expect(page.locator('#btn-agregar-detalle')).toBeVisible();
    await expect(page.locator('#content-registro')).toBeHidden();
    await expect(page.locator('#detalle-tabla')).toBeHidden();

    // El modal ocupa toda la pantalla: formulario a la izquierda, tabla (vacía) a la derecha.
    await page.locator('#btn-agregar-detalle').click();
    const modal = page.locator('#modalDetalle');
    await expect(modal).toBeVisible();
    const vista = page.viewportSize();
    const caja = await modal.boundingBox();
    expect(caja.width).toBeGreaterThanOrEqual(vista.width - 1);
    expect(caja.height).toBeGreaterThanOrEqual(vista.height - 1);
    const form = await modal.locator('.detalle-modal__form').boundingBox();
    const zonaTabla = await modal.locator('.detalle-modal__tabla').boundingBox();
    expect(form.x).toBeLessThan(zonaTabla.x);
    expect(zonaTabla.width).toBeGreaterThan(form.width * 3);
    await expect(modal.locator('#detalle-modal-vacio')).toBeVisible();

    // Agregar sin servicio avisa dentro del modal y no lo cierra.
    await modal.locator('#btn-detalle-agregar').click();
    await expect(modal.locator('#detalle-modal-error')).toContainText('Selecciona un servicio');
    await expect(modal).toBeVisible();
    await modal.getByRole('button', { name: 'Cerrar ventana' }).click();
    await expect(modal).toBeHidden();

    await agregarServicioDesdeModal(page, { cantidad: 2, precio: 150 });

    const filas = page.locator('#cotizacion-detalles tr');
    await expect(filas).toHaveCount(2); // cabecera de categoría + servicio
    await expect(filas.nth(0)).toContainText(CATEGORIA.toUpperCase());
    await expect(filas.nth(1)).toContainText(SERVICIO);
    await expect(filas.nth(1)).toContainText('S/ 300.00');
    await expect(page.locator('#detalle-vacio')).toBeHidden();
    await expect(page.locator('#btn-agregar-detalle-barra')).toBeVisible();
    // El total del paso Condiciones se sigue calculando igual (300 + 18 % IGV).
    await expect(page.locator('#total_final_cotizacion')).toHaveText('354.00');
});

test('«Editar» reabre el modal con los datos y actualiza el ítem (REQ-LIMS-57, 61)', async ({ page }) => {
    await abrirFormulario(page);
    await page.locator('.cot-tab-btn[data-tab="servicios"]').click();
    await agregarServicioDesdeModal(page, { cantidad: 2, precio: 150 });

    const filaServicio = page.locator('#cotizacion-detalles tr', { hasText: SERVICIO });
    await filaServicio.getByRole('button', { name: 'Editar' }).click();

    const modal = page.locator('#modalDetalle');
    await expect(modal).toBeVisible();
    await expect(modal.locator('#detalle-modal-modo')).toHaveText('Editar ítem');
    await expect(modal.locator('#reg_cantidad')).toHaveValue('2');
    await expect(modal.locator('#reg_precio')).toHaveValue('150');
    await expect(modal.locator('#reg_servicio-ts-control').locator('..')).toContainText(SERVICIO);
    await expect(modal.locator('#cotizacion-detalles tr.editando')).toContainText(SERVICIO);

    await modal.locator('#reg_cantidad').fill('3');
    await expect(modal.locator('#btn-detalle-agregar')).toHaveText(/Actualizar ítem/);
    await modal.locator('#btn-detalle-agregar').click();
    // Se actualiza en la tabla del modal, sin cerrarlo.
    await expect(modal.locator('#cotizacion-detalles tr', { hasText: SERVICIO })).toContainText('S/ 450.00');
    await expect(modal.locator('#detalle-modal-modo')).toHaveText('Agregar ítem');

    // También se edita desde la tabla del propio modal.
    await modal.locator('#cotizacion-detalles tr', { hasText: SERVICIO }).getByRole('button', { name: 'Editar' }).click();
    await expect(modal.locator('#reg_cantidad')).toHaveValue('3');
    await modal.locator('#reg_precio').fill('100');
    await modal.locator('#btn-detalle-agregar').click();
    await expect(modal.locator('#cotizacion-detalles tr', { hasText: SERVICIO })).toContainText('S/ 300.00');

    await modal.locator('#btn-detalle-guardar').click();
    await expect(modal).toBeHidden();
    await expect(page.locator('#tab-panel-servicios #cotizacion-detalles tr')).toHaveCount(2);
    await expect(filaServicio).toContainText('S/ 300.00');

    // Al volver a «Agregar detalle» el modal ya no está en modo edición.
    await page.locator('#btn-agregar-detalle-barra').click();
    await expect(modal.locator('#detalle-modal-modo')).toHaveText('Agregar ítem');
    await expect(modal.locator('#reg_cantidad')).toHaveValue('1');
    // Esc cierra primero la lista del buscador enfocado y luego el modal.
    await page.keyboard.press('Escape');
    await page.keyboard.press('Escape');
    await expect(modal).toBeHidden();
});

test('el asistente completo guarda la cotización y al editarla carga el detalle (REQ-LIMS-53 a 56)', async ({ page }) => {
    await abrirFormulario(page);
    const asunto = `E2E modal detalle ${Date.now()}`;

    // Paso 1: Cliente
    await elegirEnBuscador(page, 'id_cliente_ruc', CLIENTE.ruc);
    await page.locator('#id_asunto_servicio').fill(asunto);
    await page.getByRole('button', { name: /Continuar a servicios/ }).click();

    // Paso 2: Servicios
    await expect(page.locator('#tab-panel-servicios')).toBeVisible();
    // «Guardar detalle» con un servicio elegido y sin agregar: se agrega solo.
    await page.locator('#btn-agregar-detalle').click();
    await elegirEnBuscador(page, 'reg_servicio', SERVICIO);
    await page.locator('#reg_precio').fill('200');
    await page.locator('#btn-detalle-guardar').click();
    await expect(page.locator('#modalDetalle')).toBeHidden();
    await page.getByRole('button', { name: /Continuar a condiciones/ }).click();

    // Paso 3: Condiciones
    await expect(page.locator('#tab-panel-resumen')).toBeVisible();
    await expect(page.locator('#total_final_cotizacion')).toHaveText('236.00');
    await page.getByRole('button', { name: /Continuar a contenido/ }).click();

    // Paso 4: Contenido → guardar
    await expect(page.locator('#tab-panel-contenido')).toBeVisible();
    await page.getByRole('button', { name: /Guardar y Generar Oferta/ }).click();
    await expect(page).toHaveURL(/\/servicios\/cotizaciones\/$/);

    // Editar la recién guardada: el detalle aparece en la tabla, sin estado vacío.
    await page.goto(`${LAB_URL}/servicios/cotizaciones/?q=${encodeURIComponent(asunto)}`);
    const fila = page.locator('tr', { hasText: asunto }).first();
    await fila.locator('a[title="Editar"]').click();
    await expect(page).toHaveURL(/\/servicios\/cotizaciones\/editar\/\d+\/$/);
    await page.locator('.cot-tab-btn[data-tab="servicios"]').click();
    await expect(page.locator('#detalle-vacio')).toBeHidden();
    await expect(page.locator('#cotizacion-detalles tr', { hasText: SERVICIO })).toContainText('S/ 200.00');
});

test('en el celular el modal ocupa toda la pantalla (REQ-LIMS-59)', async ({ page }) => {
    await page.setViewportSize({ width: 390, height: 844 });
    await abrirFormulario(page);
    await page.locator('.cot-tab-btn[data-tab="servicios"]').click();
    await page.locator('#btn-agregar-detalle').click();

    const caja = page.locator('#modalDetalle');
    await expect(caja).toBeVisible();
    const box = await caja.boundingBox();
    expect(box.width).toBeGreaterThanOrEqual(389);
    expect(box.height).toBeGreaterThanOrEqual(840);
    // Sin scroll horizontal de la página.
    expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(390);
});
