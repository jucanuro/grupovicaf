// Valores que siembra `python manage.py sembrar_e2e`
// (core/management/commands/sembrar_e2e.py). Si cambia uno allí, cambia aquí.
module.exports = {
    LAB_URL: process.env.E2E_LAB_URL || 'http://127.0.0.1:8000',
    WEB_URL: process.env.E2E_WEB_URL || 'http://127.0.0.1:8001',
    PASSWORD: process.env.E2E_PASSWORD || 'vicaf-e2e-2026',

    USUARIOS: {
        coordinador: 'e2e.coordinador',
        tecnicoAsignado: 'e2e.tecnico.a',
        tecnicoAjeno: 'e2e.tecnico.b',
        analista: 'e2e.analista',
        recepcion: 'e2e.recepcion',
        jefe: 'e2e.jefe',
        comercial: 'e2e.comercial',
    },

    // Panel de proyectos con avance por muestra (HU-LIMS-19).
    PROYECTO_AVANCE: {
        codigo: 'P-E2E-AVANCE',
        nombre: 'Proyecto E2E Avance por muestra',
        etapas: { por_ingresar: 5, recibida: 2, en_ensayo: 1, informe: 0 },
        solicitud: 'SOL-E2E-AV01',
    },

    CLIENTE: { ruc: '20999999991', razonSocial: 'Constructora E2E SAC' },
    SOLICITUD: 'SOL-E2E-0001',
    SLUG_INFORME: 'e2e00000-0000-4000-8000-000000000001',

    ENSAYO_WEB: { slug: 'e2e-proctor-modificado', titulo: 'Proctor Modificado E2E' },
    WHATSAPP_DIGITOS: '51964326364',
};
