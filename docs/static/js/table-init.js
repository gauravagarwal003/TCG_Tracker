document.addEventListener('DOMContentLoaded', function () {
    const table = document.querySelector('table');
    if (!table) return;

    // Store original order
    const tbody = table.querySelector('tbody');
    const rows = Array.from(tbody.querySelectorAll('tr'));
    rows.forEach((row, index) => {
        row.setAttribute('data-original-index', index);
    });

    // --- 1. Client-Side Sorting ---
    const headers = table.querySelectorAll('th');
    headers.forEach((header, index) => {
        // Skip sorting for Actions column or explicit no-sort
        if (header.innerText.toLowerCase().includes('actions') || header.classList.contains('no-sort')) return;

        header.style.cursor = 'pointer';
        header.addEventListener('click', () => {
            sortTable(table, index);
        });
        // Add a sort icon
        header.innerHTML += ' <i class="fas fa-sort text-muted ms-1 small" style="opacity: 0.5;"></i>';
    });

    // --- 2. ID Toggle ---
    const toggleBtn = document.getElementById('toggleIdsBtn');
    if (toggleBtn) {
        toggleBtn.addEventListener('click', function() {
            const elements = document.querySelectorAll('.toggle-id');
            const isHidden = elements[0].classList.contains('d-none');
            
            elements.forEach(el => {
                if (isHidden) {
                    el.classList.remove('d-none');
                } else {
                    el.classList.add('d-none');
                }
            });
            
            this.textContent = isHidden ? 'Hide IDs' : 'Show IDs';
        });
    }

    // --- 2b. Store/Method Toggle ---
    const toggleDetailsBtn = document.getElementById('toggleDetailsBtn');
    if (toggleDetailsBtn) {
        toggleDetailsBtn.addEventListener('click', function() {
            const elements = document.querySelectorAll('.toggle-details');
            const isHidden = elements[0].classList.contains('d-none');
            
            elements.forEach(el => {
                if (isHidden) {
                    el.classList.remove('d-none');
                } else {
                    el.classList.add('d-none');
                }
            });
            
            this.textContent = isHidden ? 'Hide Store/Method' : 'Show Store/Method';
        });
    }

    // --- 3. Shopping Interface Filters ---
    const searchInput = document.getElementById('globalSearch');
    const typeFilter = document.getElementById('typeFilter');
    
    // Bind events if elements exist
    if (searchInput) {
        searchInput.addEventListener('keyup', () => filterData(table));
    }
    if (typeFilter) {
        typeFilter.addEventListener('change', () => filterData(table));
    }

    // --- 4. Apply Default Sorting ---
    // For holdings table (has Total Value column), sort by Total Value descending
    // For transactions table (has Date column), sort by Date descending
    applyDefaultSort(table);
    
    // Initialize tooltips
    var tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'));
    var tooltipList = tooltipTriggerList.map(function (tooltipTriggerEl) {
        return new bootstrap.Tooltip(tooltipTriggerEl);
    });
});

function applyDefaultSort(table) {
    const headers = Array.from(table.querySelectorAll('th'));
    const tbody = table.querySelector('tbody');
    const rows = Array.from(tbody.querySelectorAll('tr'));
    
    // Check if this is the holdings table
    const latestPriceIndex = headers.findIndex(h => h.textContent.includes('Latest Price'));
    if (latestPriceIndex !== -1) {
        // Holdings table - sort by Latest Price descending (most valuable individual items)
        rows.sort((rowA, rowB) => {
            const cellA = rowA.cells[latestPriceIndex].textContent.trim();
            const cellB = rowB.cells[latestPriceIndex].textContent.trim();
            const valA = parseFloat(cellA.replace(/[$,]/g, ''));
            const valB = parseFloat(cellB.replace(/[$,]/g, ''));
            return valB - valA; // Descending
        });
        rows.forEach(row => tbody.appendChild(row));
        return;
    }
    
    // Check if this is the transactions table
    const dateIndex = headers.findIndex(h => h.textContent.includes('Date'));
    if (dateIndex !== -1) {
        // Transactions table - sort by Date descending (newest first)
        rows.sort((rowA, rowB) => {
            const cellA = rowA.cells[dateIndex].textContent.trim();
            const cellB = rowB.cells[dateIndex].textContent.trim();
            
            // Parse MM/DD/YYYY format
            const dateA = parseDateString(cellA);
            const dateB = parseDateString(cellB);
            
            return dateB - dateA; // Descending (newest first)
        });
        rows.forEach(row => tbody.appendChild(row));
        return;
    }
}

