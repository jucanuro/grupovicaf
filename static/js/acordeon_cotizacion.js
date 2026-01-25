function toggleHeaderSection() {
    const content = document.getElementById('header-content-section');
    const chevron = document.getElementById('header-chevron');
    const summary = document.getElementById('header-summary-inline');
    const badge = document.getElementById('header-status-badge');
    
    // Obtener valores para el resumen
    const clienteSelect = document.getElementById('id_cliente_ruc');
    const clienteText = clienteSelect.options[clienteSelect.selectedIndex]?.text || "";
    const asuntoText = document.getElementById('id_asunto_servicio').value;

    if (content.classList.contains('hidden')) {
        // Abrir
        content.classList.remove('hidden');
        chevron.style.transform = 'rotate(0deg)';
        summary.classList.add('hidden');
        badge.classList.add('hidden');
    } else {
        // Cerrar
        content.classList.add('hidden');
        chevron.style.transform = 'rotate(180deg)';
        
        // Mostrar resumen si hay datos
        if (clienteSelect.value || asuntoText) {
            document.getElementById('summary-text').innerText = `${clienteText.split('-')[1] || clienteText} | ${asuntoText}`;
            summary.classList.remove('hidden');
            badge.classList.remove('hidden');
        }
    }
}

function toggleRegistroPanel() {
    const content = document.getElementById('content-registro');
    const icon = document.getElementById('icon-registro');
    
    if (content.classList.contains('hidden')) {
        content.classList.remove('hidden');
        icon.style.transform = 'rotate(180deg)';
    } else {
        content.classList.add('hidden');
        icon.style.transform = 'rotate(0deg)';
    }
}