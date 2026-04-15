document.addEventListener('DOMContentLoaded', () => {
    const STORAGE_KEYS = {
        sidebarExpanded: 'vicaf.sidebar.expanded',
        proyectosOpen: 'vicaf.sidebar.proyectos.open'
    };

    const body = document.body;
    const sidebar = document.querySelector('.sidebar-glass') || document.getElementById('sidebar');
    const toggleBtn = document.getElementById('toggle-sidebar');
    const menuIcon = document.getElementById('menu-icon');

    const proyectosBtn = document.getElementById('proyectos-btn');
    const proyectosMenu = document.getElementById('proyectos-menu');
    const arrowProyectos = document.getElementById('arrow-proyectos');

    const mobileBtn = document.getElementById('mobile-menu-btn');
    const mobileMenu = document.getElementById('mobile-menu');
    const closeMobile = document.getElementById('close-mobile');

    const palette = document.getElementById('cmd-palette');
    const panel = document.getElementById('cmd-panel');
    const input = document.getElementById('cmd-input');
    const trigger = document.getElementById('search-trigger');
    const closeCmd = document.getElementById('cmd-close');

    const yearEl = document.getElementById('year');
    if (yearEl) yearEl.textContent = new Date().getFullYear();

    function refreshIcons() {
        if (typeof lucide !== 'undefined') {
            lucide.createIcons();
        }
    }

    refreshIcons();

    function currentPath() {
        return window.location.pathname || '';
    }

    function isProyectoRoute() {
        return currentPath().includes('/proyectos/');
    }

    function setSidebarExpanded(expanded, persist = true) {
        if (!sidebar) return;

        sidebar.classList.toggle('is-expanded', expanded);

        if (expanded) {
            sidebar.classList.remove('w-[5.5rem]');
            sidebar.classList.add('w-[19rem]');
            body.classList.add('sidebar-expanded');
        } else {
            sidebar.classList.add('w-[5.5rem]');
            sidebar.classList.remove('w-[19rem]');
            body.classList.remove('sidebar-expanded');
        }

        document.querySelectorAll('.nav-text').forEach(el => {
            if (expanded) {
                el.classList.remove('opacity-0', 'translate-x-[-15px]', 'translate-x-[-20px]', 'pointer-events-none');
                el.classList.add('opacity-100', 'translate-x-0');
            } else {
                el.classList.remove('opacity-100', 'translate-x-0');
                el.classList.add('opacity-0');
            }
        });

        if (persist) {
            localStorage.setItem(STORAGE_KEYS.sidebarExpanded, expanded ? '1' : '0');
        }
    }

    function setSidebarMobileOpen(open) {
        if (!sidebar) return;

        sidebar.classList.toggle('-translate-x-full', !open);

        if (menuIcon) {
            menuIcon.setAttribute('data-lucide', open ? 'x' : 'menu');
            refreshIcons();
        }
    }

    function setProyectosMenu(open, persist = true) {
        if (!proyectosMenu || !proyectosBtn) return;

        proyectosMenu.classList.toggle('hidden', !open);
        proyectosMenu.classList.toggle('flex', open);

        if (arrowProyectos) {
            arrowProyectos.classList.toggle('rotate-90', open);
        }

        proyectosBtn.setAttribute('aria-expanded', open ? 'true' : 'false');

        if (persist) {
            localStorage.setItem(STORAGE_KEYS.proyectosOpen, open ? '1' : '0');
        }
    }

    function toggleProyectosMenu() {
        if (!proyectosMenu) return;
        const isOpen = !proyectosMenu.classList.contains('hidden');
        setProyectosMenu(!isOpen, true);
    }

    function hydrateStateFromStorage() {
        if (!sidebar) return;

        const isDesktop = window.matchMedia('(min-width: 1024px)').matches;
        const savedSidebarExpanded = localStorage.getItem(STORAGE_KEYS.sidebarExpanded);
        const savedProyectosOpen = localStorage.getItem(STORAGE_KEYS.proyectosOpen);

        if (isDesktop) {
            const shouldExpand = savedSidebarExpanded === '1';
            setSidebarExpanded(shouldExpand, false);
        }

        if (isProyectoRoute()) {
            setProyectosMenu(true, false);
        } else if (savedProyectosOpen !== null) {
            setProyectosMenu(savedProyectosOpen === '1', false);
        } else {
            setProyectosMenu(false, false);
        }
    }

    function bindSidebarInteractions() {
        if (!sidebar) return;

        const isDesktop = () => window.matchMedia('(min-width: 1024px)').matches;

        sidebar.addEventListener('mouseenter', () => {
            if (!isDesktop()) return;
            setSidebarExpanded(true, false);
        });

        sidebar.addEventListener('mouseleave', () => {
            if (!isDesktop()) return;
            const pinned = localStorage.getItem(STORAGE_KEYS.sidebarExpanded) === '1';
            setSidebarExpanded(pinned, false);
        });

        if (toggleBtn) {
            toggleBtn.addEventListener('click', () => {
                if (isDesktop()) {
                    const expanded = sidebar.classList.contains('is-expanded');
                    setSidebarExpanded(!expanded, true);
                } else {
                    const isHidden = sidebar.classList.contains('-translate-x-full');
                    setSidebarMobileOpen(isHidden);
                }
            });
        }
    }

    function bindProyectoMenu() {
        if (!proyectosBtn || !proyectosMenu) return;

        proyectosBtn.addEventListener('click', (e) => {
            e.preventDefault();
            e.stopPropagation();
            toggleProyectosMenu();
        });

        proyectosBtn.addEventListener('keydown', (e) => {
            if (e.key === 'Enter' || e.key === ' ') {
                e.preventDefault();
                toggleProyectosMenu();
            }
        });
    }

    function bindMobileMenu() {
        if (mobileBtn && mobileMenu) {
            mobileBtn.addEventListener('click', () => {
                mobileMenu.classList.remove('translate-x-full');
            });
        }

        if (closeMobile && mobileMenu) {
            closeMobile.addEventListener('click', () => {
                mobileMenu.classList.add('translate-x-full');
            });
        }
    }

    function openCmd() {
        if (!palette) return;
        palette.classList.remove('hidden');
        requestAnimationFrame(() => {
            palette.classList.remove('opacity-0');
            panel?.classList.remove('scale-95');
            panel?.classList.add('scale-100');
            input?.focus();
        });
    }

    function closeCmdFunc() {
        if (!palette) return;
        palette.classList.add('opacity-0');
        panel?.classList.remove('scale-100');
        panel?.classList.add('scale-95');
        setTimeout(() => {
            palette.classList.add('hidden');
        }, 180);
    }

    if (trigger) trigger.addEventListener('click', openCmd);
    if (closeCmd) closeCmd.addEventListener('click', closeCmdFunc);

    document.addEventListener('keydown', (e) => {
        if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'k') {
            e.preventDefault();
            openCmd();
        }

        if (e.key === 'Escape') {
            if (palette && !palette.classList.contains('hidden')) {
                closeCmdFunc();
            }
        }
    });

    if (palette) {
        palette.addEventListener('click', (e) => {
            if (e.target === palette) closeCmdFunc();
        });
    }

    window.addEventListener('resize', () => {
        hydrateStateFromStorage();
    });

    hydrateStateFromStorage();
    bindSidebarInteractions();
    bindProyectoMenu();
    bindMobileMenu();
});