function parseDateString(dateStr) {
    // Handle MM/DD/YYYY format
    if (dateStr.match(/\d{1,2}\/\d{1,2}\/\d{4}/)) {
        return new Date(dateStr);
    }
    // Handle YYYY-MM-DD format
    if (dateStr.match(/\d{4}-\d{2}-\d{2}/)) {
        return new Date(dateStr);
    }
    return new Date(0); // Invalid date goes to bottom
}

function sortTable(table, colIndex) {
    const tbody = table.querySelector('tbody');
    let rows = Array.from(tbody.querySelectorAll('tr'));
    const header = table.querySelectorAll('th')[colIndex];
    
    // Logic: '' -> asc -> desc -> ''
    const currentOrder = header.getAttribute('data-order') || '';
    let newOrder = '';

    if (currentOrder === '') {
        newOrder = 'asc';
    } else if (currentOrder === 'asc') {
        newOrder = 'desc';
    } else if (currentOrder === 'desc') {
        newOrder = '';
    }

    // Reset other headers
    table.querySelectorAll('th').forEach(th => {
        if (th !== header) {
            th.setAttribute('data-order', '');
            const icon = th.querySelector('.fa-sort, .fa-sort-up, .fa-sort-down');
            if(icon) icon.className = 'fas fa-sort text-muted ms-1 small'; 
        }
    });

    // Update current header
    header.setAttribute('data-order', newOrder);
    const icon = header.querySelector('.fas');
    if(icon) {
        if (newOrder === 'asc') {
            icon.className = 'fas fa-sort-up text-primary ms-1 small';
        } else if (newOrder === 'desc') {
            icon.className = 'fas fa-sort-down text-primary ms-1 small';
        } else {
            icon.className = 'fas fa-sort text-muted ms-1 small';
        }
    }

    // Perform Sort
    if (newOrder === '') {
        // Restore original order
        rows.sort((a, b) => {
            return parseInt(a.getAttribute('data-original-index')) - parseInt(b.getAttribute('data-original-index'));
        });
    } else {
        const isAscending = newOrder === 'asc';
        
        rows.sort((rowA, rowB) => {
            const cellA = rowA.cells[colIndex].textContent.trim();
            const cellB = rowB.cells[colIndex].textContent.trim();
            
            // Try numerical sort
            const valA = parseFloat(cellA.replace(/[$,]/g, ''));
            const valB = parseFloat(cellB.replace(/[$,]/g, ''));
            
            if (!isNaN(valA) && !isNaN(valB)) {
                return isAscending ? valA - valB : valB - valA;
            }
            
            // Date sort (handles both MM/DD/YYYY and YYYY-MM-DD formats)
            if (cellA.match(/\d{1,2}\/\d{1,2}\/\d{4}/) && cellB.match(/\d{1,2}\/\d{1,2}\/\d{4}/)) {
                 return isAscending 
                    ? new Date(cellA) - new Date(cellB) 
                    : new Date(cellB) - new Date(cellA);
            }
            if (cellA.match(/\d{4}-\d{2}-\d{2}/) && cellB.match(/\d{4}-\d{2}-\d{2}/)) {
                 return isAscending 
                    ? new Date(cellA) - new Date(cellB) 
                    : new Date(cellB) - new Date(cellA);
            }

            return isAscending ? cellA.localeCompare(cellB) : cellB.localeCompare(cellA);
        });
    }
    
    rows.forEach(row => tbody.appendChild(row));
}

function filterData(table) {
    const searchInput = document.getElementById('globalSearch');
    const typeFilter = document.getElementById('typeFilter');
    
    const query = searchInput ? searchInput.value.toLowerCase() : '';
    const typeQuery = typeFilter ? typeFilter.value.toLowerCase() : '';
    
    const tbody = table.querySelector('tbody');
    const rows = tbody.querySelectorAll('tr');

    rows.forEach(row => {
        // Find the "Type" cell (1st column, index 0)
        const typeCell = row.cells[0]; 
        const rowText = row.innerText.toLowerCase();
        
        let matchesSearch = rowText.includes(query);
        let matchesType = true;
        
        if (typeQuery && typeCell) {
            matchesType = typeCell.textContent.toLowerCase().includes(typeQuery);
        }
        
        if (matchesSearch && matchesType) {
            row.style.display = '';
        } else {
            row.style.display = 'none';
        }
    });
}
