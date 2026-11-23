// Modo claro / oscuro del LIMS y del correo (pedido del cliente, 2026-11-23).
// static/js/tema.js marca <html class="dark">; el CSS de cada pantalla
// (tema_oscuro*.css y correo.css) cambia los colores.
const { test, expect } = require('@playwright/test');
const { LAB_URL, USUARIOS } = require('./datos');
const { entrarAlLab, iniciarSesion, cdnLocal } = require('./ayudas');

test.beforeEach(async ({ context }) => {
    await cdnLocal(context);
});

/** Color de fondo del <body> como [r, g, b]. */
async function fondoBody(page) {
    const rgb = await page.evaluate(() => getComputedStyle(document.body).backgroundColor);
    return rgb.match(/\d+/g).slice(0, 3).map(Number);
}
const oscuro = ([r, g, b]) => (r + g + b) / 3 < 60;

test.describe('LIMS', () => {
    test.use({ colorScheme: 'light' });

    test('el botón cambia a modo oscuro, se recuerda al recargar y vuelve a claro', async ({ page }) => {
        await entrarAlLab(page, USUARIOS.coordinador);
        const html = page.locator('html');
        const boton = page.locator('#tema-alternar');

        await expect(html).not.toHaveClass(/\bdark\b/);
        await expect(boton).toHaveAttribute('aria-pressed', 'false');
        await expect(boton).toHaveAttribute('aria-label', 'Cambiar a modo oscuro');
        expect(oscuro(await fondoBody(page))).toBe(false);

        await boton.click();
        await expect(html).toHaveClass(/\bdark\b/);
        await expect(boton).toHaveAttribute('aria-pressed', 'true');
        await expect(boton).toHaveAttribute('aria-label', 'Cambiar a modo claro');
        expect(oscuro(await fondoBody(page))).toBe(true);
        // Las tarjetas del dashboard también se oscurecen.
        const tarjeta = await page.locator('.dash-card').first()
            .evaluate((n) => getComputedStyle(n).backgroundColor);
        expect(tarjeta).not.toBe('rgb(255, 255, 255)');

        // Otra pantalla y recarga: sigue en oscuro.
        await page.goto(`${LAB_URL}/proyectos/solicitudes/`);
        await expect(html).toHaveClass(/\bdark\b/);
        await page.reload();
        await expect(html).toHaveClass(/\bdark\b/);

        await page.locator('#tema-alternar').click();
        await expect(html).not.toHaveClass(/\bdark\b/);
        await page.reload();
        await expect(html).not.toHaveClass(/\bdark\b/);
    });
});

test.describe('sin preferencia guardada', () => {
    test.use({ colorScheme: 'dark' });

    test('sigue el modo oscuro del sistema', async ({ page }) => {
        await entrarAlLab(page, USUARIOS.coordinador);
        await expect(page.locator('html')).toHaveClass(/\bdark\b/);
        await expect(page.locator('#tema-alternar')).toHaveAttribute('aria-pressed', 'true');
    });
});

test.describe('correo', () => {
    test.use({ colorScheme: 'light' });

    test('la portada y el correo tienen su botón y funcionan con la CSP del correo', async ({ page }) => {
        const violaciones = [];
        page.on('console', (m) => {
            if (m.type() === 'error' && /Content Security Policy/.test(m.text())) violaciones.push(m.text());
        });

        // Portada de inicio (laboratorio.): botón con texto.
        await iniciarSesion(page, USUARIOS.coordinador);
        const portada = page.locator('[data-tema-alternar]');
        await expect(portada).toContainText('Modo oscuro');
        await portada.click();
        await expect(page.locator('html')).toHaveClass(/\bdark\b/);
        await expect(portada).toContainText('Modo claro');

        // Correo (email.): su propio botón en la barra.
        await page.goto(`${LAB_URL}/correo/abrir/`);
        await expect(page).toHaveURL(/email\.localhost/);
        const boton = page.locator('.barra--app [data-tema-alternar]');
        await expect(boton).toBeVisible();
        if (!(await page.locator('html').evaluate((n) => n.classList.contains('dark')))) {
            await boton.click();
        }
        await expect(page.locator('html')).toHaveClass(/\bdark\b/);
        expect(oscuro(await fondoBody(page))).toBe(true);
        await page.reload();
        await expect(page.locator('html')).toHaveClass(/\bdark\b/);

        await boton.click();
        await expect(page.locator('html')).not.toHaveClass(/\bdark\b/);
        expect(oscuro(await fondoBody(page))).toBe(false);
        expect(violaciones).toEqual([]);
    });
});
