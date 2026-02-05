// GitHub API Integration for Pokemon Tracker
// Handles all GitHub API operations for transactions and mappings

class GitHubAPI {
    constructor() {
        this.config = {
            owner: 'gauravagarwal003',
            repo: 'Pokemon_Tracker',
            branch: 'main'
        };
        this.apiBase = 'https://api.github.com';
        this.cache = {
            transactions: null,
            mappings: null,
            transactionsSha: null,
            mappingsSha: null
        };
        // Detect if running locally
        this.isLocal = window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1' || window.location.hostname === '';
    }

    // Get token from PokeAuth
    get token() {
        return window.PokeAuth?.getToken() || sessionStorage.getItem('github_token');
    }

    // Check if authenticated with GitHub
    isAuthenticated() {
        return !!this.token;
    }

    // Prompt for GitHub PAT with detailed instructions
    async authenticate() {
        const modal = document.createElement('div');
        modal.className = 'modal fade';
        modal.id = 'githubAuthModal';
        modal.innerHTML = `
            <div class="modal-dialog modal-lg">
                <div class="modal-content">
                    <div class="modal-header bg-dark text-white">
                        <h5 class="modal-title"><i class="fab fa-github me-2"></i>GitHub Authentication</h5>
                        <button type="button" class="btn-close btn-close-white" data-bs-dismiss="modal"></button>
                    </div>
                    <div class="modal-body">
                        <div class="alert alert-info">
                            <i class="fas fa-info-circle me-2"></i>
                            To edit transactions, you need a GitHub Personal Access Token (PAT).
                        </div>
                        
                        <h6>Steps to create a token:</h6>
                        <ol class="mb-4">
                            <li>Go to <a href="https://github.com/settings/tokens" target="_blank">GitHub Token Settings</a></li>
                            <li>Click <strong>"Generate new token"</strong> → <strong>"Generate new token (classic)"</strong></li>
                            <li>Name it: <code>Pokemon Tracker</code></li>
                            <li>Select expiration (recommend: 90 days or No expiration)</li>
                            <li>Check the <strong>repo</strong> scope (full access to repositories)</li>
                            <li>Click <strong>"Generate token"</strong></li>
                            <li>Copy the token (starts with <code>ghp_</code>)</li>
                        </ol>
                        
                        <div class="form-group">
                            <label for="tokenInput" class="form-label fw-bold">Paste your token:</label>
                            <input type="password" class="form-control" id="tokenInput" 
                                   placeholder="ghp_xxxxxxxxxxxxxxxxxxxx">
                            <div class="form-text">Token is stored in your browser session only (cleared when you close browser).</div>
                        </div>
                        
                        <div id="tokenError" class="alert alert-danger mt-3" style="display: none;"></div>
                    </div>
                    <div class="modal-footer">
                        <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">Cancel</button>
                        <button type="button" class="btn btn-success" id="validateTokenBtn">
                            <i class="fas fa-check me-2"></i>Validate & Save
                        </button>
                    </div>
                </div>
            </div>
        `;

        document.body.appendChild(modal);
        const bsModal = new bootstrap.Modal(modal);
        bsModal.show();

        return new Promise((resolve) => {
            const validateBtn = document.getElementById('validateTokenBtn');
            const tokenInput = document.getElementById('tokenInput');
            const errorDiv = document.getElementById('tokenError');

            validateBtn.addEventListener('click', async () => {
                const token = tokenInput.value.trim();
                
                if (!token) {
                    errorDiv.textContent = 'Please enter a token';
                    errorDiv.style.display = 'block';
                    return;
                }

                validateBtn.disabled = true;
                validateBtn.innerHTML = '<span class="spinner-border spinner-border-sm me-2"></span>Validating...';

                try {
                    // Test the token
                    const response = await fetch(`${this.apiBase}/repos/${this.config.owner}/${this.config.repo}`, {
                        headers: {
                            'Authorization': `Bearer ${token}`,
                            'Accept': 'application/vnd.github.v3+json'
                        }
                    });

                    if (!response.ok) {
                        throw new Error(`Invalid token: ${response.status}`);
                    }

                    // Check we have write access
                    const repoData = await response.json();
                    if (!repoData.permissions?.push) {
                        throw new Error('Token does not have write access to this repo');
                    }

                    // Save token
                    if (window.PokeAuth) {
                        window.PokeAuth.setToken(token);
                    } else {
                        sessionStorage.setItem('github_token', token);
                    }

                    bsModal.hide();
                    modal.remove();
                    resolve(true);

                } catch (error) {
                    errorDiv.textContent = `Error: ${error.message}. Make sure the token has 'repo' scope.`;
                    errorDiv.style.display = 'block';
                    validateBtn.disabled = false;
                    validateBtn.innerHTML = '<i class="fas fa-check me-2"></i>Validate & Save';
                }
            });

            modal.addEventListener('hidden.bs.modal', () => {
                modal.remove();
                resolve(false);
            });
        });
    }

