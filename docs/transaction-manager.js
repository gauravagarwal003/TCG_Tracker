// Transaction Management UI for GitHub Pages

document.addEventListener('DOMContentLoaded', function() {
    const isTransactionsPage = window.location.pathname.includes('transactions.html');
    if (!isTransactionsPage) return;

    // Check authentication
    if (!githubAPI.isAuthenticated()) {
        showLoginPrompt();
        return;
    }

    setupTransactionButtons();
    loadTransactionsFromGitHub();
});

function showLoginPrompt() {
    const container = document.querySelector('.card-body');
    const loginHTML = `
        <div class="alert alert-info">
            <h5><i class="fas fa-lock"></i> Authentication Required</h5>
            <p>To add, edit, or delete transactions, you need to authenticate with GitHub.</p>
            <button class="btn btn-primary" onclick="authenticateGitHub()">
                <i class="fab fa-github"></i> Authenticate with GitHub
            </button>
        </div>
    `;
    container.insertAdjacentHTML('afterbegin', loginHTML);
}

function authenticateGitHub() {
    const token = prompt('Enter your GitHub Personal Access Token:\n\nTo create one:\n1. Go to GitHub Settings > Developer Settings\n2. Personal Access Tokens > Tokens (classic)\n3. Generate new token\n4. Grant "repo" scope\n5. Copy and paste here');
    
    if (token) {
        githubAPI.setToken(token);
        window.location.reload();
    }
}

function setupTransactionButtons() {
    // Replace "Edit CSV on GitHub" with "Add Transaction"
    const buttonContainer = document.querySelector('.text-end');
    if (buttonContainer) {
        buttonContainer.innerHTML = `
            <button class="btn btn-primary" onclick="showAddTransactionModal()">
                <i class="fas fa-plus"></i> Add Transaction
            </button>
            <button class="btn btn-outline-secondary btn-sm ms-2" onclick="githubAPI.logout()">
                <i class="fas fa-sign-out-alt"></i> Logout
            </button>
        `;
    }

    // Add edit/delete buttons to table
    addActionButtons();
}

function addActionButtons() {
    const table = document.querySelector('table');
    if (!table) return;

    // Add Actions header if not exists
    const headerRow = table.querySelector('thead tr');
    if (!headerRow.querySelector('th:last-child')?.textContent.includes('Actions')) {
        const th = document.createElement('th');
        th.style.width = '100px';
        th.textContent = 'Actions';
        headerRow.appendChild(th);
    }

    // Add action buttons to each row
    const rows = table.querySelectorAll('tbody tr');
    rows.forEach((row, index) => {
        if (row.querySelector('.btn-group')) return; // Already has buttons

        const td = document.createElement('td');
        td.innerHTML = `
            <div class="btn-group" role="group">
                <button class="btn btn-sm btn-link text-primary p-0 me-2" onclick="editTransaction(${index})" title="Edit">
                    <i class="fas fa-edit"></i>
                </button>
                <button class="btn btn-sm btn-link text-danger p-0" onclick="deleteTransaction(${index})" title="Delete">
                    <i class="fas fa-trash-alt"></i>
                </button>
            </div>
        `;
        row.appendChild(td);
    });
}

async function loadTransactionsFromGitHub() {
    try {
        const { transactions } = await githubAPI.getTransactions();
        window.cachedTransactions = transactions;
        console.log('Loaded transactions from GitHub:', transactions.length);
    } catch (error) {
        console.error('Failed to load transactions:', error);
        alert('Failed to load transactions from GitHub. Please check your token and try again.');
    }
}

function showAddTransactionModal() {
    const modal = createTransactionModal(null);
    document.body.appendChild(modal);
    const bsModal = new bootstrap.Modal(modal);
    bsModal.show();
}

async function editTransaction(index) {
    if (!window.cachedTransactions) {
        await loadTransactionsFromGitHub();
    }
    
    const transaction = window.cachedTransactions[index];
    const modal = createTransactionModal(transaction, index);
    document.body.appendChild(modal);
    const bsModal = new bootstrap.Modal(modal);
    bsModal.show();
}

async function deleteTransaction(index) {
    if (!confirm('Are you sure you want to delete this transaction?')) return;

    try {
        showLoadingOverlay('Deleting transaction...');
        await githubAPI.deleteTransaction(index);
        hideLoadingOverlay();
        alert('Transaction deleted! The page will refresh to show changes.');
        window.location.reload();
    } catch (error) {
        hideLoadingOverlay();
        alert('Failed to delete transaction: ' + error.message);
    }
}

