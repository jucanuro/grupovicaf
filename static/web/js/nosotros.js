document.addEventListener("DOMContentLoaded", function () {
    let modalButtons = document.querySelectorAll('[data-modal]');
    modalButtons.forEach(button => {
        button.addEventListener('click', function () {
            const modalId = this.getAttribute('data-modal');
            const modal = document.getElementById(modalId);
            if (modal) {
                modal.classList.remove('hidden');
            }
        });
    });

    let closeModalButtons = document.querySelectorAll('[data-modal-close]');
    closeModalButtons.forEach(button => {
        button.addEventListener('click', function () {
            const modalId = this.getAttribute('data-modal-close');
            const modal = document.getElementById(modalId);
            if (modal) {
                modal.classList.add('hidden');
            }
        });
    });

    window.addEventListener('click', function (e) {
        if (e.target.classList.contains('bg-black')) {
            e.target.classList.add('hidden');
        }
    });
});
