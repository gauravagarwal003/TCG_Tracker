// Transaction Management UI for Pokemon Tracker GitHub Pages
// Full CRUD operations with product search and new product flow

document.addEventListener('DOMContentLoaded', function() {
    initTransactionManager();
});

// Global state
let cachedTransactions = [];
let cachedMappings = [];
let currentEditIndex = null;

async function initTransactionManager() {
    const isTransactionsPage = window.location.pathname.includes('transactions');
    if (!isTransactionsPage) return;

    // Wait for page to be visible (auth may have hidden it)
    await waitForAuth();
    
    // Setup UI
    setupNavButtons();
    
    // Check GitHub auth
    if (!githubAPI.isAuthenticated()) {
        showGitHubAuthPrompt();
    } else {
        await loadAndRenderTransactions();
    }
}

function waitForAuth() {
    return new Promise(resolve => {
        const check = () => {
            if (document.body.style.visibility !== 'hidden') {
                resolve();
            } else {
                setTimeout(check, 100);
            }
        };
        check();
    });
}

function setupNavButtons() {
    // Find or create button container
    let buttonContainer = document.querySelector('.col-md-6.text-end');
    if (!buttonContainer) {
        const header = document.querySelector('.row.mb-3');
        if (header) {
            buttonContainer = document.createElement('div');
            buttonContainer.className = 'col-md-6 text-end';
            header.appendChild(buttonContainer);
        }
    }

    if (buttonContainer) {
        buttonContainer.innerHTML = `
            <button class="btn btn-success me-2" onclick="showAddTransactionModal()" id="addTxBtn" disabled>
                <i class="fas fa-plus me-1"></i>Add Transaction
            </button>
            <button class="btn btn-outline-danger btn-sm" onclick="handleLogout()" id="logoutBtn">
                <i class="fas fa-sign-out-alt me-1"></i>Logout
            </button>
        `;
    }
}

function showGitHubAuthPrompt() {
    const cardBody = document.querySelector('.card-body');
    if (!cardBody) return;

    const authPrompt = document.createElement('div');
    authPrompt.id = 'githubAuthPrompt';
    authPrompt.className = 'alert alert-warning mb-4';
    authPrompt.innerHTML = `
        <div class="d-flex align-items-center">
            <i class="fab fa-github fa-2x me-3"></i>
            <div class="flex-grow-1">
                <strong>GitHub Authentication Required</strong>
                <p class="mb-0 small">To add, edit, or delete transactions, you need to authenticate with GitHub.</p>
            </div>
            <button class="btn btn-dark" onclick="handleGitHubAuth()">
                <i class="fab fa-github me-2"></i>Connect GitHub
            </button>
        </div>
    `;
    
    cardBody.insertBefore(authPrompt, cardBody.firstChild);
}

async function handleGitHubAuth() {
    const success = await githubAPI.authenticate();
    if (success) {
        const prompt = document.getElementById('githubAuthPrompt');
        if (prompt) prompt.remove();
        await loadAndRenderTransactions();
    }
}

function handleLogout() {
    if (confirm('Are you sure you want to logout?')) {
        githubAPI.logout();
    }
}

async function loadAndRenderTransactions() {
    try {
        showLoadingOverlay('Loading transactions...');
        
        // Load data from GitHub
        const [txResult, mapResult] = await Promise.all([
            githubAPI.getTransactions(),
            githubAPI.getMappings()
        ]);
        
        cachedTransactions = txResult.transactions;
        cachedMappings = mapResult.mappings;
        
        // Enable add button
        const addBtn = document.getElementById('addTxBtn');
        if (addBtn) addBtn.disabled = false;
        
        // Add edit/delete buttons to table
        addActionButtonsToTable();
        
        hideLoadingOverlay();
        
    } catch (error) {
        hideLoadingOverlay();
        console.error('Failed to load transactions:', error);
        
        // If auth error, show auth prompt
        if (error.message.includes('Not authenticated')) {
            showGitHubAuthPrompt();
        } else {
            showToast('Error loading transactions: ' + error.message, 'error');
        }
    }
}

