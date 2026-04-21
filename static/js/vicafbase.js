document.addEventListener('DOMContentLoaded', () => {
    const STORAGE_KEYS = {
        sidebarExpanded: 'vicaf.sidebar.expanded',
        proyectosOpen: 'vicaf.sidebar.proyectos.open'
    };

    const body = document.body;

    // Sidebar / navegación principal
    const sidebar = document.querySelector('.sidebar-glass') || document.getElementById('sidebar');
    const toggleBtn = document.getElementById('toggle-sidebar');
    const menuIcon = document.getElementById('menu-icon');

    const proyectosBtn = document.getElementById('proyectos-btn');
    const proyectosMenu = document.getElementById('proyectos-menu');
    const arrowProyectos = document.getElementById('arrow-proyectos');

    const mobileBtn = document.getElementById('mobile-menu-btn');
    const mobileMenu = document.getElementById('mobile-menu');
    const closeMobile = document.getElementById('close-mobile');

    // Command palette
    const palette = document.getElementById('cmd-palette');
    const panel = document.getElementById('cmd-panel');
    const input = document.getElementById('cmd-input');
    const trigger = document.getElementById('search-trigger');
    const closeCmd = document.getElementById('cmd-close');

    // Año footer
    const yearEl = document.getElementById('year');

    // Launcher desktop inferior izquierdo
    const startTrigger = document.getElementById('desktop-start-trigger');
    const startMenu = document.getElementById('desktop-start-menu');
    const startOverlay = document.getElementById('desktop-start-overlay');
    const startSearch = document.getElementById('desktop-start-search');
    const startItems = Array.from(document.querySelectorAll('.desktop-start-item'));
    const startEmpty = document.getElementById('desktop-start-empty');
    const startCounter = document.getElementById('desktop-start-counter');

    if (yearEl) {
        yearEl.textContent = new Date().getFullYear();
    }

    let refreshIconsTimer = null;

    function refreshIcons(retries = 20) {
        const iconNodes = document.querySelectorAll('[data-lucide]');
        if (!iconNodes.length) return;

        if (typeof lucide !== 'undefined' && typeof lucide.createIcons === 'function') {
            try {
                lucide.createIcons();
                document.documentElement.classList.add('lucide-ready');
                return;
            } catch (error) {
                console.warn('Lucide createIcons falló, reintentando...', error);
            }
        }

        if (retries > 0) {
            setTimeout(() => refreshIcons(retries - 1), 120);
        } else {
            console.warn('Lucide no estuvo disponible a tiempo.');
        }
    }

    function queueRefreshIcons(delay = 60) {
        clearTimeout(refreshIconsTimer);
        refreshIconsTimer = setTimeout(() => {
            refreshIcons();
        }, delay);
    }

    function observeDynamicIcons() {
        if (!document.body) return;

        const observer = new MutationObserver((mutations) => {
            let shouldRefresh = false;

            for (const mutation of mutations) {
                if (mutation.type === 'childList') {
                    mutation.addedNodes.forEach(node => {
                        if (!(node instanceof HTMLElement)) return;

                        if (
                            node.matches?.('[data-lucide]') ||
                            node.querySelector?.('[data-lucide]')
                        ) {
                            shouldRefresh = true;
                        }
                    });
                }

                if (mutation.type === 'attributes') {
                    const target = mutation.target;
                    if (target instanceof HTMLElement && target.hasAttribute('data-lucide')) {
                        shouldRefresh = true;
                    }
                }

                if (shouldRefresh) break;
            }

            if (shouldRefresh) {
                queueRefreshIcons(40);
            }
        });

        observer.observe(document.body, {
            childList: true,
            subtree: true,
            attributes: true,
            attributeFilter: ['data-lucide']
        });
    }

    function currentPath() {
        return window.location.pathname || '';
    }

    function isProyectoRoute() {
        return currentPath().includes('/proyectos/');
    }

    function isDesktop() {
        return window.matchMedia('(min-width: 1024px)').matches;
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
                el.classList.remove(
                    'opacity-0',
                    'translate-x-[-15px]',
                    'translate-x-[-20px]',
                    'pointer-events-none'
                );
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
            queueRefreshIcons();
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

        queueRefreshIcons();
    }

    function toggleProyectosMenu() {
        if (!proyectosMenu) return;
        const isOpen = !proyectosMenu.classList.contains('hidden');
        setProyectosMenu(!isOpen, true);
    }

    function hydrateStateFromStorage() {
        if (!sidebar) return;

        const desktop = isDesktop();
        const savedSidebarExpanded = localStorage.getItem(STORAGE_KEYS.sidebarExpanded);
        const savedProyectosOpen = localStorage.getItem(STORAGE_KEYS.proyectosOpen);

        if (desktop) {
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
                queueRefreshIcons();
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
            queueRefreshIcons();
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

    function bindCommandPalette() {
        if (trigger) trigger.addEventListener('click', openCmd);
        if (closeCmd) closeCmd.addEventListener('click', closeCmdFunc);

        if (palette) {
            palette.addEventListener('click', (e) => {
                if (e.target === palette) closeCmdFunc();
            });
        }
    }

    window.initCommandHeaders = function initCommandHeaders() {
        const headers = document.querySelectorAll('[data-command-header]');

        headers.forEach(header => {
            if (header.dataset.commandReady === 'true') return;
            header.dataset.commandReady = 'true';

            const toggle = header.querySelector('[data-command-toggle]');
            const closeBtn = header.querySelector('[data-command-close]');
            const backdrop = header.querySelector('[data-command-backdrop]');
            const panelEl = header.querySelector('[data-command-panel]');
            const primaryAction = header.querySelector('[data-command-primary-action]');

            const openPanel = () => {
                document.querySelectorAll('[data-command-header].is-open').forEach(other => {
                    if (other !== header) other.classList.remove('is-open');
                });

                header.classList.add('is-open');
                queueRefreshIcons();
            };

            const closePanel = () => {
                header.classList.remove('is-open');
            };

            if (toggle) {
                toggle.addEventListener('click', (e) => {
                    e.preventDefault();
                    e.stopPropagation();
                    console.log('toggle clickeado');

                    if (header.classList.contains('is-open')) {
                        closePanel();
                    } else {
                        openPanel();
                    }
                });
            }

            if (closeBtn) {
                closeBtn.addEventListener('click', (e) => {
                    e.preventDefault();
                    e.stopPropagation();
                    closePanel();
                });
            }

            if (backdrop) {
                backdrop.addEventListener('click', closePanel);
            }

            if (panelEl) {
                panelEl.addEventListener('click', (e) => e.stopPropagation());
            }

            if (primaryAction) {
                primaryAction.addEventListener('click', () => {
                    closePanel();
                });
            }
        });
    };

    function updateCounter(visibleCount) {
        if (!startCounter) return;
        startCounter.textContent = `${visibleCount} módulo${visibleCount === 1 ? '' : 's'}`;
    }

    function filterStartMenu(query = '') {
        if (!startItems.length) {
            updateCounter(0);
            if (startEmpty) startEmpty.classList.remove('hidden');
            return;
        }

        const term = query.trim().toLowerCase();
        let visibleCount = 0;

        startItems.forEach(item => {
            const searchText = (item.dataset.search || '').toLowerCase();
            const labelText = (item.textContent || '').toLowerCase();
            const match = !term || searchText.includes(term) || labelText.includes(term);

            item.classList.toggle('hidden', !match);

            if (match) visibleCount += 1;
        });

        if (startEmpty) {
            startEmpty.classList.toggle('hidden', visibleCount > 0);
        }

        updateCounter(visibleCount);
    }

    function openStartMenu() {
        if (!startMenu || !startOverlay || !isDesktop()) return;

        if (startSearch) {
            startSearch.value = '';
        }

        filterStartMenu('');

        startMenu.classList.remove(
            'hidden',
            'opacity-0',
            'translate-y-6',
            'scale-95',
            'pointer-events-none'
        );
        startMenu.classList.add(
            'opacity-100',
            'translate-y-0',
            'scale-100',
            'pointer-events-auto'
        );

        startOverlay.classList.remove('hidden', 'opacity-0', 'pointer-events-none');
        startOverlay.classList.add('opacity-100', 'pointer-events-auto');

        if (startTrigger) {
            startTrigger.setAttribute('aria-expanded', 'true');
        }

        setTimeout(() => {
            queueRefreshIcons();
            startSearch?.focus();
        }, 120);
    }

    function closeStartMenu() {
        if (!startMenu || !startOverlay) return;

        startMenu.classList.remove(
            'opacity-100',
            'translate-y-0',
            'scale-100',
            'pointer-events-auto'
        );
        startMenu.classList.add(
            'opacity-0',
            'translate-y-6',
            'scale-95',
            'pointer-events-none'
        );

        startOverlay.classList.remove('opacity-100', 'pointer-events-auto');
        startOverlay.classList.add('opacity-0', 'pointer-events-none');

        if (startTrigger) {
            startTrigger.setAttribute('aria-expanded', 'false');
        }

        setTimeout(() => {
            if (!startMenu.classList.contains('opacity-100')) {
                startMenu.classList.add('hidden');
                startOverlay.classList.add('hidden');
            }
        }, 300);
    }

    function toggleStartMenu() {
        if (!startMenu) return;
        const isOpen = startMenu.classList.contains('opacity-100');
        if (isOpen) {
            closeStartMenu();
        } else {
            openStartMenu();
        }
    }

    function bindStartMenu() {
        if (startTrigger) {
            startTrigger.addEventListener('click', (e) => {
                e.stopPropagation();
                toggleStartMenu();
            });
        }

        if (startOverlay) {
            startOverlay.addEventListener('click', closeStartMenu);
        }

        if (startMenu) {
            startMenu.addEventListener('click', (e) => {
                e.stopPropagation();
            });
        }

        if (startSearch) {
            startSearch.addEventListener('input', (e) => {
                filterStartMenu(e.target.value);
            });
        }
    }

    document.addEventListener('click', (e) => {
        if (startMenu && startTrigger) {
            if (!startMenu.contains(e.target) && !startTrigger.contains(e.target)) {
                closeStartMenu();
            }
        }

        document.querySelectorAll('[data-command-header].is-open').forEach(header => {
            const toggle = header.querySelector('[data-command-toggle]');
            const panelEl = header.querySelector('[data-command-panel]');

            const clickedInsideToggle = toggle?.contains(e.target);
            const clickedInsidePanel = panelEl?.contains(e.target);

            if (!clickedInsideToggle && !clickedInsidePanel) {
                header.classList.remove('is-open');
            }
        });
    });

    document.addEventListener('keydown', (e) => {
        if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'k') {
            e.preventDefault();
            openCmd();
        }

        if (e.key === 'Escape') {
            if (palette && !palette.classList.contains('hidden')) {
                closeCmdFunc();
            }

            closeStartMenu();

            document.querySelectorAll('[data-command-header].is-open').forEach(header => {
                header.classList.remove('is-open');
            });
        }
    });

    window.addEventListener('resize', () => {
        hydrateStateFromStorage();

        if (!isDesktop()) {
            closeStartMenu();
        }
    });

    hydrateStateFromStorage();
    bindSidebarInteractions();
    bindProyectoMenu();
    bindMobileMenu();
    bindCommandPalette();
    bindStartMenu();
    initCommandHeaders();

    filterStartMenu('');
    refreshIcons();
    observeDynamicIcons();

    window.addEventListener('load', () => {
        refreshIcons();
    });

    setTimeout(() => refreshIcons(), 250);
    setTimeout(() => refreshIcons(), 700);
    setTimeout(() => refreshIcons(), 1200);
});