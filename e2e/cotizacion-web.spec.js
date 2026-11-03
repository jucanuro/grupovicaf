// Cotización desde la web pública → bandeja "Solicitudes web" del laboratorio.
const { test, expect } = require('@playwright/test');
const { WEB_URL, LAB_URL, USUARIOS, ENSAYO_WEB } = require('./datos');
const { entrarAlLab } = require('./ayudas');

test('la solicitud enviada desde /contacto/ llega a la bandeja del laboratorio', async ({ browser }) => {
    // Razón social única por corrida: la base local puede guardar corridas anteriores.
    const razonSocial = `Obra E2E ${Date.now()} SAC`;

    const visitante = await browser.newPage();
    await visitante.goto(`${WEB_URL}/contacto/`);
    await visitante.locator('#id_ruc').fill('20999999992');
    await visitante.locator('#id_razon_social').fill(razonSocial);
    await visitante.locator('#id_persona_contacto').fill('Luis Prueba');
    await visitante.locator('#id_correo_contacto').fill('luis@e2e.invalid');
    await visitante.locator('#id_telefono_contacto').fill('999999992');
    await visitante.locator(`#id_servicio_${ENSAYO_WEB.slug}`).check();
    await visitante.locator(`input[name="cantidad_${ENSAYO_WEB.slug}"]`).fill('3');
    await visitante.locator('#id_necesidad').fill('Proctor para la sub-base de un pavimento en Baños del Inca.');
    await visitante.locator('#id_necesidad').locator('xpath=ancestor::form').locator('button[type="submit"]').click();

    await expect(visitante.getByText('recibimos tu solicitud de cotización')).toBeVisible();
    await visitante.close();

    const laboratorio = await browser.newPage();
    await entrarAlLab(laboratorio, USUARIOS.coordinador);
    await laboratorio.goto(`${LAB_URL}/servicios/cotizaciones/solicitudes-web/`);

    await expect(laboratorio.getByText(razonSocial).first()).toBeVisible();
    await expect(laboratorio.getByText(ENSAYO_WEB.titulo).first()).toBeVisible();
    await laboratorio.close();
});

test('la bandeja de solicitudes web exige iniciar sesión', async ({ page }) => {
    await page.goto(`${LAB_URL}/servicios/cotizaciones/solicitudes-web/`);
    await expect(page).toHaveURL(/\/\?next=/);
});
