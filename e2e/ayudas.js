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

/**
 * Solo en máquinas sin salida a los CDN (p. ej. un sandbox): con
 * E2E_CDN_DIR=<carpeta con node_modules de lucide, fullcalendar, tom-select y
 * @tailwindcss/browser> sirve esas librerías desde disco. En el CI no hace nada.
 */
async function cdnLocal(context) {
    const dir = process.env.E2E_CDN_DIR;
    if (!dir) return;
    const fs = require('fs');
    const path = require('path');
    const mapa = [
        [/cdn\.tailwindcss\.com/, '@tailwindcss/browser/dist/index.global.js', 'application/javascript', ';window.tailwind=window.tailwind||{};'],
        [/unpkg\.com\/lucide/, 'lucide/dist/umd/lucide.min.js', 'application/javascript'],
        [/fullcalendar@[^/]+\/index\.global\.min\.js/, 'fullcalendar/index.global.min.js', 'application/javascript'],
        [/tom-select@[^/]+\/dist\/js\/tom-select\.complete\.min\.js/, 'tom-select/dist/js/tom-select.complete.min.js', 'application/javascript'],
        [/tom-select@[^/]+\/dist\/css\/tom-select\.css/, 'tom-select/dist/css/tom-select.css', 'text/css'],
    ];
    await context.route(/^https:\/\//, (route) => {
        const url = route.request().url();
        for (const [re, archivo, tipo, extra] of mapa) {
            if (re.test(url)) {
                const cuerpo = fs.readFileSync(path.join(dir, 'node_modules', archivo), 'utf8') + (extra || '');
                return route.fulfill({ body: cuerpo, contentType: tipo });
            }
        }
        return route.abort();
    });
}

module.exports.cdnLocal = cdnLocal;