    // Logout
    logout() {
        if (window.PokeAuth) {
            window.PokeAuth.logout();
        } else {
            sessionStorage.removeItem('github_token');
            window.location.reload();
        }
    }

    // Make authenticated API request
    async request(url, options = {}) {
        if (!this.token) {
            throw new Error('Not authenticated');
        }

        const response = await fetch(url, {
            ...options,
            headers: {
                'Authorization': `Bearer ${this.token}`,
                'Accept': 'application/vnd.github.v3+json',
                'Content-Type': 'application/json',
                ...options.headers
            }
        });

        if (!response.ok) {
            const error = await response.json().catch(() => ({}));
            throw new Error(error.message || `API Error: ${response.status}`);
        }

        return response.json();
    }

    // Get file content from repo
    async getFile(path) {
        const url = `${this.apiBase}/repos/${this.config.owner}/${this.config.repo}/contents/${path}?ref=${this.config.branch}`;
        const data = await this.request(url);
        
        return {
            content: atob(data.content.replace(/\n/g, '')),
            sha: data.sha
        };
    }

    // Update file in repo
    async updateFile(path, content, message, sha) {
        // Don't commit if running locally
        if (this.isLocal) {
            console.log('[LOCAL MODE] Skipping commit:', message);
            alert(`Running in local mode - changes will not be committed to GitHub.\n\nTo save changes permanently, commit and push manually:\ngit add ${path}\ngit commit -m "${message}"\ngit push`);
            return { sha: sha }; // Return fake success
        }
        const url = `${this.apiBase}/repos/${this.config.owner}/${this.config.repo}/contents/${path}`;
        
        return this.request(url, {
            method: 'PUT',
            body: JSON.stringify({
                message: message,
                content: btoa(unescape(encodeURIComponent(content))),
                sha: sha,
                branch: this.config.branch
            })
        });
    }

    // ===== CSV HELPERS =====

    // Parse CSV to array of objects
    parseCSV(csv) {
        const lines = csv.trim().split('\n');
        if (lines.length < 1) return [];
        
        const headers = this.parseCSVLine(lines[0]);
        
        return lines.slice(1).map((line, index) => {
            const values = this.parseCSVLine(line);
            const obj = { _index: index };
            headers.forEach((header, i) => {
                obj[header] = values[i] || '';
            });
            return obj;
        });
    }

    // Parse single CSV line handling quoted values
    parseCSVLine(line) {
        const result = [];
        let current = '';
        let inQuotes = false;
        
        for (let i = 0; i < line.length; i++) {
            const char = line[i];
            
            if (char === '"') {
                if (inQuotes && line[i + 1] === '"') {
                    current += '"';
                    i++;
                } else {
                    inQuotes = !inQuotes;
                }
            } else if (char === ',' && !inQuotes) {
                result.push(current);
                current = '';
            } else {
                current += char;
            }
        }
        result.push(current);
        
        return result;
    }

    // Convert array of objects to CSV
    toCSV(data, headers) {
        const escapeCSV = (val) => {
            if (val == null) return '';
            const str = String(val);
            if (str.includes(',') || str.includes('"') || str.includes('\n')) {
                return `"${str.replace(/"/g, '""')}"`;
            }
            return str;
        };
        
        const rows = [headers.join(',')];
        data.forEach(row => {
            const values = headers.map(header => escapeCSV(row[header]));
            rows.push(values.join(','));
        });
        
        return rows.join('\n');
    }

    // ===== TRANSACTIONS =====

    // Get all transactions
    async getTransactions(forceRefresh = false) {
        if (!forceRefresh && this.cache.transactions) {
            return { 
                transactions: this.cache.transactions, 
                sha: this.cache.transactionsSha 
            };
        }

        const file = await this.getFile('transactions.csv');
        const transactions = this.parseCSV(file.content);
        
        this.cache.transactions = transactions;
        this.cache.transactionsSha = file.sha;
        
        return { transactions, sha: file.sha };
    }

