// Asistente de WhatsApp de la web (specs/WEB, REQ-WEB-04 a 18).
//
// "abierto" depende de la hora real de Lima. Para que la prueba no cambie
// según cuándo corra, se intercepta la respuesta REAL del endpoint y solo se
// fija ese campo; el catálogo, el saludo y el número vienen del servidor.
const { test, expect } = require('@playwright/test');
const { WEB_URL, ENSAYO_WEB, WHATSAPP_DIGITOS } = require('./datos');

async function fijarHorario(page, abierto) {
    await page.route('**/contacto/asistente/', async (route) => {
        const respuesta = await route.fetch();
        const datos = await respuesta.json();
        await route.fulfill({ response: respuesta, json: { ...datos, abierto } });
    });
}

async function abrirAsistente(page) {
    await page.goto(`${WEB_URL}/`);
    await page.locator('[data-asistente-abrir]').click();
    const panel = page.locator('#asistente-wa');
    await expect(panel).toBeVisible();
    return panel;
}

async function responder(panel, campo, valor) {
    await panel.getByPlaceholder(campo).fill(valor);
    await panel.getByRole('button', { name: 'Continuar' }).click();
}

async function completarCotizacion(panel) {
    await panel.getByRole('button', { name: '2) Solicitar una cotización' }).click();
    await responder(panel, 'Nombre y apellido', 'Ana Pérez');
    await panel.getByRole('button', { name: 'Omitir' }).click();
    await panel.getByRole('button', { name: ENSAYO_WEB.titulo, exact: true }).click();

    // REQ-WEB-12: cantidad fuera de rango no avanza.
    await responder(panel, 'Ej.: 3', '0');
    await expect(panel.getByRole('alert')).toContainText('número entero mayor que cero');
    await responder(panel, 'Ej.: 3', '3');

    // REQ-WEB-13: provincia excluida (D-VCF-002) no avanza.
    await responder(panel, 'Distrito o referencia', 'Jaén');
    await expect(panel.getByRole('alert')).toContainText('solo proyectos en Cajamarca');
    await responder(panel, 'Distrito o referencia', 'Baños del Inca');
}

test('el botón flotante abre el asistente con el menú (REQ-WEB-01, 04)', async ({ page }) => {
    await fijarHorario(page, true);
    const panel = await abrirAsistente(page);

    await expect(page.locator('[data-asistente-abrir]')).toHaveCount(1);
    await expect(panel).toContainText(/Buenos días|Buenas tardes|Buenas noches/);
    for (const opcion of ['1) Ver nuestros servicios', '2) Solicitar una cotización', '3) Conversar con un asesor']) {
        await expect(panel.getByRole('button', { name: opcion })).toBeVisible();
    }
});

test('en horario, la cotización arma el enlace a WhatsApp con la plantilla (REQ-WEB-11 a 16)', async ({ page }) => {
    await fijarHorario(page, true);
    const panel = await abrirAsistente(page);
    await completarCotizacion(panel);

    await expect(panel).toContainText('Revise sus datos');
    await expect(panel).toContainText('Persona natural');
    await expect(panel).toContainText('Baños del Inca, Cajamarca');

    const enlace = panel.getByRole('link', { name: 'Enviar por WhatsApp' });
    await expect(enlace).toHaveAttribute('target', '_blank');
    const href = await enlace.getAttribute('href');
    expect(href.startsWith(`https://wa.me/${WHATSAPP_DIGITOS}?text=`)).toBe(true);

    const mensaje = new URL(href).searchParams.get('text');
    expect(mensaje).toMatch(/^(Buenos días|Buenas tardes|Buenas noches), Grupo VICAF\. Solicito una cotización:/);
    expect(mensaje).toContain('• Nombre: Ana Pérez');
    expect(mensaje).toContain('• Empresa: Persona natural');
    expect(mensaje).toContain(`• Servicio: ${ENSAYO_WEB.titulo}`);
    expect(mensaje).toContain('• Cantidad de muestras: 3');
    expect(mensaje).toContain('• Ubicación: Baños del Inca, Cajamarca');
});

test('fuera de horario muestra el aviso antes de abrir WhatsApp (REQ-WEB-18)', async ({ page }) => {
    await fijarHorario(page, false);
    const panel = await abrirAsistente(page);
    await completarCotizacion(panel);

    await panel.getByRole('button', { name: 'Enviar por WhatsApp' }).click();
    await expect(panel).toContainText('Nuestro horario de atención es');
    const href = await panel.getByRole('link', { name: 'Continuar a WhatsApp' }).getAttribute('href');
    expect(href.startsWith(`https://wa.me/${WHATSAPP_DIGITOS}?text=`)).toBe(true);
});

test('el endpoint del asistente no expone precios ni códigos internos (REQ-WEB-10)', async ({ request }) => {
    const respuesta = await request.get(`${WEB_URL}/contacto/asistente/`);
    expect(respuesta.ok()).toBe(true);
    const texto = await respuesta.text();
    expect(texto).not.toContain('E2E-001');
    expect(texto).not.toMatch(/precio|codigo_facturacion|acreditado/i);
});
