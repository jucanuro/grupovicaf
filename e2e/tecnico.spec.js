// L3: el técnico ve solo sus ensayos y el código confidencial en vez del cliente.
const { test, expect } = require('@playwright/test');
const { LAB_URL, USUARIOS, SOLICITUD, CLIENTE } = require('./datos');
const { entrarAlLab } = require('./ayudas');

const LISTA = `${LAB_URL}/proyectos/solicitudes/`;

test('el técnico asignado ve su solicitud con el código confidencial y sin razón social', async ({ page }) => {
    await entrarAlLab(page, USUARIOS.tecnicoAsignado);
    await page.goto(LISTA);

    await expect(page.getByText(SOLICITUD).first()).toBeVisible();
    await expect(page.getByText(/CLI-\d{2}-\d{4}/).first()).toBeVisible();
    expect(await page.content()).not.toContain(CLIENTE.razonSocial);
});

test('otro técnico no ve la solicitud ni puede bajar su PDF', async ({ browser }) => {
    const asignado = await browser.newPage();
    await entrarAlLab(asignado, USUARIOS.tecnicoAsignado);
    await asignado.goto(LISTA);
    const urlPdf = await asignado.locator('a[href*="/proyectos/ensayo/"][href$="/pdf/"]').first().getAttribute('href');
    await asignado.close();

    const ajeno = await browser.newPage();
    await entrarAlLab(ajeno, USUARIOS.tecnicoAjeno);
    await ajeno.goto(LISTA);
    expect(await ajeno.content()).not.toContain(SOLICITUD);

    const respuesta = await ajeno.request.get(new URL(urlPdf, LAB_URL).href);
    expect(respuesta.status()).toBe(403);
    await ajeno.close();
});

test('el coordinador (ensayos.ver_todos) ve la razón social', async ({ page }) => {
    await entrarAlLab(page, USUARIOS.coordinador);
    await page.goto(LISTA);

    await expect(page.getByText(SOLICITUD).first()).toBeVisible();
    expect(await page.content()).toContain(CLIENTE.razonSocial);
});