function createTransactionModal(transaction, index) {
    const isEdit = transaction !== null;
    const modalId = 'transactionModal';

    const modal = document.createElement('div');
    modal.className = 'modal fade';
    modal.id = modalId;
    modal.innerHTML = `
        <div class="modal-dialog modal-lg">
            <div class="modal-content">
                <div class="modal-header">
                    <h5 class="modal-title">${isEdit ? 'Edit' : 'Add'} Transaction</h5>
                    <button type="button" class="btn-close" data-bs-dismiss="modal"></button>
                </div>
                <div class="modal-body">
                    <form id="transactionForm">
                        <div class="row mb-3">
                            <div class="col-md-12">
                                <label class="form-label">Product Name *</label>
                                <input type="text" class="form-control" id="item" value="${transaction?.Item || ''}" required>
                            </div>
                        </div>
                        
                        <div class="row mb-3">
                            <div class="col-md-6">
                                <label class="form-label">Product ID</label>
                                <input type="text" class="form-control" id="product_id" value="${transaction?.product_id || ''}">
                            </div>
                            <div class="col-md-6">
                                <label class="form-label">Group ID</label>
                                <input type="text" class="form-control" id="group_id" value="${transaction?.group_id || ''}">
                            </div>
                        </div>

                        <div class="row mb-3">
                            <div class="col-md-6">
                                <label class="form-label">Transaction Type *</label>
                                <select class="form-select" id="transaction_type" required>
                                    <option value="">Select Type</option>
                                    <option value="BUY" ${transaction?.['Transaction Type'] === 'BUY' ? 'selected' : ''}>BUY</option>
                                    <option value="SELL" ${transaction?.['Transaction Type'] === 'SELL' ? 'selected' : ''}>SELL</option>
                                    <option value="OPEN" ${transaction?.['Transaction Type'] === 'OPEN' ? 'selected' : ''}>OPEN</option>
                                </select>
                            </div>
                            <div class="col-md-6">
                                <label class="form-label">Quantity *</label>
                                <input type="number" step="0.01" class="form-control" id="quantity" value="${transaction?.Quantity || ''}" required>
                            </div>
                        </div>

                        <div class="row mb-3">
                            <div class="col-md-6">
                                <label class="form-label">Date Purchased *</label>
                                <input type="text" class="form-control" id="date_purchased" placeholder="MM/DD/YYYY" value="${transaction?.['Date Purchased'] || ''}" required>
                            </div>
                            <div class="col-md-6">
                                <label class="form-label">Date Received *</label>
                                <input type="text" class="form-control" id="date_received" placeholder="MM/DD/YYYY" value="${transaction?.['Date Recieved'] || ''}" required>
                            </div>
                        </div>

                        <div class="row mb-3">
                            <div class="col-md-6">
                                <label class="form-label">Price Per Unit</label>
                                <input type="text" class="form-control" id="price" placeholder="$0.00" value="${transaction?.['Price Per Unit'] || ''}">
                            </div>
                            <div class="col-md-6">
                                <label class="form-label">Store/Place</label>
                                <input type="text" class="form-control" id="place" value="${transaction?.Place || ''}">
                            </div>
                        </div>

                        <div class="row mb-3">
                            <div class="col-md-6">
                                <label class="form-label">Method</label>
                                <select class="form-select" id="method">
                                    <option value="">Select Method</option>
                                    <option value="Online" ${transaction?.Method === 'Online' ? 'selected' : ''}>Online</option>
                                    <option value="In-person" ${transaction?.Method === 'In-person' ? 'selected' : ''}>In-person</option>
                                </select>
                            </div>
                        </div>

                        <div class="row mb-3">
                            <div class="col-md-12">
                                <label class="form-label">Notes</label>
                                <textarea class="form-control" id="notes" rows="3">${transaction?.Notes || ''}</textarea>
                            </div>
                        </div>
                    </form>
                </div>
                <div class="modal-footer">
                    <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">Cancel</button>
                    <button type="button" class="btn btn-success" onclick="saveTransaction(${isEdit ? index : 'null'})">
                        <i class="fas fa-save"></i> ${isEdit ? 'Update' : 'Add'} Transaction
                    </button>
                </div>
            </div>
        </div>
    `;

    return modal;
}

async function saveTransaction(index) {
    const form = document.getElementById('transactionForm');
    if (!form.checkValidity()) {
        form.reportValidity();
        return;
    }

    const transaction = {
        'Date Purchased': document.getElementById('date_purchased').value,
        'Date Recieved': document.getElementById('date_received').value,
        'Transaction Type': document.getElementById('transaction_type').value,
        'Price Per Unit': document.getElementById('price').value,
        'Quantity': document.getElementById('quantity').value,
        'Item': document.getElementById('item').value,
        'group_id': document.getElementById('group_id').value,
        'product_id': document.getElementById('product_id').value,
        'Method': document.getElementById('method').value,
        'Place': document.getElementById('place').value,
        'Notes': document.getElementById('notes').value
    };

    try {
        showLoadingOverlay(index === null ? 'Adding transaction...' : 'Updating transaction...');
        
        if (index === null) {
            await githubAPI.addTransaction(transaction);
        } else {
            await githubAPI.updateTransaction(index, transaction);
        }
        
        hideLoadingOverlay();
        
        // Close modal
        const modal = bootstrap.Modal.getInstance(document.getElementById('transactionModal'));
        modal.hide();
        
        alert('Transaction saved! GitHub Actions will update the data shortly. The page will refresh.');
        window.location.reload();
    } catch (error) {
        hideLoadingOverlay();
        alert('Failed to save transaction: ' + error.message);
    }
}

function showLoadingOverlay(message) {
    const overlay = document.createElement('div');
    overlay.id = 'loadingOverlay';
    overlay.style.cssText = 'position:fixed;top:0;left:0;width:100%;height:100%;background:rgba(0,0,0,0.7);z-index:9999;display:flex;align-items:center;justify-content:center;';
    overlay.innerHTML = `
        <div class="text-center text-white">
            <div class="spinner-border mb-3" role="status"></div>
            <div>${message}</div>
        </div>
    `;
    document.body.appendChild(overlay);
}

function hideLoadingOverlay() {
    const overlay = document.getElementById('loadingOverlay');
    if (overlay) overlay.remove();
}
