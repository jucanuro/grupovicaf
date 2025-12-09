document.addEventListener('DOMContentLoaded', () => {
    if (typeof lucide !== 'undefined') {
        lucide.createIcons();
    }
    
    const projectsListView = document.getElementById('projects-list-view');
    const samplesView = document.getElementById('samples-view');
    const samplesHistoryList = document.getElementById('samples-history-list');
    const registerSampleForm = document.getElementById('register-sample-form');

    const searchInput = document.getElementById('search-input');
    const table = document.getElementById('projects-table');
    const rows = table ? table.getElementsByTagName('tr') : [];
    
    if (searchInput) {
        searchInput.addEventListener('keyup', (e) => {
            const filter = e.target.value.toLowerCase();
            for (let i = 1; i < rows.length; i++) {
                const row = rows[i];
                const cells = row.getElementsByTagName('td');
                const projectText = cells[0].textContent || cells[0].innerText;
                const clientText = cells[1].textContent || cells[1].innerText;
                
                if (projectText.toLowerCase().indexOf(filter) > -1 || clientText.toLowerCase().indexOf(filter) > -1) {
                    row.style.display = "";
                } else {
                    row.style.display = "none";
                }
            }
        });
    }

    const backToProjectsBtn = document.getElementById('back-to-projects-btn');
    const registerSamplesBtns = document.querySelectorAll('.register-samples-btn');
    
    registerSamplesBtns.forEach(button => {
        button.addEventListener('click', async (e) => {
            e.preventDefault();
            const row = e.target.closest('tr');
            const projectId = row.dataset.id;
            const totalSamples = parseInt(row.dataset.muestras);
            const projectName = row.dataset.nombre;
            
            document.getElementById('total-samples-display').textContent = totalSamples;
            document.getElementById('samples-project-name').textContent = projectName;
            document.getElementById('register-project-id').value = projectId;

            projectsListView.style.display = 'none';
            samplesView.style.display = 'block';

            await loadSamplesHistory(projectId);
        });
    });

    function toggleSampleRegistrationForm(isComplete, totalSamples, registeredCount) {
        const form = document.getElementById('register-sample-form');
        const submitButton = form.querySelector('button[type="submit"]');
        const inputs = form.querySelectorAll('input:not([type="hidden"]), textarea, select');
        const header = document.querySelector('#samples-view .glass-card h2');

        if (isComplete) {
            inputs.forEach(input => input.disabled = true);
            
            submitButton.disabled = true;
            submitButton.innerHTML = `<i data-lucide="lock" class="w-5 h-5 inline-block mr-2"></i> Límite (${registeredCount} de ${totalSamples}) Alcanzado`;
            submitButton.classList.remove('bg-green-500', 'hover:bg-green-600', 'bg-red-700'); 
            submitButton.classList.add('bg-gray-600', 'cursor-not-allowed');

            if (!header.dataset.originalText) {
                header.dataset.originalText = header.textContent;
            }
            header.textContent = 'Registro de Muestras Completado';

        } else {
            inputs.forEach(input => input.disabled = false);

            submitButton.disabled = false;
            submitButton.innerHTML = `<i data-lucide="plus" class="w-5 h-5 inline-block mr-2"></i> Guardar Muestra`;
            submitButton.classList.remove('bg-gray-600', 'cursor-not-allowed', 'bg-red-700');
            submitButton.classList.add('bg-green-500', 'hover:bg-green-600');
            
            if (header.dataset.originalText) {
                header.textContent = header.dataset.originalText;
            } else {
                 header.textContent = 'Registrar Nueva Muestra'; 
            }
        }
        lucide.createIcons();
    }
    
    async function loadSamplesHistory(projectId) {
        try {
            const response = await fetch(`/proyectos/muestras/${projectId}/`);
            const data = await response.json();
            
            samplesHistoryList.innerHTML = '';
            const registeredCount = data.muestras.length;
            const totalSamples = parseInt(document.getElementById('total-samples-display').textContent);
            
            if (registeredCount > 0) {
                data.muestras.forEach(sample => {
                    renderSampleItem(sample);
                });
            } else {
                samplesHistoryList.innerHTML = `<p class="text-slate-400 text-center text-lg">No hay muestras registradas para este proyecto aún.</p>`;
            }
            
            document.getElementById('registered-samples-display').textContent = registeredCount;
            document.getElementById('pending-samples-display').textContent = totalSamples - registeredCount;
            
            if (registeredCount >= totalSamples) {
                toggleSampleRegistrationForm(true, totalSamples, registeredCount);
            } else {
                toggleSampleRegistrationForm(false, totalSamples, registeredCount);
            }
            
            lucide.createIcons();

        } catch (error) {
            console.error('Error al cargar las muestras:', error);
            showCustomModal('Error al cargar las muestras', 'Hubo un error al cargar las muestras. Por favor, intente de nuevo.', 'error');
        }
    }

    if (backToProjectsBtn) {
        backToProjectsBtn.addEventListener('click', () => {
            samplesView.style.display = 'none';
            projectsListView.style.display = 'block';
        });
    }
    
    if (registerSampleForm) {
        registerSampleForm.addEventListener('submit', async (e) => {
            e.preventDefault();
            
            const totalSamples = parseInt(document.getElementById('total-samples-display').textContent);
            const projectId = document.getElementById('register-project-id').value;
            const registeredCount = parseInt(document.getElementById('registered-samples-display').textContent);

            if (registeredCount >= totalSamples) {
                const message = `¡Ya se han registrado todas las muestras para este proyecto! (${registeredCount} de ${totalSamples}) 🚫`;
                showCustomModal('Límite Alcanzado', message, 'warning');
                return;
            }

            const formData = new FormData(registerSampleForm);
            const sampleData = Object.fromEntries(formData.entries());

            const masaAproxKgValue = sampleData['masa_aprox_kg'];
            if (masaAproxKgValue && masaAproxKgValue.trim() !== '') {
                sampleData['masa_aprox_kg'] = parseFloat(masaAproxKgValue.replace(',', '.'));
                if (isNaN(sampleData['masa_aprox_kg'])) {
                    showCustomModal('Error de Formato', 'La masa debe ser un número válido.', 'error');
                    return; 
                }
            } else {
                delete sampleData['masa_aprox_kg'];
            }

            const dateFields = ['fecha_recepcion', 'fecha_fabricacion', 'fecha_ensayo_rotura', 'fecha_informe'];
            let hasDateError = false;

            dateFields.forEach(field => {
                const dateValue = sampleData[field];
                if (dateValue && dateValue.trim() !== '') {
                    const parts = dateValue.split('/');
                    if (parts.length === 3 && parts[0].length === 2 && parts[1].length === 2 && parts[2].length === 4) {
                        sampleData[field] = `${parts[2]}-${parts[1]}-${parts[0]}`;
                    } else if (dateValue.length === 10 && dateValue.includes('-')) {
                         sampleData[field] = dateValue;
                    } else {
                        showCustomModal('Error de Fecha', `El campo ${field} tiene un formato de fecha inválido. Use DD/MM/YYYY.`, 'error');
                        hasDateError = true;
                        return;
                    }
                } else {
                    sampleData[field] = null;
                }
            });

            if (hasDateError) {
                return;
            }

            sampleData['proyecto_id'] = projectId;

            try {
                const response = await fetch('/proyectos/crear-muestra/', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                    },
                    body: JSON.stringify(sampleData)
                });

                const result = await response.json();

                if (response.ok) {
                    const placeholder = samplesHistoryList.querySelector('p');
                    if (placeholder && placeholder.textContent.includes('No hay muestras registradas')) {
                        samplesHistoryList.innerHTML = '';
                    }

                    renderSampleItem(result.muestra);
                    
                    const newRegisteredCount = registeredCount + 1;
                    document.getElementById('registered-samples-display').textContent = newRegisteredCount;
                    document.getElementById('pending-samples-display').textContent = totalSamples - newRegisteredCount;

                    lucide.createIcons();
                    registerSampleForm.reset();
                    updateProjectStatusInTable(projectId, newRegisteredCount, totalSamples);
                    
                    if (newRegisteredCount >= totalSamples) {
                        toggleSampleRegistrationForm(true, totalSamples, newRegisteredCount);
                    } else {
                        toggleSampleRegistrationForm(false, totalSamples, newRegisteredCount);
                    }
                    
                    const nuevaMuestraId = result.muestra.id;
                    const redirectUrl = `/proyectos/solicitudes/registro/${nuevaMuestraId}/`;
                    
                    showCustomModal(
                        'Muestra Registrada', 
                        result.message + ' Redirigiendo automáticamente para registrar la Solicitud de Ensayo...', 
                        'success',
                        () => window.location.href = redirectUrl
                    );
                    
                } else {
                    showCustomModal('Error al Guardar', 'Error: ' + result.message, 'error');
                }

            } catch (error) {
                console.error('Error al guardar la muestra:', error);
                showCustomModal('Error de Conexión', 'Hubo un error al conectar con el servidor. Por favor, intente de nuevo.', 'error');
            }
        });
    }

    function renderSampleItem(sample) {
        const newSampleItem = document.createElement('li');
        newSampleItem.className = 'flex items-center gap-4 p-4 bg-slate-700/50 rounded-lg text-slate-300 transition-transform duration-200 hover:scale-[1.02]';
        
        const muestraId = sample.id; 
        
        const registroSolicitudUrl = `/proyectos/solicitudes/registro/${muestraId}/`;
        
        const solicitudYaRegistrada = sample.orden_ensayo_id !== null;
        
        const linkClasses = solicitudYaRegistrada 
            ? 'bg-purple-500/20 text-purple-300 hover:bg-purple-500/40 hover:scale-110'
            : 'bg-blue-500/20 text-blue-300 hover:bg-blue-500/40 hover:scale-110';
            
        const linkTitle = solicitudYaRegistrada 
            ? 'Ver/Editar Solicitud de Ensayo (Registrada)' 
            : 'Registrar Nueva Solicitud de Ensayo';

        newSampleItem.innerHTML = `
            <i data-lucide="flask-conical" class="text-purple-400 w-6 h-6 flex-shrink-0"></i>
            <div class="flex-grow">
                <p class="font-semibold text-white">${sample.codigo_muestra}</p>
                <p class="text-sm text-slate-400">Recepción: ${sample.fecha_recepcion} | Estado: ${sample.estado}</p>
            </div>
            
            <div class="card-acciones">
                <a href="${registroSolicitudUrl}" 
                title="${linkTitle}" 
                class="p-2 rounded-full transition-colors transform ${linkClasses}">
                    
                    <svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" data-lucide="scroll-text" class="lucide lucide-scroll-text w-5 h-5">
                        <path d="M15 12h-5"></path>
                        <path d="M15 8h-5"></path>
                        <path d="M19 17V5a2 2 0 0 0-2-2H4"></path>
                        <path d="M8 21h12a2 2 0 0 0 2-2v-1a1 1 0 0 0-1-1H11a1 1 0 0 0-1 1v1a2 2 0 1 1-4 0V5a2 2 0 1 0-4 0v2a1 1 0 0 0 1 1h3"></path>
                    </svg>
                </a> 
            </div>
        `;
        samplesHistoryList.appendChild(newSampleItem);
    }
    
    function updateProjectStatusInTable(projectId, registered, total) {
        const row = document.querySelector(`tr[data-id="${projectId}"]`);
        if (row) {
            const statusCell = row.querySelector('td:nth-child(5) span');
            
            let newStatus = 'PENDIENTE'; 
            let statusColorClass = 'bg-yellow-500/20 text-yellow-300';
            
            if (registered > 0 && registered < total) {
                newStatus = 'EN RECEPCIÓN'; 
                statusColorClass = 'bg-blue-500/20 text-blue-300';
            } else if (registered === total) {
                newStatus = 'LISTO P/ ENSAYO'; 
                statusColorClass = 'bg-purple-500/20 text-purple-300';
            }
            
            statusCell.textContent = newStatus;
            statusCell.className = `px-3 py-1 inline-flex text-xs leading-5 font-semibold rounded-full ${statusColorClass}`;
            
            row.dataset.estado = newStatus;
        }
    }
    
    function showCustomModal(title, message, type, onConfirm = null) {
        const existingModal = document.querySelector('.fixed.inset-0.bg-black.bg-opacity-50.z-50');
        if (existingModal) {
            existingModal.remove();
        }

        let icon, color;
        switch(type) {
            case 'success':
                icon = 'check-circle';
                color = 'text-green-400';
                break;
            case 'error':
                icon = 'x-circle';
                color = 'text-red-400';
                break;
            case 'warning':
                icon = 'alert-triangle';
                color = 'text-yellow-400';
                break;
            default:
                icon = 'info';
                color = 'text-blue-400';
        }

        const modal = document.createElement('div');
        modal.className = 'fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center p-4 z-50 animate-fade-in-up backdrop-blur-sm';
        modal.innerHTML = `
            <div class="glass-card p-8 rounded-2xl shadow-xl w-full max-w-sm text-center border border-slate-600/50 transform transition-transform duration-300">
                <i data-lucide="${icon}" class="w-12 h-12 inline-block mb-3 ${color}"></i>
                <h3 class="text-white text-2xl font-bold mb-2">${title}</h3>
                <p class="text-slate-300 mb-4">${message}</p>
                <button id="modal-ok-btn" class="mt-4 px-6 py-2 bg-blue-500 text-white font-semibold rounded-full hover:bg-blue-600 transition-colors transform hover:scale-105 shadow-lg">OK</button>
            </div>
        `;
        document.body.appendChild(modal);
        lucide.createIcons();
        
        document.getElementById('modal-ok-btn').addEventListener('click', () => {
            modal.remove();
            if (onConfirm && typeof onConfirm === 'function') {
                onConfirm();
            }
        });
    }

});