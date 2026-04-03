// GitHub API Integration for TCG Tracker v2
// Works with transactions.json (not CSV)

class GitHubAPI {
    constructor() {
        this.config = {
            owner: 'gauravagarwal003',
            repo: 'TCG_Tracker',
            branch: 'main'
        };
        this.apiBase = 'https://api.github.com';
        this.cache = {};
        this.isLocal = window.location.hostname === 'localhost' ||
                       window.location.hostname === '127.0.0.1' ||
                       window.location.hostname === '';
    }

    async loadConfig() {
        try {
            const resp = await fetch('/config.json', { cache: 'no-store' });
            if (!resp.ok) return;
            const cfg = await resp.json();
            if (cfg.github) {
                this.config.owner = cfg.github.owner || this.config.owner;
                this.config.repo = cfg.github.repo || this.config.repo;
                this.config.branch = cfg.github.branch || this.config.branch;
            }
        } catch (e) {
            console.warn('Could not load /config.json', e);
        }
    }

    get token() {
        return window.TCGAuth?.getToken() || sessionStorage.getItem('github_token');
    }

    isAuthenticated() {
        return !!this.token;
    }

    async authenticate() {
        if (!window.bootstrap || !bootstrap.Modal) {
            const token = window.prompt('Paste your GitHub PAT (repo scope):');
            if (!token) return false;
            try {
                const response = await fetch(
                    `${this.apiBase}/repos/${this.config.owner}/${this.config.repo}`,
                    { headers: { 'Authorization': `Bearer ${token}`, 'Accept': 'application/vnd.github.v3+json' } }
                );
                if (!response.ok) throw new Error('Invalid token: ' + response.status);
                const repoData = await response.json();
                if (!repoData.permissions?.push) throw new Error('Token lacks write access');

                if (window.TCGAuth) {
                    window.TCGAuth.setToken(token);
                } else {
                    sessionStorage.setItem('github_token', token);
                }
                return true;
            } catch (error) {
                alert('Error: ' + error.message);
                return false;
            }
        }

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
                        <h6>Steps:</h6>
                        <ol class="mb-4">
                            <li>Go to <a href="https://github.com/settings/tokens" target="_blank">GitHub Token Settings</a></li>
                            <li>Generate new token (classic) with <strong>repo</strong> scope</li>
                            <li>Paste the token below</li>
                        </ol>
                        <div class="form-group">
                            <label for="tokenInput" class="form-label fw-bold">Paste your token:</label>
                            <input type="password" class="form-control" id="tokenInput"
                                   placeholder="ghp_xxxxxxxxxxxxxxxxxxxx">
                            <div class="form-text">Stored in session only.</div>
                        </div>
                        <div id="tokenError" class="alert alert-danger mt-3" style="display:none;"></div>
                    </div>
                    <div class="modal-footer">
                        <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">Cancel</button>
                        <button type="button" class="btn btn-success" id="validateTokenBtn">
                            <i class="fas fa-check me-2"></i>Validate &amp; Save
                        </button>
                    </div>
                </div>
            </div>`;

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
                    const response = await fetch(
                        `${this.apiBase}/repos/${this.config.owner}/${this.config.repo}`,
                        { headers: { 'Authorization': `Bearer ${token}`, 'Accept': 'application/vnd.github.v3+json' } }
                    );
                    if (!response.ok) throw new Error('Invalid token: ' + response.status);
                    const repoData = await response.json();
                    if (!repoData.permissions?.push) throw new Error('Token lacks write access');

                    if (window.TCGAuth) {
                        window.TCGAuth.setToken(token);
                    } else {
                        sessionStorage.setItem('github_token', token);
                    }
                    bsModal.hide();
                    modal.remove();
                    resolve(true);
                } catch (error) {
                    errorDiv.textContent = 'Error: ' + error.message;
                    errorDiv.style.display = 'block';
                    validateBtn.disabled = false;
                    validateBtn.innerHTML = '<i class="fas fa-check me-2"></i>Validate &amp; Save';
                }
            });

            modal.addEventListener('hidden.bs.modal', () => {
                modal.remove();
                resolve(false);
            });
        });
    }

    logout() {
        if (window.TCGAuth) {
            window.TCGAuth.logout();
        } else {
            sessionStorage.removeItem('github_token');
            window.location.reload();
        }
    }

    async request(url, options = {}) {
        if (!this.token) throw new Error('Not authenticated');
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
            throw new Error(error.message || 'API Error: ' + response.status);
        }
        return response.json();
    }

    decodeBase64Utf8(base64Text) {
        if (!base64Text) return '';
        const binary = atob(base64Text.replace(/\n/g, ''));
        const bytes = Uint8Array.from(binary, ch => ch.charCodeAt(0));
        return new TextDecoder('utf-8').decode(bytes);
    }

    async fetchRawFile(path) {
        const rawUrl = `https://raw.githubusercontent.com/${this.config.owner}/${this.config.repo}/${this.config.branch}/${path}`;
        const response = await fetch(rawUrl, {
            headers: {
                'Authorization': `Bearer ${this.token}`,
                'Accept': 'application/vnd.github.v3.raw'
            }
        });
        if (!response.ok) {
            throw new Error(`Failed to fetch raw ${path}: ${response.status}`);
        }
        return response.text();
    }