function addActionButtonsToTable() {
    const table = document.querySelector('table');
    if (!table) return;

    // Add Actions header
    const headerRow = table.querySelector('thead tr');
    if (headerRow && !headerRow.querySelector('.actions-header')) {
        const th = document.createElement('th');
        th.className = 'actions-header';
        th.style.width = '110px';
        th.textContent = 'Actions';
        headerRow.appendChild(th);
    }

    // Add action buttons to each row
    const rows = table.querySelectorAll('tbody tr');
    rows.forEach((row, index) => {
        // Skip if already has actions
        if (row.querySelector('.action-buttons')) return;
        
        const td = document.createElement('td');
        td.className = 'action-buttons';
        td.innerHTML = `
            <button class="btn btn-sm btn-outline-primary me-1" onclick="showEditTransactionModal(${index})" title="Edit">
                <i class="fas fa-edit"></i>
            </button>
            <button class="btn btn-sm btn-outline-danger" onclick="confirmDeleteTransaction(${index})" title="Delete">
                <i class="fas fa-trash"></i>
            </button>
        `;
        row.appendChild(td);
    });
}

// ===== MODALS =====

function showAddTransactionModal() {
    currentEditIndex = null;
    showTransactionModal(null);
}

function showEditTransactionModal(index) {
    currentEditIndex = index;
    const transaction = cachedTransactions[index];
    showTransactionModal(transaction);
}

