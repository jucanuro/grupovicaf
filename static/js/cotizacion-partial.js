(function () {
    function handlePlantillaChange(select) {
        const plantillaId = select.value;
        if (!plantillaId) return;

        const baseUrl = window.CotizacionConfig?.urlPlantillaBase || '/servicios/api/plantilla/';

        fetch(`${baseUrl}${plantillaId}/`)
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    const detalles = data.detalles;
                    window.detallesCotizacion = detalles;

                    const inputJson = document.getElementById('detalles_json');
                    if (inputJson) {
                        inputJson.value = JSON.stringify(detalles);
                    }

                    if (typeof renderTablaDetalles === 'function') {
                        renderTablaDetalles(detalles);
                    }
                } else {
                    alert("Error cargando plantilla");
                }
            })
            .catch(error => {
                console.error(error);
                alert("Error en la petición");
            });
    }

    function cargarPlantillaAjax(plantillaId) {
        const selectTemporal = { value: plantillaId };
        handlePlantillaChange(selectTemporal);
    }

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
        document.body.classList.add('overflow-hidden');
    }

    function cerrarModalPlantillas() {
        const modal = document.getElementById('modalPlantillas');
        if (!modal) return;

        modal.classList.add('hidden');
        document.body.classList.remove('overflow-hidden');
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

    function confirmarCargaPlantilla() {
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

        seleccionarModo('plantilla');
        cerrarModalPlantillas();
        cargarPlantillaAjax(select.value);
    }

    document.addEventListener('DOMContentLoaded', function () {
        const selectPlantilla = document.getElementById('select-plantilla');
        if (selectPlantilla) {
            selectPlantilla.addEventListener('change', function (e) {
                if (e.target.value) {
                    seleccionarModo('plantilla');
                }
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

    window.handlePlantillaChange = handlePlantillaChange;
    window.cargarPlantillaAjax = cargarPlantillaAjax;
    window.seleccionarModo = seleccionarModo;
    window.abrirModalPlantillas = abrirModalPlantillas;
    window.cerrarModalPlantillas = cerrarModalPlantillas;
    window.actualizarTextoPlantilla = actualizarTextoPlantilla;
    window.confirmarCargaPlantilla = confirmarCargaPlantilla;
})();