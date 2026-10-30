const { expect } = require('@playwright/test');
const { LAB_URL, PASSWORD } = require('./datos');

/** Inicia sesión en el LIMS con un usuario sembrado. */
async function entrarAlLab(page, usuario) {
    await page.goto(`${LAB_URL}/`);
    await page.locator('input[name="username"]').fill(usuario);
    await page.locator('input[name="password"]').fill(PASSWORD);
    await page.locator('form button[type="submit"]').click();
    await expect(page).toHaveURL(/\/dashboard\/$/);
}

module.exports = { entrarAlLab };
