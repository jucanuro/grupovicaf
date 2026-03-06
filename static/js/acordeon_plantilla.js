/**
 * VICAF PRO V2.0 - Gestión de Acordeones para Plantillas
 * Archivo: acordeon_plantilla.js
 */

function toggleHeaderSection() {
    const content = document.getElementById('header-content-section');
    const chevron = document.getElementById('header-chevron');
    const summary = document.getElementById('header-summary-inline');
    const badge = document.getElementById('header-status-badge');
    
    const clienteSelect = document.getElementById('id_cliente_ruc');
    const clienteText = clienteSelect?.options[clienteSelect.selectedIndex]?.text || "";
    const asuntoText = document.getElementById('id_asunto_servicio')?.value || "";

    if (content.classList.contains('hidden')) {
        content.classList.remove('hidden');
        if (chevron) chevron.style.transform = 'rotate(0deg)';
        if (summary) summary.classList.add('hidden');
        if (badge) badge.classList.add('hidden');
    } else {
        content.classList.add('hidden');
        if (chevron) chevron.style.transform = 'rotate(180deg)';
        
        if (clienteSelect?.value || asuntoText) {
            const summaryTextEl = document.getElementById('summary-text');
            if (summaryTextEl) {
                const cleanName = clienteText.includes('-') ? clienteText.split('-')[1].trim() : clienteText;
                summaryTextEl.innerText = `${cleanName} | ${asuntoText}`;
            }
            if (summary) summary.classList.remove('hidden');
            if (badge) badge.classList.remove('hidden');
        }
    }
}


function toggleRegistroPanel() {
    const content = document.getElementById('content-registro');
    const icon = document.getElementById('icon-registro');
    
    if (!content) return;

    if (content.classList.contains('hidden')) {
        content.classList.remove('hidden');
        if (icon) icon.style.transform = 'rotate(180deg)';
    } else {
        content.classList.add('hidden');
        if (icon) icon.style.transform = 'rotate(0deg)';
    }
}

document.addEventListener('DOMContentLoaded', () => {
    // Si necesitas que empiece cerrado o con alguna lógica específica al cargar
});