    // Add new transaction
    async addTransaction(transaction) {
        const { transactions, sha } = await this.getTransactions(true);
        transactions.push(transaction);
        
        const headers = [
            'Date Purchased', 'Date Recieved', 'Transaction Type', 'Price Per Unit',
            'Quantity', 'Item', 'group_id', 'product_id', 'Method', 'Place', 'Notes'
        ];
        const csv = this.toCSV(transactions, headers);
        
        await this.updateFile('transactions.csv', csv, `Add transaction: ${transaction.Item}`, sha);
        this.cache.transactions = null; // Invalidate cache
    }

    // Update existing transaction
    async updateTransaction(index, transaction) {
        const { transactions, sha } = await this.getTransactions(true);
        
        if (index < 0 || index >= transactions.length) {
            throw new Error('Transaction not found');
        }
        
        transactions[index] = { ...transactions[index], ...transaction };
        
        const headers = [
            'Date Purchased', 'Date Recieved', 'Transaction Type', 'Price Per Unit',
            'Quantity', 'Item', 'group_id', 'product_id', 'Method', 'Place', 'Notes'
        ];
        const csv = this.toCSV(transactions, headers);
        
        await this.updateFile('transactions.csv', csv, `Update transaction: ${transaction.Item}`, sha);
        this.cache.transactions = null;
    }

    // Delete transaction
    async deleteTransaction(index) {
        const { transactions, sha } = await this.getTransactions(true);
        
        if (index < 0 || index >= transactions.length) {
            throw new Error('Transaction not found');
        }
        
        const deleted = transactions.splice(index, 1)[0];
        
        const headers = [
            'Date Purchased', 'Date Recieved', 'Transaction Type', 'Price Per Unit',
            'Quantity', 'Item', 'group_id', 'product_id', 'Method', 'Place', 'Notes'
        ];
        const csv = this.toCSV(transactions, headers);
        
        await this.updateFile('transactions.csv', csv, `Delete transaction: ${deleted.Item}`, sha);
        this.cache.transactions = null;
    }

    // ===== MAPPINGS =====

    // Get all mappings
    async getMappings(forceRefresh = false) {
        if (!forceRefresh && this.cache.mappings) {
            return { 
                mappings: this.cache.mappings, 
                sha: this.cache.mappingsSha 
            };
        }

        const file = await this.getFile('mappings.json');
        const mappings = JSON.parse(file.content);
        
        this.cache.mappings = mappings;
        this.cache.mappingsSha = file.sha;
        
        return { mappings, sha: file.sha };
    }

    // Search products in mappings
    async searchProducts(query) {
        const { mappings } = await this.getMappings();
        
        if (!query || query.length < 2) return [];
        
        const lowerQuery = query.toLowerCase();
        return mappings
            .filter(m => m.name.toLowerCase().includes(lowerQuery))
            .slice(0, 15); // Limit results
    }

    // Add new product to mappings
    async addProduct(name, productId, groupId, categoryId) {
        const { mappings, sha } = await this.getMappings(true);
        
        // Check if already exists
        const exists = mappings.find(
            m => m.product_id === String(productId) && m.group_id === String(groupId)
        );
        
        if (exists) {
            return exists; // Return existing product
        }
        
        // Generate URLs
        const imageUrl = `https://tcgplayer-cdn.tcgplayer.com/product/${productId}_200w.jpg`;
        const url = `https://www.tcgplayer.com/product/${productId}`;
        
        const newProduct = {
            product_id: String(productId),
            name: name,
            group_id: String(groupId),
            imageUrl: imageUrl,
            categoryId: parseInt(categoryId) || 3,
            url: url
        };
        
        mappings.push(newProduct);
        
        const json = JSON.stringify(mappings, null, 2);
        await this.updateFile('mappings.json', json, `Add product: ${name}`, sha);
        
        this.cache.mappings = null; // Invalidate cache
        
        return newProduct;
    }

    // Get product by IDs
    async getProduct(productId, groupId) {
        const { mappings } = await this.getMappings();
        
        return mappings.find(
            m => m.product_id === String(productId) && m.group_id === String(groupId)
        );
    }
}

// Initialize global API instance
const githubAPI = new GitHubAPI();