    async getFile(path) {
        const url = `${this.apiBase}/repos/${this.config.owner}/${this.config.repo}/contents/${path}?ref=${this.config.branch}`;
        const data = await this.request(url);

        if (data.content && data.encoding === 'base64') {
            return {
                content: this.decodeBase64Utf8(data.content),
                sha: data.sha
            };
        }

        // Contents API may omit file content for larger files (>1 MB).
        // Fall back to blob API first, then raw download as a final fallback.
        if (data.sha) {
            try {
                const blob = await this.request(
                    `${this.apiBase}/repos/${this.config.owner}/${this.config.repo}/git/blobs/${data.sha}`
                );
                if (blob.content && blob.encoding === 'base64') {
                    return {
                        content: this.decodeBase64Utf8(blob.content),
                        sha: data.sha
                    };
                }
            } catch (e) {
                console.warn(`Blob API fallback failed for ${path}:`, e);
            }
        }

        const rawText = await this.fetchRawFile(path);
        if (!rawText && (data.size || 0) > 0) {
            throw new Error(`Failed to read non-empty file: ${path}`);
        }
        return {
            content: rawText,
            sha: data.sha
        };
    }

    async updateFile(path, content, message, sha) {
        if (this.isLocal) {
            console.log('[LOCAL] Skipping commit:', message);
            alert('Local mode – changes not committed to GitHub.');
            return { sha: sha };
        }
        const url = `${this.apiBase}/repos/${this.config.owner}/${this.config.repo}/contents/${path}`;
        const utf8Bytes = new TextEncoder().encode(content);
        const binaryString = Array.from(utf8Bytes, byte => String.fromCharCode(byte)).join('');
        const base64Content = btoa(binaryString);
        return this.request(url, {
            method: 'PUT',
            body: JSON.stringify({
                message: message,
                content: base64Content,
                sha: sha,
                branch: this.config.branch
            })
        });
    }

    // Update multiple files in a single atomic commit using the Git Data API
    async updateFilesAtomic(files, message) {
        // files: [{ path, content, sha? }]
        if (this.isLocal) {
            console.log('[LOCAL] Skipping atomic commit:', message);
            alert('Local mode – changes not committed to GitHub.');
            return null;
        }

        // Create blobs first — content-addressed so safe to do once outside the retry loop
        const blobPromises = files.map(f => {
            const utf8Bytes = new TextEncoder().encode(f.content);
            const binaryString = Array.from(utf8Bytes, byte => String.fromCharCode(byte)).join('');
            const base64Content = btoa(binaryString);
            return this.request(`${this.apiBase}/repos/${this.config.owner}/${this.config.repo}/git/blobs`, {
                method: 'POST',
                body: JSON.stringify({ content: base64Content, encoding: 'base64' })
            }).then(res => ({ path: f.path, sha: res.sha }));
        });
        const blobs = await Promise.all(blobPromises);
        const treeEntries = blobs.map(b => ({ path: b.path, mode: '100644', type: 'blob', sha: b.sha }));

        // Retry loop — handles the case where another commit (e.g. daily CI) lands
        // between our fetch and our push, causing a "not a fast forward" rejection.
        const MAX_RETRIES = 3;
        for (let attempt = 0; attempt < MAX_RETRIES; attempt++) {
            // Get current branch HEAD
            const ref = await this.request(
                `${this.apiBase}/repos/${this.config.owner}/${this.config.repo}/git/ref/heads/${this.config.branch}`
            );
            const commitSha = ref.object.sha;

            // Get base tree SHA from current commit
            const commitData = await this.request(
                `${this.apiBase}/repos/${this.config.owner}/${this.config.repo}/git/commits/${commitSha}`
            );

            // Create tree on top of current HEAD
            const newTree = await this.request(
                `${this.apiBase}/repos/${this.config.owner}/${this.config.repo}/git/trees`,
                { method: 'POST', body: JSON.stringify({ base_tree: commitData.tree.sha, tree: treeEntries }) }
            );

            // Create commit with current HEAD as parent
            const newCommit = await this.request(
                `${this.apiBase}/repos/${this.config.owner}/${this.config.repo}/git/commits`,
                { method: 'POST', body: JSON.stringify({ message, tree: newTree.sha, parents: [commitSha] }) }
            );

            // Advance the branch ref — retry on fast-forward conflict
            try {
                await this.request(
                    `${this.apiBase}/repos/${this.config.owner}/${this.config.repo}/git/refs/heads/${this.config.branch}`,
                    { method: 'PATCH', body: JSON.stringify({ sha: newCommit.sha }) }
                );
                return newCommit;
            } catch (err) {
                if (attempt < MAX_RETRIES - 1 && err.message?.toLowerCase().includes('not a fast forward')) {
                    console.warn(`Commit race on attempt ${attempt + 1}, retrying…`);
                    continue;
                }
                throw err;
            }
        }
        throw new Error('Failed to commit after several retries due to concurrent updates. Please try again.');
    }
}

// Initialize global API instance
const githubAPI = new GitHubAPI();
window.githubAPI = githubAPI;