function showTransactionModal(transaction) {
    const isEdit = transaction !== null;
    
    // Remove existing modal if any
    const existingModal = document.getElementById('transactionModal');
    if (existingModal) existingModal.remove();

    const modal = document.createElement('div');
    modal.className = 'modal fade';
    modal.id = 'transactionModal';
    modal.setAttribute('data-bs-backdrop', 'static');
    
    modal.innerHTML = `
        <div class="modal-dialog modal-lg">
            <div class="modal-content">
                <div class="modal-header bg-primary text-white">
                    <h5 class="modal-title">
                        <i class="fas ${isEdit ? 'fa-edit' : 'fa-plus'} me-2"></i>
                        ${isEdit ? 'Edit' : 'Add'} Transaction
                    </h5>
                    <button type="button" class="btn-close btn-close-white" data-bs-dismiss="modal"></button>
                </div>
                <div class="modal-body">
                    <form id="transactionForm">
                        <!-- Product Search Section -->
                        <div class="card mb-3">
                            <div class="card-header bg-light">
                                <i class="fas fa-search me-2"></i>Product Selection
                            </div>
                            <div class="card-body">
                                <div class="mb-3">
                                    <label class="form-label">Search Product <span class="text-danger">*</span></label>
                                    <input type="text" class="form-control" id="productSearch" 
                                           placeholder="Type to search existing products..."
                                           value="${transaction?.Item || ''}"
                                           autocomplete="off">
                                    <div id="searchResults" class="list-group position-absolute w-100 shadow" style="z-index: 1000; display: none; max-height: 200px; overflow-y: auto;"></div>
                                </div>
                                
                                <div id="selectedProduct" class="alert alert-success" style="display: ${transaction ? 'block' : 'none'};">
                                    <div class="d-flex align-items-center">
                                        <img id="productImage" src="${getProductImage(transaction)}" 
                                             style="width: 60px; height: 60px; object-fit: contain; margin-right: 15px;"
                                             onerror="this.style.display='none'">
                                        <div>
                                            <strong id="productName">${transaction?.Item || ''}</strong>
                                            <br><small class="text-muted">
                                                Product ID: <span id="displayProductId">${transaction?.product_id || ''}</span> | 
                                                Group ID: <span id="displayGroupId">${transaction?.group_id || ''}</span>
                                            </small>
                                        </div>
                                        <button type="button" class="btn btn-sm btn-outline-secondary ms-auto" onclick="clearSelectedProduct()">
                                            <i class="fas fa-times"></i>
                                        </button>
                                    </div>
                                </div>
                                
                                <div id="newProductToggle" class="text-center mt-2" style="display: ${transaction ? 'none' : 'block'};">
                                    <span class="text-muted">Product not found? </span>
                                    <a href="#" onclick="toggleNewProductForm(); return false;">Add new product</a>
                                </div>
                                
                                <!-- New Product Form (Hidden by default) -->
                                <div id="newProductForm" style="display: none;" class="mt-3 p-3 bg-light rounded">
                                    <h6 class="mb-3"><i class="fas fa-plus-circle me-2"></i>Add New Product</h6>
                                    <div class="row g-3">
                                        <div class="col-12">
                                            <label class="form-label">Product Name <span class="text-danger">*</span></label>
                                            <input type="text" class="form-control" id="newProductName" placeholder="e.g., Prismatic Evolutions Elite Trainer Box">
                                        </div>
                                        <div class="col-md-4">
                                            <label class="form-label">Product ID <span class="text-danger">*</span></label>
                                            <input type="text" class="form-control" id="newProductId" placeholder="e.g., 593355">
                                        </div>
                                        <div class="col-md-4">
                                            <label class="form-label">Group ID <span class="text-danger">*</span></label>
                                            <input type="text" class="form-control" id="newGroupId" placeholder="e.g., 23821">
                                        </div>
                                        <div class="col-md-4">
                                            <label class="form-label">Category ID</label>
                                            <input type="text" class="form-control" id="newCategoryId" placeholder="3" value="3">
                                            <div class="form-text">Usually 3 for Pokemon</div>
                                        </div>
                                        <div class="col-12">
                                            <button type="button" class="btn btn-primary" onclick="confirmNewProduct()">
                                                <i class="fas fa-check me-2"></i>Use This Product
                                            </button>
                                            <button type="button" class="btn btn-outline-secondary ms-2" onclick="toggleNewProductForm()">
                                                Cancel
                                            </button>
                                        </div>
                                    </div>
                                    <div class="alert alert-info mt-3 small">
                                        <i class="fas fa-info-circle me-2"></i>
                                        Find Product ID and Group ID on TCGPlayer URL:<br>
                                        <code>tcgplayer.com/product/<strong>[PRODUCT_ID]</strong>/...</code><br>
                                        Group ID is in the API or can be found in product category pages.
                                    </div>
                                </div>
                                
                                <!-- Hidden fields for product data -->
                                <input type="hidden" id="productId" value="${transaction?.product_id || ''}">
                                <input type="hidden" id="groupId" value="${transaction?.group_id || ''}">
                                <input type="hidden" id="itemName" value="${transaction?.Item || ''}">
                            </div>
                        </div>
                        
                        <!-- Transaction Details -->
                        <div class="card mb-3">
                            <div class="card-header bg-light">
                                <i class="fas fa-receipt me-2"></i>Transaction Details
                            </div>
                            <div class="card-body">
                                <div class="row g-3">
                                    <div class="col-md-4">
                                        <label class="form-label">Type <span class="text-danger">*</span></label>
                                        <select class="form-select" id="transactionType" required>
                                            <option value="">Select...</option>
                                            <option value="BUY" ${transaction?.['Transaction Type'] === 'BUY' ? 'selected' : ''}>BUY</option>
                                            <option value="SELL" ${transaction?.['Transaction Type'] === 'SELL' ? 'selected' : ''}>SELL</option>
                                            <option value="OPEN" ${transaction?.['Transaction Type'] === 'OPEN' ? 'selected' : ''}>OPEN</option>
                                            <option value="PULL" ${transaction?.['Transaction Type'] === 'PULL' ? 'selected' : ''}>PULL</option>
                                            <option value="TRADE" ${transaction?.['Transaction Type'] === 'TRADE' ? 'selected' : ''}>TRADE</option>
                                        </select>
                                    </div>
                                    <div class="col-md-4">
                                        <label class="form-label">Quantity <span class="text-danger">*</span></label>
                                        <input type="number" step="0.01" class="form-control" id="quantity" 
                                               value="${transaction?.Quantity || '1'}" required>
                                    </div>
                                    <div class="col-md-4">
                                        <label class="form-label">Price Per Unit</label>
                                        <div class="input-group">
                                            <span class="input-group-text">$</span>
                                            <input type="text" class="form-control" id="pricePerUnit" 
                                                   value="${formatPrice(transaction?.['Price Per Unit'])}"
                                                   placeholder="0.00">
                                        </div>
                                    </div>
                                    <div class="col-md-6">
                                        <label class="form-label">Date Purchased <span class="text-danger">*</span></label>
                                        <input type="text" class="form-control" id="datePurchased" 
                                               placeholder="MM/DD/YYYY"
                                               value="${transaction?.['Date Purchased'] || ''}" required>
                                    </div>
                                    <div class="col-md-6">
                                        <label class="form-label">Date Received <span class="text-danger">*</span></label>
                                        <input type="text" class="form-control" id="dateReceived" 
                                               placeholder="MM/DD/YYYY"
                                               value="${transaction?.['Date Recieved'] || ''}" required>
                                    </div>
                                </div>
                            </div>
                        </div>
                        
                        <!-- Purchase Info -->
                        <div class="card mb-3">
                            <div class="card-header bg-light">
                                <i class="fas fa-store me-2"></i>Purchase Info
                            </div>
                            <div class="card-body">
                                <div class="row g-3">
                                    <div class="col-md-6">
                                        <label class="form-label">Store/Place</label>
                                        <input type="text" class="form-control" id="place" 
                                               value="${transaction?.Place || ''}"
                                               placeholder="e.g., Target, Pokemon Center">
                                    </div>
                                    <div class="col-md-6">
                                        <label class="form-label">Method</label>
                                        <select class="form-select" id="method">
                                            <option value="">Select...</option>
                                            <option value="Online" ${transaction?.Method === 'Online' ? 'selected' : ''}>Online</option>
                                            <option value="In-person" ${transaction?.Method === 'In-person' ? 'selected' : ''}>In-person</option>
                                        </select>
                                    </div>
                                    <div class="col-12">
                                        <label class="form-label">Notes</label>
                                        <textarea class="form-control" id="notes" rows="3"
                                                  placeholder="Any additional details...">${transaction?.Notes || ''}</textarea>
                                    </div>
                                </div>
                            </div>
                        </div>
                    </form>
                </div>
                <div class="modal-footer">
                    <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">
                        <i class="fas fa-times me-2"></i>Cancel
                    </button>
                    <button type="button" class="btn btn-success" onclick="saveTransaction()">
                        <i class="fas fa-save me-2"></i>${isEdit ? 'Update' : 'Add'} Transaction
                    </button>
                </div>
            </div>
        </div>
    `;

    document.body.appendChild(modal);
    
    // Initialize search functionality
    setupProductSearch();
    
    // Show modal
    const bsModal = new bootstrap.Modal(modal);
    bsModal.show();
    
    // Cleanup on close
    modal.addEventListener('hidden.bs.modal', () => {
        modal.remove();
    });
}

