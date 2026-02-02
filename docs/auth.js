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

    // Show password prompt
    function showPasswordPrompt() {
        return new Promise((resolve) => {
            // Create modal overlay
            const overlay = document.createElement('div');
            overlay.id = 'authOverlay';
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
                font-family: 'Inter', -apple-system, sans-serif;
            `;

            overlay.innerHTML = `
                <div style="background: white; padding: 40px; border-radius: 16px; box-shadow: 0 25px 50px -12px rgba(0,0,0,0.5); max-width: 400px; width: 90%;">
                    <div style="text-align: center; margin-bottom: 24px;">
                        <i class="fas fa-lock" style="font-size: 48px; color: #6366f1; margin-bottom: 16px;"></i>
                        <h2 style="margin: 0; color: #1e293b; font-size: 24px;">PokeTracker</h2>
                        <p style="color: #64748b; margin-top: 8px;">Enter password to continue</p>
                    </div>
                    <form id="authForm">
                        <input type="password" id="authPassword" class="form-control" placeholder="Password" 
                               style="padding: 12px 16px; font-size: 16px; border-radius: 8px; margin-bottom: 16px;" 
                               autocomplete="current-password" autofocus>
                        <button type="submit" class="btn btn-primary w-100" 
                                style="padding: 12px; font-size: 16px; border-radius: 8px; background: #6366f1; border: none;">
                            <i class="fas fa-sign-in-alt me-2"></i>Login
                        </button>
                        <div id="authError" style="color: #ef4444; margin-top: 12px; text-align: center; display: none;">
                            Incorrect password
                        </div>
                    </form>
                </div>
            `;

            document.body.appendChild(overlay);
            document.body.style.overflow = 'hidden';

            const form = document.getElementById('authForm');
            const passwordInput = document.getElementById('authPassword');
            const errorDiv = document.getElementById('authError');

            form.addEventListener('submit', async (e) => {
                e.preventDefault();
                const password = passwordInput.value;
                
                if (await verifyPassword(password)) {
                    sessionStorage.setItem(AUTH_KEY, PASSWORD_HASH);
                    overlay.remove();
                    document.body.style.overflow = '';
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
        // Hide body until authenticated
        document.body.style.visibility = 'hidden';

        if (!isPasswordAuthenticated()) {
            await showPasswordPrompt();
        }

        // Show the page
        document.body.style.visibility = 'visible';
    }

    // Run auth on page load
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', authenticate);
    } else {
        authenticate();
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
