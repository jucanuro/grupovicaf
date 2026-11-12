// VCF-LIMS · Módulo de correo, Paso 1: pantalla de entrada tras el login,
// cada tarjeta en pestaña nueva y salto firmado a email.localhost.
const { test, expect } = require('@playwright/test');
const { iniciarSesion } = require('./ayudas');
const { LAB_URL, USUARIOS } = require('./datos');

// Chromium resuelve *.localhost a 127.0.0.1: el mismo runserver del lab
// responde como host del correo (CORREO_HOST=email.localhost por defecto).
const HOST_CORREO = 'email.localhost';

test.describe('pantalla de entrada', () => {
    test('el coordinador ve Correos y Sistema, ambas en pestaña nueva', async ({ page }) => {
        await iniciarSesion(page, USUARIOS.coordinador);

        const correos = page.locator('[data-tarjeta="correos"]');
        const sistema = page.locator('[data-tarjeta="sistema"]');
        await expect(correos).toBeVisible();
        await expect(sistema).toBeVisible();
        await expect(correos.locator('[data-cuenta]')).toHaveCount(3);

        for (const enlace of await page.locator('[data-tarjeta] a').all()) {
            await expect(enlace).toHaveAttribute('target', '_blank');
            await expect(enlace).toHaveAttribute('rel', /noopener/);
        }
    });

    test('Entrar al sistema abre el dashboard en otra pestaña', async ({ page, context }) => {
        await iniciarSesion(page, USUARIOS.coordinador);
        const [pestana] = await Promise.all([
            context.waitForEvent('page'),
            page.getByRole('link', { name: /Entrar al sistema/ }).click(),
        ]);
        await expect(pestana).toHaveURL(`${LAB_URL}/dashboard/`);
        await expect(page).toHaveURL(/\/inicio\/$/);
    });

    test('cada cuenta abre su bandeja en el host del correo, sin segundo login', async ({ page, context }) => {
        await iniciarSesion(page, USUARIOS.coordinador);
        const [pestana] = await Promise.all([
            context.waitForEvent('page'),
            page.getByRole('link', { name: 'Abrir informes@grupovicaf.com en una pestaña nueva' }).click(),
        ]);
        await expect(pestana).toHaveURL(new RegExp(`^http://${HOST_CORREO}:\\d+/c/informes/bandeja/$`));
        await expect(pestana.getByRole('heading', { name: 'Bandeja de entrada' })).toBeVisible();
        await expect(pestana.locator('.lista__sub')).toContainText('informes@grupovicaf.com');
    });

    test('el técnico sin correo.ver solo ve Sistema', async ({ page }) => {
        await iniciarSesion(page, USUARIOS.tecnicoAsignado);
        await expect(page.locator('[data-tarjeta="sistema"]')).toBeVisible();
        await expect(page.locator('[data-tarjeta="correos"]')).toHaveCount(0);
    });
});
