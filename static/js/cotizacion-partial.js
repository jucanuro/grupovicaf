(function () {
    function seleccionarModo(modo) {
        const btnVacio = document.getElementById('btn-modo-vacio');
        const btnPlantilla = document.getElementById('btn-modo-plantilla');

        if (!btnVacio || !btnPlantilla) return;

        if (modo === 'vacio') {
            btnVacio.classList.replace('border-slate-100', 'border-blue-500');
            btnPlantilla.classList.replace('border-emerald-500', 'border-slate-100');
        } else {
            btnPlantilla.classList.replace('border-slate-100', 'border-emerald-500');
            btnVacio.classList.replace('border-blue-500', 'border-slate-100');
        }
    }

    function abrirModalPlantillas() {
        const modal = document.getElementById('modalPlantillas');
        if (!modal) return;

        modal.classList.remove('hidden');
        document.documentElement.classList.add('modal-open');
        document.body.classList.add('modal-open');
    }

    function cerrarModalPlantillas() {
        const modal = document.getElementById('modalPlantillas');
        if (!modal) return;

        modal.classList.add('hidden');
        document.documentElement.classList.remove('modal-open');
        document.body.classList.remove('modal-open');
    }

    function actualizarTextoPlantilla() {
        const select = document.getElementById('select-plantilla-modal');
        const preview = document.getElementById('textoPlantillaPreview');

        if (!select || !preview) return;

        if (select.value) {
            preview.classList.remove('hidden');
            preview.textContent = 'Plantilla seleccionada: ' + select.options[select.selectedIndex].text;
        } else {
            preview.classList.add('hidden');
            preview.textContent = '';
        }
    }

    async function confirmarCargaPlantilla() {
        const select = document.getElementById('select-plantilla-modal');
        if (!select) return;

        if (!select.value) {
            select.focus();
            select.classList.add('border-rose-400', 'ring-2', 'ring-rose-100');

            setTimeout(() => {
                select.classList.remove('border-rose-400', 'ring-2', 'ring-rose-100');
            }, 1500);
            return;
        }

        const btnCargar = document.querySelector('button[onclick="confirmarCargaPlantilla()"]');

        if (btnCargar) {
            btnCargar.innerHTML = '<i data-lucide="loader-2" class="w-4 h-4 animate-spin"></i> Cargando...';
            btnCargar.disabled = true;
            if (typeof lucide !== 'undefined') lucide.createIcons();
        }

        try {
            seleccionarModo('plantilla');

            if (typeof window.cargarPlantillaAjax === 'function') {
                await window.cargarPlantillaAjax(select.value);
            }

            cerrarModalPlantillas();
        } catch (error) {
            console.error(error);
            alert('Error al cargar plantilla');
        } finally {
            setTimeout(() => {
                if (btnCargar) {
                    btnCargar.innerHTML = '<i data-lucide="download" class="w-4 h-4"></i> Cargar plantilla';
                    btnCargar.disabled = false;
                    if (typeof lucide !== 'undefined') lucide.createIcons();
                }
            }, 300);
        }
    }

    document.addEventListener('DOMContentLoaded', function () {
        const selectPlantillaModal = document.getElementById('select-plantilla-modal');

        if (selectPlantillaModal) {
            selectPlantillaModal.addEventListener('change', function (e) {
                if (e.target.value) {
                    seleccionarModo('plantilla');
                }
                actualizarTextoPlantilla();
            });
        }

        if (window.lucide) {
            lucide.createIcons();
        }
    });

    document.addEventListener('keydown', function (event) {
        if (event.key === 'Escape') {
            cerrarModalPlantillas();
        }
    });

    window.seleccionarModo = seleccionarModo;
    window.abrirModalPlantillas = abrirModalPlantillas;
    window.cerrarModalPlantillas = cerrarModalPlantillas;
    window.actualizarTextoPlantilla = actualizarTextoPlantilla;
    window.confirmarCargaPlantilla = confirmarCargaPlantilla;
})();