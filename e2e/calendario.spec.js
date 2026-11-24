// Calendario rediseñado (HU-LIMS-21): calendarios de equipo y personales,
// visibilidad por participantes, creación rápida, formulario en dos paneles
// con cliente opcional y vista semanal con bloques por calendario.
// Datos: `python manage.py sembrar_e2e` (eventos en la semana actual).
const { test, expect } = require('@playwright/test');
const { LAB_URL, USUARIOS, CALENDARIO } = require('./datos');
const { entrarAlLab, cdnLocal } = require('./ayudas');

const EV = CALENDARIO.eventos;

test.beforeEach(async ({ context, page }) => {
    await cdnLocal(context);
    await page.setViewportSize({ width: 1440, height: 900 });
});

async function abrirCalendario(page, usuario) {
    await entrarAlLab(page, usuario);
    await page.goto(`${LAB_URL}/actividades/calendario/`);
    await page.evaluate(() => { try { localStorage.clear(); } catch (e) { /* sin almacenamiento */ } });
    await page.reload();
    await expect(page.locator('#fullcalendar .fc-timegrid')).toBeVisible();
}

const evento = (page, titulo) => page.locator('#fullcalendar .fc-event', { hasText: titulo });

test('cada persona ve solo los calendarios y eventos que le tocan', async ({ page }) => {
    await abrirCalendario(page, USUARIOS.agenda);
    await expect(page.locator('#vc-cal-equipo')).toContainText(CALENDARIO.equipo);
    await expect(page.locator('#vc-cal-personal')).toContainText(CALENDARIO.personal);
    await expect(evento(page, EV.equipo)).toBeVisible();
    await expect(evento(page, EV.personal)).toBeVisible();
    // Un evento con participantes solo lo ven ellos y quien lo creó.
    await expect(evento(page, EV.privado)).toHaveCount(0);

    await page.context().clearCookies();
    await abrirCalendario(page, USUARIOS.recepcion);
    await expect(evento(page, EV.equipo)).toBeVisible();
    await expect(evento(page, EV.personal)).toHaveCount(0);
    await expect(evento(page, EV.privado)).toHaveCount(0);
    await expect(page.locator('#vc-cal-personal')).not.toContainText(CALENDARIO.personal);

    await page.context().clearCookies();
    await abrirCalendario(page, USUARIOS.tecnicoAsignado);
    await expect(evento(page, EV.privado)).toBeVisible();
    await expect(evento(page, EV.equipo)).toHaveCount(0);
});

test('quien solo ve un calendario de equipo no puede editar sus eventos', async ({ page }) => {
    await abrirCalendario(page, USUARIOS.recepcion);
    await evento(page, EV.equipo).click();
    const tarjeta = page.locator('#popDetalle');
    await expect(tarjeta).toBeVisible();
    await expect(tarjeta).toContainText(CALENDARIO.equipo);
    await expect(tarjeta.locator('[data-accion="editar"]')).toHaveCount(0);
    await expect(tarjeta.locator('[data-accion="eliminar"]')).toHaveCount(0);
});

test('la vista semanal muestra título y hora, y los eventos que se cruzan van lado a lado', async ({ page }) => {
    await abrirCalendario(page, USUARIOS.recepcion);
    const largo = evento(page, EV.largo);
    const corto = evento(page, EV.corto);
    await expect(largo).toContainText(EV.largo);
    await expect(corto).toContainText(EV.corto);
    await expect(corto).toContainText(/8:30/);
    const a = await largo.boundingBox();
    const b = await corto.boundingBox();
    // El corto no tapa el título del largo: empieza a su derecha.
    expect(b.x).toBeGreaterThan(a.x + 10);
});

test('crear rápido arrastrando en la semana, en el calendario elegido', async ({ page }) => {
    await abrirCalendario(page, USUARIOS.agenda);
    // Domingo a las 19:00: hueco libre en los datos sembrados.
    const columna = page.locator('#fullcalendar .fc-timegrid-col[data-date]').last();
    const fila = page.locator('#fullcalendar .fc-timegrid-slot-lane[data-time="19:00:00"]');
    const col = await columna.boundingBox();
    const f = await fila.boundingBox();
    const x = col.x + col.width / 2;
    await page.mouse.move(x, f.y + 3);
    await page.mouse.down();
    await page.mouse.move(x, f.y + f.height * 2 - 3, { steps: 5 });
    await page.mouse.up();

    const pop = page.locator('#popRapido');
    await expect(pop).toBeVisible();
    await expect(page.locator('#rapido_hi')).toHaveValue('19:00');
    // La hora de fin se elige de una lista con la duración al lado.
    await page.locator('#rapido_hf').click();
    await page.locator('#rapido_hf_lista').getByRole('option', { name: /20:00\s*1 h$/ }).click();
    await expect(page.locator('#rapido_hf')).toHaveValue('20:00');
    const titulo = `Rápida E2E ${Date.now()}`;
    await page.locator('#rapido_titulo').fill(titulo);
    await page.locator('#rapido_calendarios').getByText(CALENDARIO.personal).click();
    const respuesta = page.waitForResponse((r) => r.url().includes('/calendario/evento/guardar/'));
    await page.locator('#rapido_titulo').press('Enter');
    expect((await respuesta).status()).toBe(200);
    await expect(pop).toBeHidden();
    await expect(evento(page, titulo)).toBeVisible();
});