function getProductImage(transaction) {
    if (!transaction) return '';
    const product = cachedMappings.find(
        m => m.product_id === String(transaction.product_id) && m.group_id === String(transaction.group_id)
    );
    return product?.imageUrl || `https://tcgplayer-cdn.tcgplayer.com/product/${transaction.product_id}_200w.jpg`;
}

function formatPrice(price) {
    if (!price) return '';
    const cleaned = String(price).replace(/[$,]/g, '');
    const num = parseFloat(cleaned);
    return isNaN(num) ? '' : num.toFixed(2);
}

function setupProductSearch() {
    const searchInput = document.getElementById('productSearch');
    const resultsDiv = document.getElementById('searchResults');
    
    if (!searchInput || !resultsDiv) return;
    
    let debounceTimer;
    
    searchInput.addEventListener('input', function() {
        clearTimeout(debounceTimer);
        const query = this.value.trim();
        
        if (query.length < 2) {
            resultsDiv.style.display = 'none';
            return;
        }
        
        debounceTimer = setTimeout(async () => {
            const results = await githubAPI.searchProducts(query);
            
            if (results.length === 0) {
                resultsDiv.innerHTML = `
                    <div class="list-group-item text-muted">
                        No products found. <a href="#" onclick="toggleNewProductForm(); return false;">Add new product</a>
                    </div>
                `;
            } else {
                resultsDiv.innerHTML = results.map(product => `
                    <a href="#" class="list-group-item list-group-item-action" 
                       onclick="selectProduct(${JSON.stringify(product).replace(/"/g, '&quot;')}); return false;">
                        <div class="d-flex align-items-center">
                            <img src="${product.imageUrl}" style="width: 40px; height: 40px; object-fit: contain; margin-right: 10px;"
                                 onerror="this.style.display='none'">
                            <div>
                                <strong>${product.name}</strong>
                                <br><small class="text-muted">ID: ${product.product_id} | Group: ${product.group_id}</small>
                            </div>
                        </div>
                    </a>
                `).join('');
            }
            
            resultsDiv.style.display = 'block';
        }, 300);
    });
    
    // Hide results when clicking outside
    document.addEventListener('click', function(e) {
        if (!searchInput.contains(e.target) && !resultsDiv.contains(e.target)) {
            resultsDiv.style.display = 'none';
        }
    });
}

