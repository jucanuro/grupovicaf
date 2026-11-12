// VCF-LIMS · Módulo de correo, Paso 2: plataforma tipo Outlook con los datos
// de `seed_correo_demo --usuario e2e.coordinador` (playwright.config.js).
const { test, expect } = require('@playwright/test');
const { iniciarSesion } = require('./ayudas');
const { LAB_URL, USUARIOS } = require('./datos');

/** Entra al correo con el enlace firmado y devuelve la página ya en email.localhost. */
async function abrirCorreo(page, cuenta) {
    await iniciarSesion(page, USUARIOS.coordinador);
    await page.goto(`${LAB_URL}/correo/abrir/${cuenta ? `?cuenta=${cuenta}` : ''}`);
    await expect(page).toHaveURL(/email\.localhost/);
    return new URL(page.url()).origin;
}

/** Falla la prueba si la CSP del host bloquea algo propio (scripts o estilos). */
function vigilarCsp(page) {
    const violaciones = [];
    page.on('console', (m) => {
        if (m.type() === 'error' && /Content Security Policy/.test(m.text())) { violaciones.push(m.text()); }
    });
    return violaciones;
}

test.describe('plataforma de correo', () => {
    test('tres paneles: carpetas, lista y lectura con el cuerpo aislado', async ({ page }) => {
        const violaciones = vigilarCsp(page);
        await abrirCorreo(page);
        await expect(page.getByRole('heading', { name: 'Bandeja unificada' })).toBeVisible();
        await expect(page.locator('.grupo-cuenta')).toHaveCount(3);

        await page.locator('.fila__enlace', { hasText: 'Solicitud de cotización' }).first().click();
        await expect(page.locator('.hilo__asunto')).toContainText('Solicitud de cotización');
        await expect(page.locator('.mensaje')).not.toHaveCount(0);
        await expect(page.getByRole('heading', { name: 'Participantes' })).toBeVisible();

        const cuerpo = page.locator('iframe[data-cuerpo]').last();
        await expect(cuerpo).toHaveAttribute('sandbox', /allow-same-origin/);
        await expect(cuerpo).not.toHaveAttribute('sandbox', /allow-scripts/);
        expect(violaciones).toEqual([]);
    });

    test('teclado: flechas recorren la lista y Enter abre', async ({ page }) => {
        await abrirCorreo(page, 'informes');
        const primera = page.locator('.fila__enlace').first();
        await primera.focus();
        await page.keyboard.press('ArrowDown');
        await expect(page.locator('.fila__enlace').nth(1)).toBeFocused();
        await page.keyboard.press('Enter');
        await expect(page).toHaveURL(/[?&]h=\d+/);
        await expect(page.locator('.fila--activa')).toHaveCount(1);
    });

    test('el boletín llega sin scripts y con imágenes remotas bloqueadas', async ({ page }) => {
        await abrirCorreo(page, 'informes');
        await page.locator('.fila__enlace', { hasText: 'Boletín técnico' }).click();
        await expect(page.getByRole('link', { name: 'Mostrar imágenes' })).toBeVisible();
        const marco = page.frameLocator('iframe[data-cuerpo]').last();
        await expect(marco.locator('h1, h2, p').first()).toBeVisible();
        await expect(marco.locator('script')).toHaveCount(0);
        await expect(marco.locator('img[src^="https://"]')).toHaveCount(0);
    });

    test('responder: borrador con firma, adjunto y envío a Enviados', async ({ page }) => {
        const violaciones = vigilarCsp(page);
        page.on('dialog', (d) => d.accept());
        await abrirCorreo(page, 'informes');
        await page.locator('.fila__enlace', { hasText: 'Solicitud de cotización' }).first().click();
        await page.locator('.mensaje--ultimo').getByRole('link', { name: 'Responder', exact: true }).click();

        await expect(page).toHaveURL(/\/redactar\/\d+\/$/);
        await expect(page.locator('#r-asunto')).toHaveValue(/^RE: /);
        await expect(page.locator('.ql-editor')).toContainText('Área de Informes');  // firma de la cuenta
        await page.locator('.ql-editor').click();
        await page.keyboard.press('Control+Home');
        await page.keyboard.type('Gracias, Ana. Adjuntamos lo solicitado.');

        await page.setInputFiles('[data-subir]', { name: 'nota.txt', mimeType: 'text/plain', buffer: Buffer.from('hola') });
        await expect(page.locator('[data-lista-adjuntos] li')).toHaveCount(1);

        await page.getByRole('button', { name: 'Enviar' }).click();
        await expect(page.locator('.avisos')).toContainText('Bandeja de salida');

        await page.locator('.grupo-cuenta[data-cuenta="informes"]').getByRole('link', { name: 'Enviados' }).click();
        await expect(page.locator('.fila__asunto', { hasText: 'RE: Solicitud de cotización' }).first()).toBeVisible();
        expect(violaciones).toEqual([]);
    });

    test('la Bandeja de salida muestra el envío fallido y permite reintentar', async ({ page }) => {
        await abrirCorreo(page, 'informes');
        await page.locator('.grupo-cuenta[data-cuenta="informes"]').getByRole('link', { name: /Bandeja de salida/ }).click();
        await expect(page.locator('.chip--rojo', { hasText: 'Falló el envío' }).first()).toBeVisible();
        await page.locator('.fila__enlace').first().click();
        await expect(page.getByRole('button', { name: 'Reintentar' })).toBeVisible();
    });

    test('búsqueda sin tildes y ficha del contacto con su cliente del LIMS', async ({ page }) => {
        const origen = await abrirCorreo(page);
        await page.locator('#q-rapida').fill('compresion');
        await page.locator('#q-rapida').press('Enter');
        await expect(page.locator('.tabla tbody tr').first()).toContainText(/compresi[oó]n/i);

        await page.goto(`${origen}/contacto/?correo=ana@e2e.invalid`);
        await expect(page.getByText('Constructora E2E SAC').first()).toBeVisible();
        await expect(page.getByRole('heading', { name: /Historial/ })).toBeVisible();
    });

    test('firmas: crear una personal con el editor', async ({ page }) => {
        const violaciones = vigilarCsp(page);
        const origen = await abrirCorreo(page);
        await page.goto(`${origen}/firmas/nueva/`);
        const nombre = `Firma E2E ${Date.now()}`;  // la base de e2e no se vacía entre corridas
        await page.locator('#f-nombre').fill(nombre);
        await page.locator('.ql-editor').click();
        await page.keyboard.type('Coordinación · GRUPO VICAF');
        await page.getByRole('button', { name: 'Guardar firma' }).click();
        await expect(page).toHaveURL(/\/firmas\/$/);
        await expect(page.getByRole('heading', { name: nombre })).toBeVisible();
        expect(violaciones).toEqual([]);
    });
});
