'use strict';

document.addEventListener('DOMContentLoaded', () => {
    const header = document.getElementById('site-header');
    const menuToggle = document.getElementById('menu-toggle');
    const mobileMenu = document.getElementById('mobile-menu');
    const openIcon = document.getElementById('menu-icon-open');
    const closeIcon = document.getElementById('menu-icon-close');
    const mobileLinks = document.querySelectorAll(
        '#mobile-menu .mobile-nav-link'
    );

    if (!menuToggle || !mobileMenu) {
        return;
    }

    const setMenuState = (isOpen) => {
        mobileMenu.classList.toggle('hidden', !isOpen);
        openIcon?.classList.toggle('hidden', isOpen);
        closeIcon?.classList.toggle('hidden', !isOpen);

        menuToggle.setAttribute('aria-expanded', String(isOpen));
        menuToggle.setAttribute(
            'aria-label',
            isOpen
                ? 'Cerrar menú principal'
                : 'Abrir menú principal'
        );
    };

    menuToggle.addEventListener('click', () => {
        const isOpen =
            menuToggle.getAttribute('aria-expanded') === 'true';

        setMenuState(!isOpen);
    });

    mobileLinks.forEach((link) => {
        link.addEventListener('click', () => {
            setMenuState(false);
        });
    });

    document.addEventListener('keydown', (event) => {
        if (event.key === 'Escape') {
            setMenuState(false);
            menuToggle.focus();
        }
    });

    document.addEventListener('click', (event) => {
        const target = event.target;

        if (
            target instanceof Node &&
            header &&
            !header.contains(target) &&
            menuToggle.getAttribute('aria-expanded') === 'true'
        ) {
            setMenuState(false);
        }
    });

    window.addEventListener('resize', () => {
        if (window.innerWidth >= 768) {
            setMenuState(false);
        }
    });
});