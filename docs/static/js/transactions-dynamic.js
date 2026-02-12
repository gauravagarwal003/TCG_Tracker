// Dynamically loads and renders the transactions table
// Assumes a <tbody id="transactions-tbody"></tbody> in the HTML

async function fetchTransactions() {
    // Try API endpoint first (development server). If that fails, fall back
    // to the static JSON file used by GitHub Pages.
    try {
        const resp = await fetch('/api/transactions');
        if (resp.ok) return await resp.json();
    } catch (e) {
        // ignore and fall back
    }
    try {
        const resp2 = await fetch('data/transactions.json');
        if (resp2.ok) return await resp2.json();
    } catch (e) {
        // ignore
    }
    return [];
}

function renderTransactionsTable(transactions) {
    const tbody = document.getElementById('transactions-tbody');
    if (!tbody) return;
    tbody.innerHTML = '';
    if (!transactions.length) {
        tbody.innerHTML = `<tr><td colspan="10" class="text-center py-4 text-muted">No transactions found.</td></tr>`;
        return;
    }
    for (const [i, tx] of transactions.entries()) {
        // Compose product cell
        let productCell = '';
        if (tx.type === 'TRADE') {
            const out = (tx.items_out || []).map(item => `${item.name} x${item.quantity}`).join(', ');
            const inn = (tx.items_in || []).map(item => `${item.name} x${item.quantity}`).join(', ');
            productCell = `${out} &rarr; ${inn}`;
        } else {
            const items = tx.items || [];
            productCell = items.map(item => `${item.name}${items.length > 1 ? ' x' + item.quantity : ''}`).join(', ');
        }
        // Compose image
        let firstItem = (tx.items && tx.items[0]) || (tx.items_in && tx.items_in[0]) || null;
        let imgCell = firstItem ? `<img src="https://tcgplayer-cdn.tcgplayer.com/product/${firstItem.product_id}_200w.jpg" alt="" class="product-thumb">` : '<div class="product-thumb-placeholder"></div>';
        // Compose type badge
        let typeClass = {
            'BUY': 'bg-primary',
            'SELL': 'bg-success',
            'OPEN': 'bg-warning text-dark',
            'TRADE': 'bg-info',
        }[tx.type] || 'bg-secondary';
        let typeBadge = `<span class="badge ${typeClass}">${tx.type}</span>`;
        // Compose qty
        let qty = tx.type === 'TRADE' ? '-' : ((tx.items && tx.items[0] && tx.items[0].quantity) || '');
        // Compose amount
        let amount = (['BUY','SELL'].includes(tx.type) && tx.amount) ? `$${tx.amount.toFixed(2)}` : '';
        // Compose notes
        let notes = tx.notes ? `<span class="text-muted" title="${tx.notes}" style="cursor: help; display: inline-block; max-width: 150px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;">${tx.notes}</span>` : '';
        // Compose actions (edit/delete)
        let actions = `<div class="d-inline-flex gap-1" role="group">
            <a href="/transactions/edit/${tx.id}" class="btn btn-sm btn-primary rounded" id="editButton">Edit</a>
            <form action="/transactions/delete/${tx.id}" method="post" onsubmit="return confirm('Delete this transaction?');" style="display: inline;">
                <button type="submit" class="btn btn-sm btn-danger rounded" title="Delete">
                    <i class="fas fa-trash-alt"></i>
                </button>
            </form>
        </div>`;
        // Compose row
        tbody.innerHTML += `<tr data-index="${i}">
            <td>${imgCell}</td>
            <td class="text-center">${typeBadge}</td>
            <td class="fw-medium">${productCell}</td>
            <td>${tx.date_received}</td>
            <td class="text-end">${qty}</td>
            <td class="text-end">${amount}</td>
            <td class="d-none toggle-details">${tx.place || ''}</td>
            <td class="d-none toggle-details">${tx.method || ''}</td>
            <td>${notes}</td>
            <td class="action-buttons">${actions}</td>
        </tr>`;
    }
}

document.addEventListener('DOMContentLoaded', async () => {
    const transactions = await fetchTransactions();
    renderTransactionsTable(transactions);
});