test('el formulario en dos paneles: cliente opcional y aviso por correo solo con cliente', async ({ page }) => {
    await abrirCalendario(page, USUARIOS.agenda);
    await page.locator('#btnNuevaActividad').click();
    const modal = page.locator('#modalFormulario');
    await expect(modal).toBeVisible();
    await expect(page.locator('#vista_previa')).toBeVisible();

    const titulo = `Visita E2E ${Date.now()}`;
    await page.locator('#titulo').fill(titulo);
    // La vista previa sigue lo que se escribe.
    await expect(page.locator('#vista_previa')).toContainText(titulo);
    await page.locator('#form_calendarios').getByText(CALENDARIO.equipo).click();

    // Sin cliente, el aviso por correo no se puede marcar.
    await expect(page.locator('#avisar_cliente')).toBeDisabled();
    await page.locator('#cliente_buscar').fill(CALENDARIO.clienteConCorreo);
    await page.locator('#cliente_buscar').press('Tab');
    await expect(page.locator('#cliente_chip')).toContainText(CALENDARIO.clienteConCorreo);
    await expect(page.locator('#avisar_cliente')).toBeEnabled();
    await page.locator('#avisar_cliente').check();

    const respuesta = page.waitForResponse((r) => r.url().includes('/calendario/evento/guardar/'));
    await page.getByRole('button', { name: /Guardar actividad/i }).click();
    const r = await respuesta;
    expect(r.status()).toBe(200);
    expect((await r.json()).aviso_cliente).toBe(true);
    await expect(modal).toBeHidden();
    await expect(evento(page, titulo)).toBeVisible();
});

test('un calendario personal nuevo solo aparece para quien lo creó', async ({ page }) => {
    await abrirCalendario(page, USUARIOS.recepcion);
    const nombre = `Estudio ${Date.now()}`;
    await page.locator('[data-nuevo-calendario="PERSONAL"]').click();
    await expect(page.locator('#modalCalendario')).toBeVisible();
    await page.locator('#cal_nombre').fill(nombre);
    await page.locator('#cal_tipo').getByText(/Personal/).click();
    await page.locator('#btnGuardarCalendario').click();
    await expect(page.locator('#modalCalendario')).toBeHidden();
    await expect(page.locator('#vc-cal-personal')).toContainText(nombre);

    await page.context().clearCookies();
    await abrirCalendario(page, USUARIOS.agenda);
    await expect(page.locator('#vc-cal-personal')).not.toContainText(nombre);
});

test('estirar o mover un evento lo guarda y ofrece deshacer', async ({ page }) => {
    await abrirCalendario(page, USUARIOS.agenda);
    const ev = evento(page, EV.equipo);
    await ev.hover();
    const r = await ev.locator('.fc-event-resizer-end').boundingBox();
    const respuesta = page.waitForResponse((x) => x.url().includes('/reprogramar/'));
    await page.mouse.move(r.x + r.width / 2, r.y + r.height / 2);
    await page.mouse.down();
    await page.mouse.move(r.x + r.width / 2, r.y + 45, { steps: 6 });
    await page.mouse.up();
    expect((await respuesta).status()).toBe(200);
    const toast = page.locator('#vc-toast');
    await expect(toast).toContainText('movida');
    // Deshacer lo deja como estaba.
    const deshacer = page.waitForResponse((x) => x.url().includes('/reprogramar/'));
    await toast.getByRole('button', { name: 'Deshacer' }).click();
    expect((await deshacer).status()).toBe(200);
    await expect(evento(page, EV.equipo)).toContainText('10:00 – 11:00');
});

test('la hora se elige de una lista y el fin conserva la duración', async ({ page }) => {
    await abrirCalendario(page, USUARIOS.agenda);
    await page.locator('#btnNuevaActividad').click();
    await page.locator('#fi_hora').click();
    const lista = page.locator('#fi_hora_lista');
    await expect(lista).toBeVisible();
    await lista.getByRole('option', { name: '10:30', exact: true }).click();
    await expect(lista).toBeHidden();
    await expect(page.locator('#fi_hora')).toHaveValue('10:30');
    await expect(page.locator('#ff_hora')).toHaveValue('11:30');

    // También se puede escribir: «4pm» → 16:00.
    await page.locator('#ff_hora').fill('4pm');
    await page.locator('#ff_hora').press('Enter');
    await expect(page.locator('#ff_hora')).toHaveValue('16:00');
    await expect(page.locator('#fecha_fin')).toHaveValue(/T16:00$/);
    await expect(page.locator('#resumen')).toContainText('10:30 – 16:00');
});
