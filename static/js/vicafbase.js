/**
 * VICAF Pro Enterprise - Core Interface Logic
 * Maneja Sidebar, Mobile Menu y Command Palette
 */

document.addEventListener('DOMContentLoaded', () => {
    // 1. Inicialización de Componentes Base
    if (typeof lucide !== 'undefined') {
        lucide.createIcons();
    }
    
    const yearEl = document.getElementById('year');
    if (yearEl) yearEl.textContent = new Date().getFullYear();

    // --- MÓDULO: SIDEBAR (HOVER & TOGGLE) ---
    const sidebar = document.querySelector('.sidebar-glass') || document.getElementById('sidebar');
    const toggleBtn = document.getElementById('toggle-sidebar');
    const menuIcon = document.getElementById('menu-icon');

    // Manejo de visibilidad de textos en hover (si se usa sidebar colapsable)
    if (sidebar) {
        sidebar.addEventListener('mouseenter', () => {
            document.querySelectorAll('.sidebar-glass-hover\\:opacity-100').forEach(el => {
                el.classList.add('opacity-100', 'translate-x-0');
                el.classList.remove('opacity-0', 'translate-x-[-10px]');
            });
        });

        sidebar.addEventListener('mouseleave', () => {
            document.querySelectorAll('.sidebar-glass-hover\\:opacity-100').forEach(el => {
                el.classList.remove('opacity-100', 'translate-x-0');
                el.classList.add('opacity-0', 'translate-x-[-10px]');
            });
        });
    }

    // Toggle Sidebar Plegable (Botón Hamburguesa)
    if (toggleBtn && sidebar) {
        toggleBtn.addEventListener('click', () => {
            sidebar.classList.toggle('-translate-x-full');
            if (menuIcon) {
                const isHidden = sidebar.classList.contains('-translate-x-full');
                menuIcon.setAttribute('data-lucide', isHidden ? 'menu' : 'x');
                lucide.createIcons();
            }
        });
    }

    // --- MÓDULO: DROPDOWNS ---
    const proyectosBtn = document.getElementById('proyectos-btn');
    const proyectosMenu = document.getElementById('proyectos-menu');
    const arrowProyectos = document.getElementById('arrow-proyectos');
    
    if (proyectosBtn && proyectosMenu) {
        proyectosBtn.addEventListener('click', () => {
            proyectosMenu.classList.toggle('hidden');
            proyectosMenu.classList.toggle('flex');
            if (arrowProyectos) arrowProyectos.classList.toggle('rotate-90');
        });
    }

    // --- MÓDULO: MOBILE MENU ---
    const mobileBtn = document.getElementById('mobile-menu-btn');
    const mobileMenu = document.getElementById('mobile-menu');
    const closeMobile = document.getElementById('close-mobile');

    if (mobileBtn && mobileMenu) {
        mobileBtn.addEventListener('click', () => mobileMenu.classList.remove('translate-x-full'));
    }
    if (closeMobile && mobileMenu) {
        closeMobile.addEventListener('click', () => mobileMenu.classList.add('translate-x-full'));
    }

    // --- MÓDULO: COMMAND PALETTE (CMD + K) ---
    const palette = document.getElementById('cmd-palette');
    const panel = document.getElementById('cmd-panel');
    const input = document.getElementById('cmd-input');
    const trigger = document.getElementById('search-trigger');
    const closeCmd = document.getElementById('cmd-close');

    function openCmd() {
        if (!palette) return;
        palette.classList.remove('hidden');
        setTimeout(() => {
            palette.classList.remove('opacity-0');
            panel?.classList.remove('scale-95');
            panel?.classList.add('scale-100');
            input?.focus();
        }, 10);
    }

    function closeCmdFunc() {
        if (!palette) return;
        palette.classList.add('opacity-0');
        panel?.classList.remove('scale-100');
        panel?.classList.add('scale-95');
        setTimeout(() => {
            palette.classList.add('hidden');
        }, 200);
    }

    if (trigger) trigger.addEventListener('click', openCmd);
    if (closeCmd) closeCmd.addEventListener('click', closeCmdFunc);

    // Atajos de teclado
    document.addEventListener('keydown', (e) => {
        if ((e.ctrlKey || e.metaKey) && e.key === 'k') {
            e.preventDefault();
            openCmd();
        }
        if (e.key === 'Escape' && palette && !palette.classList.contains('hidden')) {
            closeCmdFunc();
        }
    });
    
    // Cerrar al click fuera del panel
    if (palette) {
        palette.addEventListener('click', (e) => {
            if (e.target === palette) closeCmdFunc();
        });
    }
});