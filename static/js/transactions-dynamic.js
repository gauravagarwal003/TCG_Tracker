// Dynamically loads and renders the transactions table from Firestore.
// Assumes a <tbody id="transactions-tbody"></tbody> in the HTML.

let currentUser = null;

function ensureFirestore() {
    if (!window.TCGFirestore) {
        throw new Error('Firestore helpers not loaded');
    }
    return window.TCGFirestore;
}

function setupNavbarAuth() {
    const logoutBtn = document.getElementById('logoutBtn');
    const userInfo = document.getElementById('userInfo');
    const userEmail = document.getElementById('userEmail');

    if (logoutBtn) {
        logoutBtn.addEventListener('click', async () => {
            if (window.TCGAuth) {
                await window.TCGAuth.logout();
                window.location.reload();
            }
        });
    }

    if (window.TCGAuth) {
        window.TCGAuth.onAuthStateChange((user) => {
            currentUser = user;
            if (user) {
                if (userEmail) userEmail.textContent = user.email || user.uid;
                if (userInfo) userInfo.style.display = 'flex';
                loadAndRenderTransactions();
            } else if (userInfo) {
                userInfo.style.display = 'none';
            }
        });
    }
}

async function deleteTransactionFirestore(txnId) {
    const firestore = ensureFirestore();
    if (!currentUser) {
        alert('You must be signed in to delete transactions.');
        return false;
    }
    try {
        await firestore.deleteTransaction(currentUser.uid, txnId);
        return true;
    } catch (err) {
        alert('Failed to delete: ' + (err?.message || err));
        return false;
    }
}

function renderTransactionsTable(transactions) {
    const tbody = document.getElementById('transactions-tbody');
    if (!tbody) return;
    tbody.innerHTML = '';
    if (!transactions.length) {
        tbody.innerHTML = `<tr><td colspan="10" class="text-center py-4 text-muted">No transactions found.</td></tr>`;
        return;
    }
    // Preserve original order index so table-init can restore it if needed
    transactions = transactions.map((t, idx) => ({...t, _originalIndex: idx}));

    // Ensure transactions are shown newest-first by `date_received`
    transactions.sort((a, b) => {
        const da = new Date(a.date_received);
        const db = new Date(b.date_received);
        return db - da; // descending
    });

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
        // Compose actions (edit/delete) for Firestore-backed mode.
        const actions = `<div class="d-inline-flex gap-1" role="group">
            <a href="add-transaction.html?edit=1&id=${tx.id}" class="btn btn-sm btn-primary rounded">Edit</a>
            <button type="button" class="btn btn-sm btn-danger rounded delete-txn-btn"
                    data-txn-id="${tx.id}" title="Delete">
                <i class="fas fa-trash-alt"></i>
            </button>
        </div>`;
        // Compose row
        tbody.innerHTML += `<tr data-original-index="${tx._originalIndex}" data-index="${i}">
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

    // Mark the Date header as sorted descending so the UI reflects default order
    try {
        const table = document.querySelector('table');
        if (table) {
            const headers = Array.from(table.querySelectorAll('th'));
            const dateIndex = headers.findIndex(h => h.textContent.includes('Date'));
            if (dateIndex !== -1) {
                const header = headers[dateIndex];
                header.setAttribute('data-order', 'desc');
                const icon = header.querySelector('.fas');
                if (icon) icon.className = 'fas fa-sort-down text-primary ms-1 small';
            }
        }
    } catch (e) {}
}

async function loadAndRenderTransactions() {
    if (!currentUser) return;
    try {
        const firestore = ensureFirestore();
        await firestore.ensureLegacyDataSeeded(currentUser);
        const transactions = await firestore.getUserTransactions(currentUser.uid);
        renderTransactionsTable(transactions);
    } catch (error) {
        console.error('Failed to load Firestore transactions:', error);
        const tbody = document.getElementById('transactions-tbody');
        if (tbody) {
            tbody.innerHTML = '<tr><td colspan="10" class="text-center py-4 text-danger">Failed to load transactions.</td></tr>';
        }
    }
}

document.addEventListener('DOMContentLoaded', () => {
    setupNavbarAuth();
});

// Delegated handler for delete buttons (rendered after DOMContentLoaded)
document.addEventListener('click', async (e) => {
    const btn = e.target.closest('.delete-txn-btn');
    if (!btn) return;
    const txnId = btn.dataset.txnId;
    if (!confirm('Delete this transaction? This cannot be undone.')) return;
    btn.disabled = true;
    btn.innerHTML = '<span class="spinner-border spinner-border-sm"></span>';
    const ok = await deleteTransactionFirestore(txnId);
    if (ok) {
        const row = btn.closest('tr');
        if (row) row.remove();
        alert('Transaction deleted.');
    } else {
        btn.disabled = false;
        btn.innerHTML = '<i class="fas fa-trash-alt"></i>';
    }
});