function selectProduct(product) {
    // Update hidden fields
    document.getElementById('productId').value = product.product_id;
    document.getElementById('groupId').value = product.group_id;
    document.getElementById('itemName').value = product.name;
    
    // Update display
    document.getElementById('productSearch').value = product.name;
    document.getElementById('productName').textContent = product.name;
    document.getElementById('displayProductId').textContent = product.product_id;
    document.getElementById('displayGroupId').textContent = product.group_id;
    document.getElementById('productImage').src = product.imageUrl;
    document.getElementById('productImage').style.display = 'block';
    
    // Show selected product card
    document.getElementById('selectedProduct').style.display = 'block';
    document.getElementById('newProductToggle').style.display = 'none';
    document.getElementById('newProductForm').style.display = 'none';
    document.getElementById('searchResults').style.display = 'none';
}

function clearSelectedProduct() {
    document.getElementById('productId').value = '';
    document.getElementById('groupId').value = '';
    document.getElementById('itemName').value = '';
    document.getElementById('productSearch').value = '';
    document.getElementById('selectedProduct').style.display = 'none';
    document.getElementById('newProductToggle').style.display = 'block';
}

function toggleNewProductForm() {
    const form = document.getElementById('newProductForm');
    const toggle = document.getElementById('newProductToggle');
    
    if (form.style.display === 'none') {
        form.style.display = 'block';
        toggle.style.display = 'none';
    } else {
        form.style.display = 'none';
        toggle.style.display = 'block';
    }
}

function confirmNewProduct() {
    const name = document.getElementById('newProductName').value.trim();
    const productId = document.getElementById('newProductId').value.trim();
    const groupId = document.getElementById('newGroupId').value.trim();
    const categoryId = document.getElementById('newCategoryId').value.trim() || '3';
    
    if (!name || !productId || !groupId) {
        showToast('Please fill in Product Name, Product ID, and Group ID', 'error');
        return;
    }
    
    const imageUrl = `https://tcgplayer-cdn.tcgplayer.com/product/${productId}_200w.jpg`;
    
    const product = {
        name,
        product_id: productId,
        group_id: groupId,
        categoryId: parseInt(categoryId),
        imageUrl,
        url: `https://www.tcgplayer.com/product/${productId}`,
        isNew: true // Flag to add to mappings when saving
    };
    
    selectProduct(product);
    
    // Store the new product flag
    document.getElementById('transactionForm').dataset.newProduct = JSON.stringify(product);
}

