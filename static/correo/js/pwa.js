/* Registra el service worker del correo (permite instalarlo como app). */
(function () {
    'use strict';
    if (!('serviceWorker' in navigator)) { return; }
    window.addEventListener('load', function () {
        navigator.serviceWorker.register('/sw.js', { scope: '/' }).catch(function () { /* sin PWA, la web sigue igual */ });
    });
})();
