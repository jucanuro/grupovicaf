// Pruebas E2E (VCF-INFRA): Playwright contra los dos sitios del proyecto.
//
//   npm run test:e2e                     # levanta lab (:8000) y web (:8001), siembra y prueba
//   E2E_PYTHON=venv/bin/python npm run test:e2e
//
// Si lab y web ya están arriba (p. ej. docker-compose.dev.yml), Playwright
// los reutiliza y NO siembra: antes corra
//   docker compose -f docker-compose.dev.yml exec lab python manage.py sembrar_e2e
// Ver e2e/README.md.
const { defineConfig, devices } = require('@playwright/test');
const { LAB_URL, WEB_URL } = require('./e2e/datos');

const python = process.env.E2E_PYTHON || 'python';
// test_local: caché en memoria y Celery en modo eager (sin Redis ni worker).
const entorno = (rol) => ({
    SITE_ROLE: rol,
    DJANGO_SETTINGS_MODULE: process.env.DJANGO_SETTINGS_MODULE || 'grupovicaf.settings.test_local',
    DEBUG: 'True',
    PYTHONUNBUFFERED: '1',
});

module.exports = defineConfig({
    testDir: './e2e',
    fullyParallel: false,
    workers: 1,
    forbidOnly: Boolean(process.env.CI),
    retries: process.env.CI ? 1 : 0,
    timeout: 30_000,
    reporter: process.env.CI ? [['list'], ['html', { open: 'never' }]] : 'list',
    use: {
        locale: 'es-PE',
        timezoneId: 'America/Lima',
        trace: 'retain-on-failure',
        screenshot: 'only-on-failure',
    },
    projects: [
        { name: 'chromium', use: { ...devices['Desktop Chrome'] } },
    ],
    webServer: [
        {
            // El lab migra y siembra antes de escuchar: cuando su URL responde,
            // los datos de e2e/datos.js ya existen.
            command: `${python} manage.py migrate --noinput && ${python} manage.py sembrar_e2e`
                + ` && ${python} manage.py runserver 127.0.0.1:8000 --noreload`,
            url: `${LAB_URL}/`,
            env: entorno('lab'),
            reuseExistingServer: !process.env.CI,
            timeout: 180_000,
            stdout: 'ignore',
            stderr: process.env.CI ? 'pipe' : 'ignore',
        },
        {
            // Responde 500 hasta que el lab termine de migrar; Playwright
            // sigue esperando mientras tanto.
            command: `${python} manage.py runserver 127.0.0.1:8001 --noreload`,
            url: `${WEB_URL}/`,
            env: entorno('web'),
            reuseExistingServer: !process.env.CI,
            timeout: 180_000,
            stdout: 'ignore',
            stderr: process.env.CI ? 'pipe' : 'ignore',
        },
    ],
});
