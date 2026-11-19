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
        // Como Outlook: solo el último mensaje abierto; los anteriores plegados en una línea.
        await expect(page.locator('.mensaje--ultimo')).toHaveAttribute('open', '');
        // Detalles (participantes, quién lo atiende, actividad) en un panel que se abre con un botón.
        const detalles = page.getByRole('button', { name: 'Detalles de la conversación' });
        if ((await detalles.getAttribute('aria-expanded')) !== 'true') { await detalles.click(); }
        await expect(page.getByRole('heading', { name: 'Participantes' })).toBeVisible();
        await detalles.click();
        await expect(page.getByRole('heading', { name: 'Participantes' })).toBeHidden();

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

    test('barra de comandos: sin marcar nada actúa sobre la conversación abierta', async ({ page }) => {
        await abrirCorreo(page, 'informes');
        const comandos = page.getByRole('toolbar', { name: 'Acciones de correo' });
        await expect(comandos.getByRole('button', { name: 'Archivar' })).toBeDisabled();
        await page.locator('.fila__enlace', { hasText: 'Recepción de muestras' }).click();
        await expect(comandos.getByRole('button', { name: 'Archivar' })).toBeEnabled();
        await comandos.getByRole('button', { name: 'Marcar como no leído' }).click();
        await expect(page.locator('.avisos')).toContainText('no leídos');
        await expect(page.locator('.fila', { hasText: 'Recepción de muestras' })).toHaveClass(/fila--no-leida/);
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

    test('destinatarios: sugerencias al entrar, fichas y quitar', async ({ page }) => {
        const violaciones = vigilarCsp(page);
        const origen = await abrirCorreo(page, 'informes');
        await page.goto(`${origen}/redactar/?cuenta=informes`);
        const para = page.locator('#r-para');
        const sugerencias = page.locator('#sug-para');

        // Al entrar al campo vacío: contactos recientes, como en Outlook.
        await para.focus();
        await expect(sugerencias).toBeVisible();
        await expect(sugerencias).toContainText('Contactos recientes');

        // Escribir busca también las cuentas VICAF; Enter elige la marcada.
        await para.pressSequentially('labor');
        await expect(sugerencias.getByRole('option').first()).toContainText('laboratorio@grupovicaf.com');
        await page.keyboard.press('Enter');
        await expect(page.locator('.ficha')).toHaveCount(1);
        await expect(page.locator('.ficha').first()).toHaveText(/Laboratorio/);

        // Pegar o escribir con comas crea varias fichas; la inválida se marca.
        await para.pressSequentially('malo@, otro@cliente.example,');
        await expect(page.locator('.ficha')).toHaveCount(3);
        await expect(page.locator('.ficha--invalida')).toHaveCount(1);

        // Retroceso en el campo vacío selecciona la última ficha y la quita.
        await page.keyboard.press('Backspace');
        await expect(page.locator('.ficha').last()).toBeFocused();
        await page.keyboard.press('Backspace');
        await expect(page.locator('.ficha')).toHaveCount(2);
        await page.getByRole('button', { name: /Quitar malo@ de Para/ }).click();
        await expect(page.locator('.ficha')).toHaveCount(1);

        await expect(page.locator('input[type="hidden"][name="para"]')).toHaveValue('Laboratorio <laboratorio@grupovicaf.com>');

        // CC y CCO quedan ocultos hasta pedirlos.
        await expect(page.locator('#r-cc')).toBeHidden();
        await page.getByRole('button', { name: 'CC', exact: true }).click();
        await expect(page.locator('#r-cc')).toBeVisible();
        await expect(page.locator('#r-cc')).toBeFocused();
        expect(violaciones).toEqual([]);
    });

    test('la Bandeja de salida muestra el envío fallido y permite reintentar', async ({ page }) => {
        await abrirCorreo(page, 'informes');
        await page.locator('.grupo-cuenta[data-cuenta="informes"]').getByRole('link', { name: /Bandeja de salida/ }).click();
        await expect(page.locator('.chip--rojo', { hasText: 'Falló el envío' }).first()).toBeVisible();
        await page.locator('.fila__enlace').first().click();
        await expect(page.getByRole('button', { name: 'Reintentar' })).toBeVisible();
    });

    test('la barra de búsqueda sugiere personas y correos mientras se escribe', async ({ page }) => {
        const violaciones = vigilarCsp(page);
        await abrirCorreo(page);
        const q = page.locator('#q-rapida');
        await q.pressSequentially('compres', { delay: 30 });
        const lista = page.locator('#q-rapida-lista');
        await expect(lista).toBeVisible();
        await expect(q).toHaveAttribute('aria-expanded', 'true');
        await expect(lista.locator('.sugerencias__titulo', { hasText: 'Correos' })).toBeVisible();
        await expect(lista.getByRole('option', { name: /Buscar «compres»/ })).toBeVisible();

        // Teclado: ↓ marca la primera opción y Enter la abre.
        await q.press('ArrowDown');
        await expect(q).toHaveAttribute('aria-activedescendant', 'q-rapida-op-0');
        await q.press('Escape');
        await expect(lista).toBeHidden();

        await q.press('End');
        await q.pressSequentially('i');
        await lista.locator('.sugerencia--correo').first().click();
        await expect(page).toHaveURL(/\?h=\d+/);
        expect(violaciones).toEqual([]);
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

    test('administrar: crear una cuenta, dar acceso, cambiar rol y quitarlo', async ({ page }) => {
        const violaciones = vigilarCsp(page);
        await abrirCorreo(page);
        await page.getByRole('link', { name: 'Administrar cuentas' }).click();
        await expect(page.getByRole('heading', { name: 'Administrar cuentas' })).toBeVisible();

        const direccion = `e2e${Date.now()}@grupovicaf.com`;  // la base de e2e no se vacía entre corridas
        await page.getByLabel('Dirección').fill(direccion);
        await page.getByLabel('Nombre visible').fill('Cuenta E2E');
        await page.getByRole('button', { name: 'Crear cuenta' }).click();
        await expect(page.getByRole('heading', { name: 'Cuenta E2E' })).toBeVisible();
        await expect(page.locator('.tabla')).toContainText('e2e.coordinador');  // «Darme acceso» marcado

        const tecnico = await page.locator('#a-usuario option', { hasText: '(e2e.tecnico.a)' }).getAttribute('value');
        await page.getByLabel('Trabajador').selectOption(tecnico);
        await page.getByLabel('Rol', { exact: true }).selectOption('lectura');
        await page.getByRole('button', { name: 'Dar acceso' }).click();
        const fila = page.locator('.tabla tr', { hasText: 'e2e.tecnico.a' });
        await expect(fila).toContainText('Sin permiso Correo en su rol');
        await fila.locator('select').selectOption('gestiona');
        await expect(page.locator('.avisos')).toContainText('Rol actualizado');

        page.once('dialog', (d) => d.accept());
        await page.locator('.tabla tr', { hasText: 'e2e.tecnico.a' }).getByRole('button', { name: 'Quitar' }).click();
        await expect(page.locator('.tabla tr', { hasText: 'e2e.tecnico.a' })).toHaveCount(0);
        await expect(page.locator('.actividad')).toContainText('quitó el acceso');

        // La cuenta nueva ya aparece en el panel de carpetas de quien la creó.
        await expect(page.locator('.grupo-cuenta', { hasText: 'Cuenta E2E' }).first()).toBeVisible();

        // Se desactiva al final: desaparece de las bandejas y las demás pruebas siguen viendo 3 cuentas.
        await page.locator('input[name="activa"][value="0"]').check();
        await page.getByRole('button', { name: 'Guardar' }).click();
        await expect(page.getByText('Inactiva: nadie la ve en su bandeja')).toBeVisible();
        await expect(page.locator('.grupo-cuenta', { hasText: 'Cuenta E2E' })).toHaveCount(0);
        expect(violaciones).toEqual([]);
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
