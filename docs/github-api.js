// GitHub API Integration for Pokemon Tracker
// Handles authentication and API calls to edit transactions.csv

const GITHUB_CONFIG = {
    owner: 'gauravagarwal003', // CHANGE THIS
    repo: 'Pokemon_Tracker',        // CHANGE THIS if different
    branch: 'main',                 // CHANGE THIS if using different branch
    clientId: 'YOUR_GITHUB_OAUTH_CLIENT_ID' // Set this after creating OAuth App
};

class GitHubAPI {
    constructor() {
        this.token = sessionStorage.getItem('github_token');
        this.apiBase = 'https://api.github.com';
    }

    // Check if user is authenticated
    isAuthenticated() {
        return !!this.token;
    }

    // Start OAuth flow
    authenticate() {
        const redirectUri = window.location.origin + window.location.pathname;
        const scope = 'repo';
        const authUrl = `https://github.com/login/oauth/authorize?client_id=${GITHUB_CONFIG.clientId}&redirect_uri=${encodeURIComponent(redirectUri)}&scope=${scope}`;
        window.location.href = authUrl;
    }

    // Handle OAuth callback
    handleCallback() {
        const urlParams = new URLSearchParams(window.location.search);
        const code = urlParams.get('code');
        
        if (code) {
            // In production, you'd exchange this code for a token via a serverless function
            // For now, we'll use a simpler approach with GitHub's device flow or manual token
            alert('OAuth code received. For security, please use a Personal Access Token instead.\n\nGo to: GitHub Settings > Developer Settings > Personal Access Tokens > Generate new token\n\nGrant "repo" scope and paste it when prompted.');
            const token = prompt('Paste your GitHub Personal Access Token:');
            if (token) {
                this.setToken(token);
                // Clean URL
                window.history.replaceState({}, document.title, window.location.pathname);
                window.location.reload();
            }
        }
    }

    // Set token manually
    setToken(token) {
        this.token = token;
        sessionStorage.setItem('github_token', token);
    }

    // Logout
    logout() {
        this.token = null;
        sessionStorage.removeItem('github_token');
        window.location.reload();
    }

    // Get file content
    async getFile(path) {
        const url = `${this.apiBase}/repos/${GITHUB_CONFIG.owner}/${GITHUB_CONFIG.repo}/contents/${path}?ref=${GITHUB_CONFIG.branch}`;
        const response = await fetch(url, {
            headers: {
                'Authorization': `token ${this.token}`,
                'Accept': 'application/vnd.github.v3+json'
            }
        });
        
        if (!response.ok) throw new Error(`Failed to get file: ${response.statusText}`);
        
        const data = await response.json();
        return {
            content: atob(data.content),
            sha: data.sha
        };
    }

    // Update file
    async updateFile(path, content, message, sha) {
        const url = `${this.apiBase}/repos/${GITHUB_CONFIG.owner}/${GITHUB_CONFIG.repo}/contents/${path}`;
        const response = await fetch(url, {
            method: 'PUT',
            headers: {
                'Authorization': `token ${this.token}`,
                'Accept': 'application/vnd.github.v3+json',
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                message: message,
                content: btoa(content),
                sha: sha,
                branch: GITHUB_CONFIG.branch
            })
        });
        
        if (!response.ok) {
            const error = await response.json();
            throw new Error(`Failed to update file: ${error.message}`);
        }
        
        return await response.json();
    }

    // Parse CSV to array of objects
    parseCSV(csv) {
        const lines = csv.trim().split('\n');
        const headers = lines[0].split(',');
        
        return lines.slice(1).map((line, index) => {
            const values = this.parseCSVLine(line);
            const obj = { _index: index };
            headers.forEach((header, i) => {
                obj[header] = values[i] || '';
            });
            return obj;
        });
    }

    // Parse a single CSV line (handles quoted values)
    parseCSVLine(line) {
        const result = [];
        let current = '';
        let inQuotes = false;
        
        for (let i = 0; i < line.length; i++) {
            const char = line[i];
            
            if (char === '"') {
                inQuotes = !inQuotes;
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

    // Get transactions
    async getTransactions() {
        const file = await this.getFile('transactions.csv');
        const transactions = this.parseCSV(file.content);
        return { transactions, sha: file.sha };
    }

    // Add transaction
    async addTransaction(transaction) {
        const { transactions, sha } = await this.getTransactions();
        transactions.push(transaction);
        
        const headers = Object.keys(transactions[0]).filter(k => k !== '_index');
        const csv = this.toCSV(transactions, headers);
        
        await this.updateFile('transactions.csv', csv, 'Add transaction', sha);
    }

    // Update transaction
    async updateTransaction(index, transaction) {
        const { transactions, sha } = await this.getTransactions();
        transactions[index] = { ...transactions[index], ...transaction };
        
        const headers = Object.keys(transactions[0]).filter(k => k !== '_index');
        const csv = this.toCSV(transactions, headers);
        
        await this.updateFile('transactions.csv', csv, 'Update transaction', sha);
    }

    // Delete transaction
    async deleteTransaction(index) {
        const { transactions, sha } = await this.getTransactions();
        transactions.splice(index, 1);
        
        const headers = ['Date Purchased','Date Recieved','Transaction Type','Price Per Unit','Quantity','Item','group_id','product_id','Method','Place','Notes'];
        const csv = this.toCSV(transactions, headers);
        
        await this.updateFile('transactions.csv', csv, 'Delete transaction', sha);
    }

    // Get mappings
    async getMappings() {
        const file = await this.getFile('mappings.json');
        return JSON.parse(file.content);
    }
}

// Initialize API
const githubAPI = new GitHubAPI();

// Handle OAuth callback on page load
if (window.location.search.includes('code=')) {
    githubAPI.handleCallback();
}
