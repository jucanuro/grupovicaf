// Web pública en el celular y aviso de bienvenida (specs/WEB v8, REQ-WEB-74 a 77).
const { test, expect } = require('@playwright/test');
const { WEB_URL } = require('./datos');

const CLAVE = 'vicaf_bienvenida_vista';
const CELULAR = { width: 390, height: 844 };

function yaVisto(page) {
    return page.addInitScript((clave) => window.localStorage.setItem(clave, '1'), CLAVE);
}

test.describe('celular', () => {
    test.use({ viewport: CELULAR, isMobile: true, hasTouch: true });

    test('REQ-WEB-74: Sistema Interno en el hero y en el menú', async ({ page }) => {
        await yaVisto(page);
        await page.goto(`${WEB_URL}/`);
        const enHero = page.locator('#home [data-sistema-interno]');
        await expect(enHero).toBeVisible();
        await expect(enHero).toHaveAttribute('href', 'https://laboratorio.grupovicaf.com/');

        await page.locator('#menu-toggle').click();
        const enMenu = page.locator('#mobile-menu [data-sistema-interno]');
        await expect(enMenu).toBeVisible();
        await expect(enMenu).toHaveAttribute('target', '_blank');
    });

    test('REQ-WEB-75: el panel del hero queda abajo y deja ver la foto', async ({ page }) => {
        await yaVisto(page);
        await page.goto(`${WEB_URL}/`);
        const panel = await page.locator('[data-hero-panel]').boundingBox();
        const hero = await page.locator('#home').boundingBox();
        // Pegado al borde inferior del hero y sin cubrir su mitad superior.
        expect(Math.abs((panel.y + panel.height) - (hero.y + hero.height))).toBeLessThan(2);
        expect(panel.y).toBeGreaterThan(hero.y + hero.height / 2 - 120);
        // Ni el botón Sistema Interno ni el panel se solapan.
        const boton = await page.locator('#home [data-sistema-interno]').boundingBox();
        expect(boton.y + boton.height).toBeLessThan(panel.y + 96);
    });
});

test.describe('escritorio', () => {
    test('REQ-WEB-74/75: Sistema Interno y panel del hero como antes', async ({ page }) => {
        await yaVisto(page);
        await page.goto(`${WEB_URL}/`);
        await expect(page.locator('#home [data-sistema-interno]')).toBeVisible();
        await expect(page.locator('#mobile-menu')).toBeHidden();
        const panel = await page.locator('[data-hero-panel]').boundingBox();
        expect(panel.y).toBeLessThan(200);
    });
});

test.describe('aviso de bienvenida', () => {
    test('REQ-WEB-76: sale la primera vez con los sellos y se va solo a los 3 s', async ({ page }) => {
        await page.goto(`${WEB_URL}/`);
        const aviso = page.locator('[data-bienvenida]');
        await expect(aviso).toBeVisible();
        // Las dos primeras certificaciones publicadas (en prod INACAL e ISO;
        // la semilla de pruebas solo publica INACAL, que trae su archivo).
        const sellos = await aviso.locator('[data-bienvenida-sello]').count();
        expect(sellos).toBeGreaterThanOrEqual(1);
        expect(sellos).toBeLessThanOrEqual(2);
        await expect(aviso).toContainText('INACAL LE-230');
        await expect(aviso.getByRole('link', { name: /Acreditación/ })).toHaveAttribute('href', '#acreditacion');
        await expect(page.locator('section#acreditacion')).toHaveCount(1);

        await page.waitForTimeout(2000);
        await expect(aviso).toBeVisible();
        await expect(aviso).toBeHidden({ timeout: 2500 });
    });

    test('REQ-WEB-76: no vuelve a salir en la siguiente visita', async ({ page }) => {
        await page.goto(`${WEB_URL}/`);
        await expect(page.locator('[data-bienvenida]')).toBeVisible();
        await page.reload();
        await page.waitForTimeout(500);
        await expect(page.locator('[data-bienvenida]')).toBeHidden();
    });

    test('REQ-WEB-77: se cierra con la X y con el enlace a Acreditación', async ({ page }) => {
        await page.goto(`${WEB_URL}/`);
        const aviso = page.locator('[data-bienvenida]');
        await aviso.getByRole('button', { name: 'Cerrar aviso' }).click();
        await expect(aviso).toBeHidden();

        await page.evaluate((clave) => window.localStorage.removeItem(clave), CLAVE);
        await page.reload();
        await aviso.getByRole('link', { name: /Acreditación/ }).click();
        await expect(aviso).toBeHidden();
        await expect(page).toHaveURL(/#acreditacion$/);
    });
});
