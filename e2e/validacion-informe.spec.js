// Página pública a la que apunta el QR del informe final (/proyectos/v/<uuid>/).
const { test, expect } = require('@playwright/test');
const { LAB_URL, SLUG_INFORME, SOLICITUD, CLIENTE } = require('./datos');

test('el QR muestra el informe sin datos confidenciales y con noindex', async ({ page }) => {
    const respuesta = await page.goto(`${LAB_URL}/proyectos/v/${SLUG_INFORME}/`);
    expect(respuesta.status()).toBe(200);

    await expect(page.getByText(/INF-\d{4}-\d{4}/).first()).toBeVisible();
    await expect(page.getByText(SOLICITUD).first()).toBeVisible();
    await expect(page.getByText(CLIENTE.razonSocial).first()).toBeVisible();
    await expect(page.locator('meta[name="robots"]')).toHaveAttribute('content', /noindex/);

    // CLAUDE.md, regla 3: ni RUC, ni código confidencial, ni el PDF.
    const html = await page.content();
    expect(html).not.toContain(CLIENTE.ruc);
    expect(html).not.toMatch(/CLI-\d{2}-\d{4}/);
    expect(html).not.toContain('informe-e2e');
});

test('un código de validación que no existe responde 404', async ({ page }) => {
    const respuesta = await page.goto(`${LAB_URL}/proyectos/v/00000000-0000-4000-8000-000000000000/`);
    expect(respuesta.status()).toBe(404);
});
