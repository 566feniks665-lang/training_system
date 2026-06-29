document.addEventListener("DOMContentLoaded", function () {
    initFlashMessages();
    initDeleteConfirm();
    initAutoHideAlerts();
    initRequiredMark();
});

function initFlashMessages() {
    const alerts = document.querySelectorAll(".alert");
    alerts.forEach(function (alert) {
        alert.addEventListener("click", function () {
            alert.style.display = "none";
        });
    });
}

function initDeleteConfirm() {
    const deleteForms = document.querySelectorAll('form[data-confirm="delete"]');

    deleteForms.forEach(function (form) {
        form.addEventListener("submit", function (event) {
            const message =
                form.getAttribute("data-confirm-message") ||
                "Вы уверены, что хотите удалить эту запись?";

            const confirmed = window.confirm(message);
            if (!confirmed) {
                event.preventDefault();
            }
        });
    });
}

function initAutoHideAlerts() {
    const alerts = document.querySelectorAll(".alert");

    alerts.forEach(function (alert) {
        setTimeout(function () {
            alert.style.transition = "opacity 0.3s ease";
            alert.style.opacity = "0";

            setTimeout(function () {
                alert.style.display = "none";
            }, 300);
        }, 4000);
    });
}

function initRequiredMark() {
    const requiredFields = document.querySelectorAll(
        'input[required], textarea[required], select[required]'
    );

    requiredFields.forEach(function (field) {
        const row = field.closest(".form-row");
        if (!row) {
            return;
        }

        const label = row.querySelector("label");
        if (!label) {
            return;
        }

        if (!label.dataset.requiredAdded) {
            label.innerHTML += ' <span style="color:#c94141;">*</span>';
            label.dataset.requiredAdded = "true";
        }
    });
}