async function saveTransaction() {
    const form = document.getElementById('transactionForm');
    
    // Validate required fields
    const productId = document.getElementById('productId').value;
    const groupId = document.getElementById('groupId').value;
    const itemName = document.getElementById('itemName').value;
    const transactionType = document.getElementById('transactionType').value;
    const quantity = document.getElementById('quantity').value;
    const datePurchased = document.getElementById('datePurchased').value;
    const dateReceived = document.getElementById('dateReceived').value;
    
    if (!productId || !groupId || !itemName) {
        showToast('Please select or add a product', 'error');
        return;
    }
    
    if (!transactionType || !quantity || !datePurchased || !dateReceived) {
        showToast('Please fill in all required fields', 'error');
        return;
    }
    
    // Format price
    let priceValue = document.getElementById('pricePerUnit').value.trim();
    if (priceValue && !priceValue.startsWith('$')) {
        priceValue = '$' + parseFloat(priceValue).toFixed(2);
    }
    
    const transaction = {
        'Date Purchased': datePurchased,
        'Date Recieved': dateReceived,
        'Transaction Type': transactionType,
        'Price Per Unit': priceValue,
        'Quantity': quantity,
        'Item': itemName,
        'group_id': groupId,
        'product_id': productId,
        'Method': document.getElementById('method').value,
        'Place': document.getElementById('place').value,
        'Notes': document.getElementById('notes').value
    };
    
    try {
        showLoadingOverlay(currentEditIndex !== null ? 'Updating transaction...' : 'Adding transaction...');
        
        // Check if we need to add a new product to mappings
        if (form.dataset.newProduct) {
            const newProduct = JSON.parse(form.dataset.newProduct);
            await githubAPI.addProduct(
                newProduct.name,
                newProduct.product_id,
                newProduct.group_id,
                newProduct.categoryId
            );
        }
        
        // Save transaction
        if (currentEditIndex !== null) {
            await githubAPI.updateTransaction(currentEditIndex, transaction);
        } else {
            await githubAPI.addTransaction(transaction);
        }
        
        hideLoadingOverlay();
        
        // Close modal
        const modal = bootstrap.Modal.getInstance(document.getElementById('transactionModal'));
        if (modal) modal.hide();
        
        showToast(
            `Transaction ${currentEditIndex !== null ? 'updated' : 'added'} successfully! GitHub Actions will update the data.`,
            'success'
        );
        
        // Reload page after a short delay
        setTimeout(() => window.location.reload(), 2000);
        
    } catch (error) {
        hideLoadingOverlay();
        showToast('Failed to save: ' + error.message, 'error');
    }
}

function confirmDeleteTransaction(index) {
    const transaction = cachedTransactions[index];
    
    if (!confirm(`Delete this transaction?\n\n${transaction?.Item || 'Unknown'}\n${transaction?.['Transaction Type']} - ${transaction?.Quantity} unit(s)`)) {
        return;
    }
    
    deleteTransaction(index);
}

async function deleteTransaction(index) {
    try {
        showLoadingOverlay('Deleting transaction...');
        
        await githubAPI.deleteTransaction(index);
        
        hideLoadingOverlay();
        showToast('Transaction deleted! GitHub Actions will update the data.', 'success');
        
        setTimeout(() => window.location.reload(), 2000);
        
    } catch (error) {
        hideLoadingOverlay();
        showToast('Failed to delete: ' + error.message, 'error');
    }
}

// ===== UI HELPERS =====

function showLoadingOverlay(message) {
    // Remove existing
    hideLoadingOverlay();
    
    const overlay = document.createElement('div');
    overlay.id = 'loadingOverlay';
    overlay.style.cssText = `
        position: fixed;
        top: 0;
        left: 0;
        width: 100%;
        height: 100%;
        background: rgba(0, 0, 0, 0.7);
        z-index: 99999;
        display: flex;
        align-items: center;
        justify-content: center;
    `;
    overlay.innerHTML = `
        <div class="text-center text-white">
            <div class="spinner-border mb-3" role="status" style="width: 3rem; height: 3rem;"></div>
            <div class="fs-5">${message}</div>
        </div>
    `;
    document.body.appendChild(overlay);
}

function hideLoadingOverlay() {
    const overlay = document.getElementById('loadingOverlay');
    if (overlay) overlay.remove();
}

function showToast(message, type = 'info') {
    // Remove existing toasts
    document.querySelectorAll('.toast-container').forEach(t => t.remove());
    
    const colors = {
        success: 'bg-success',
        error: 'bg-danger',
        warning: 'bg-warning',
        info: 'bg-info'
    };
    
    const icons = {
        success: 'fa-check-circle',
        error: 'fa-exclamation-circle',
        warning: 'fa-exclamation-triangle',
        info: 'fa-info-circle'
    };
    
    const container = document.createElement('div');
    container.className = 'toast-container position-fixed top-0 end-0 p-3';
    container.style.zIndex = '99999';
    container.innerHTML = `
        <div class="toast show ${colors[type]} text-white" role="alert">
            <div class="toast-body d-flex align-items-center">
                <i class="fas ${icons[type]} me-2"></i>
                ${message}
                <button type="button" class="btn-close btn-close-white ms-auto" onclick="this.closest('.toast-container').remove()"></button>
            </div>
        </div>
    `;
    
    document.body.appendChild(container);
    
    // Auto-remove after 5 seconds
    setTimeout(() => container.remove(), 5000);
}
