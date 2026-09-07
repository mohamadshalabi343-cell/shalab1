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

// دالة البحث الفوري (تم نقلها إلى index.html ولكن نتركها هنا للاستخدام العام)
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

// تحويل رسائل الفلاش التقليدية إلى Toasts (عند تحميل الصفحة)
document.addEventListener('DOMContentLoaded', function() {
    // تفعيل حساب الربح في نماذج الإضافة والتعديل
    if (document.getElementById('cost') && document.getElementById('amount_received')) {
        calculateProfit('cost', 'amount_received', 'profit_preview');
    }

    // تحويل رسائل الفلاش إلى Toasts (إذا وجدت)
    const alerts = document.querySelectorAll('.alert');
    alerts.forEach(alert => {
        // نأخذ النص وننشئ توست بدلاً من التنبيه
        const message = alert.textContent.trim();
        const isSuccess = alert.classList.contains('alert-success');
        const bgColor = isSuccess ? 'bg-success' : 'bg-danger';
        
        // إنشاء عنصر التوست
        const toastHTML = `
            <div class="toast align-items-center text-white ${bgColor} border-0 show" role="alert" aria-live="assertive" aria-atomic="true" style="min-width: 250px;">
                <div class="d-flex">
                    <div class="toast-body">
                        ${message}
                    </div>
                    <button type="button" class="btn-close btn-close-white me-2 m-auto" data-bs-dismiss="toast"></button>
                </div>
            </div>
        `;
        // إضافة التوست إلى الحاوية
        const container = document.getElementById('toast-container');
        if (container) {
            container.innerHTML += toastHTML;
        }
        // إخفاء التنبيه الأصلي
        alert.style.display = 'none';
    });

    // إغلاق التوستات تلقائياً بعد 5 ثوانٍ
    setTimeout(() => {
        document.querySelectorAll('.toast').forEach(toast => {
            const bsToast = bootstrap.Toast.getInstance(toast);
            if (bsToast) bsToast.hide();
        });
    }, 5000);
});
