// Authentication for Pokemon Tracker GitHub Pages
// Dual-layer: Password + GitHub PAT

(function() {
    'use strict';

    // Configuration - Change this password hash for your own password
    // To generate: Open browser console and run:
    // crypto.subtle.digest('SHA-256', new TextEncoder().encode('your-password')).then(h => console.log(Array.from(new Uint8Array(h)).map(b => b.toString(16).padStart(2, '0')).join('')))
    const PASSWORD_HASH = 'e91e78805d7e65607f3c2f25f174d385dbef65f56f325ca1331e380abcd54838';
    
    const AUTH_KEY = 'poketracker_auth';
    const TOKEN_KEY = 'github_token';

    // Check if user has passed password auth
    function isPasswordAuthenticated() {
        return sessionStorage.getItem(AUTH_KEY) === PASSWORD_HASH;
    }

    // Check if user has GitHub token
    function hasGitHubToken() {
        return !!sessionStorage.getItem(TOKEN_KEY);
    }

    // Hash password using SHA-256
    async function hashPassword(password) {
        const hashBuffer = await crypto.subtle.digest('SHA-256', new TextEncoder().encode(password));
        const hashArray = Array.from(new Uint8Array(hashBuffer));
        return hashArray.map(b => b.toString(16).padStart(2, '0')).join('');
    }

    // Verify password
    async function verifyPassword(password) {
        const hash = await hashPassword(password);
        return hash === PASSWORD_HASH;
    }

    // Create blocking overlay immediately
    function createBlockingOverlay() {
        const overlay = document.createElement('div');
        overlay.id = 'authBlockingOverlay';
        overlay.style.cssText = `
            position: fixed;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
            z-index: 99999;
            display: flex;
            align-items: center;
            justify-content: center;
        `;
        return overlay;
    }

    // Show password prompt
    function showPasswordPrompt(overlay) {
        return new Promise((resolve) => {
            overlay.innerHTML = `
                <div style="background: white; padding: 40px; border-radius: 16px; box-shadow: 0 25px 50px -12px rgba(0,0,0,0.5); max-width: 400px; width: 90%; font-family: 'Inter', -apple-system, sans-serif;">
                    <div style="text-align: center; margin-bottom: 24px;">
                        <div style="font-size: 48px; margin-bottom: 16px;">🔒</div>
                        <h2 style="margin: 0; color: #1e293b; font-size: 24px;">PokeTracker</h2>
                        <p style="color: #64748b; margin-top: 8px;">Enter password to continue</p>
                    </div>
                    <form id="authForm">
                        <input type="password" id="authPassword" placeholder="Password" 
                               style="width: 100%; padding: 12px 16px; font-size: 16px; border-radius: 8px; margin-bottom: 16px; border: 1px solid #e2e8f0; box-sizing: border-box;" 
                               autocomplete="current-password">
                        <button type="submit" 
                                style="width: 100%; padding: 12px; font-size: 16px; border-radius: 8px; background: #6366f1; border: none; color: white; cursor: pointer; font-weight: 500;">
                            Login
                        </button>
                        <div id="authError" style="color: #ef4444; margin-top: 12px; text-align: center; display: none;">
                            Incorrect password
                        </div>
                    </form>
                </div>
            `;

            // Wait for DOM to update then focus
            setTimeout(() => {
                const passwordInput = document.getElementById('authPassword');
                if (passwordInput) passwordInput.focus();
            }, 100);

            const form = document.getElementById('authForm');
            const passwordInput = document.getElementById('authPassword');
            const errorDiv = document.getElementById('authError');

            form.addEventListener('submit', async (e) => {
                e.preventDefault();
                const password = passwordInput.value;
                
                if (await verifyPassword(password)) {
                    sessionStorage.setItem(AUTH_KEY, PASSWORD_HASH);
                    resolve(true);
                } else {
                    errorDiv.style.display = 'block';
                    passwordInput.value = '';
                    passwordInput.focus();
                }
            });
        });
    }

    // Main auth flow
    async function authenticate() {
        // If already authenticated, do nothing
        if (isPasswordAuthenticated()) {
            return;
        }

        // Create and show blocking overlay
        const overlay = createBlockingOverlay();
        document.body.appendChild(overlay);

        try {
            await showPasswordPrompt(overlay);
            overlay.remove();
        } catch (error) {
            console.error('Auth error:', error);
            overlay.remove();
        }
    }

    // Run auth immediately when script loads
    if (document.body) {
        authenticate();
    } else {
        document.addEventListener('DOMContentLoaded', authenticate);
    }

    // Export functions for use by other scripts
    window.PokeAuth = {
        isPasswordAuthenticated,
        hasGitHubToken,
        getToken: () => sessionStorage.getItem(TOKEN_KEY),
        setToken: (token) => sessionStorage.setItem(TOKEN_KEY, token),
        clearToken: () => sessionStorage.removeItem(TOKEN_KEY),
        logout: () => {
            sessionStorage.removeItem(AUTH_KEY);
            sessionStorage.removeItem(TOKEN_KEY);
            window.location.reload();
        }
    };
})();
