const { expect } = require('@playwright/test');
const { LAB_URL, PASSWORD } = require('./datos');

/** Inicia sesión y se queda en la pantalla de entrada (tarjetas Correos / Sistema). */
async function iniciarSesion(page, usuario) {
    await page.goto(`${LAB_URL}/`);
    await page.locator('input[name="username"]').fill(usuario);
    await page.locator('input[name="password"]').fill(PASSWORD);
    await page.locator('form button[type="submit"]').click();
    await expect(page).toHaveURL(/\/inicio\/$/);
}

/** Inicia sesión en el LIMS con un usuario sembrado y entra al dashboard. */
async function entrarAlLab(page, usuario) {
    await iniciarSesion(page, usuario);
    await page.goto(`${LAB_URL}/dashboard/`);
    await expect(page).toHaveURL(/\/dashboard\/$/);
}

module.exports = { entrarAlLab, iniciarSesion };
