function confirmDelete(message) {
    return confirm(message || 'هل أنت متأكد من الحذف؟');
}

function calculateProfit(costId, receivedId, previewId) {
    const costInput = document.getElementById(costId);
    const receivedInput = document.getElementById(receivedId);
    const previewElement = document.getElementById(previewId);

    if (!costInput || !receivedInput || !previewElement) return;

    function updateProfit() {
        const cost = parseFloat(costInput.value) || 0;
        const received = parseFloat(receivedInput.value) || 0;
        const profit = received - cost;

        previewElement.textContent = profit.toFixed(0) + ' ل.س';

        if (profit >= 0) {
            previewElement.className = 'badge bg-success fs-6';
        } else {
            previewElement.className = 'badge bg-danger fs-6';
        }
    }

    costInput.addEventListener('input', updateProfit);
    receivedInput.addEventListener('input', updateProfit);

    updateProfit();
}

function formatCurrency(amount) {
    return amount.toFixed(0) + ' ل.س';
}

function filterTable(inputId, tableId) {
    const input = document.getElementById(inputId);
    const table = document.getElementById(tableId);

    if (!input || !table) return;

    input.addEventListener('keyup', function() {
        const filter = this.value.toLowerCase();
        const rows = table.querySelectorAll('tbody tr');

        rows.forEach(row => {
            const text = row.textContent.toLowerCase();
            row.style.display = text.includes(filter) ? '' : 'none';
        });
    });
}

document.addEventListener('DOMContentLoaded', function() {
    if (document.getElementById('cost') && document.getElementById('amount_received')) {
        calculateProfit('cost', 'amount_received', 'profit_preview');
    }

    const alerts = document.querySelectorAll('.alert');
    alerts.forEach(alert => {
        setTimeout(() => {
            const bsAlert = new bootstrap.Alert(alert);
            bsAlert.close();
        }, 5000);
    });
});