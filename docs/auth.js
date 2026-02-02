// Simple password protection for GitHub Pages
// Note: This is client-side only and not fully secure, but provides basic protection

(function() {
    // Password hash (SHA-256 of your password)
    // Change this to your own password hash
    // To generate: Open browser console and run: crypto.subtle.digest('SHA-256', new TextEncoder().encode('your-password')).then(h => console.log(Array.from(new Uint8Array(h)).map(b => b.toString(16).padStart(2, '0')).join('')))
    const PASSWORD_HASH = 'e91e78805d7e65607f3c2f25f174d385dbef65f56f325ca1331e380abcd54838';
    
    // Check if user is authenticated
    const isAuthenticated = sessionStorage.getItem('poketracker_auth') === PASSWORD_HASH;
    
    if (!isAuthenticated) {
        // Hide the body content
        document.body.style.display = 'none';
        
        // Show password prompt
        const password = prompt('Enter password to access PokeTracker:');
        
        if (password) {
            // Hash the entered password
            crypto.subtle.digest('SHA-256', new TextEncoder().encode(password))
                .then(hashBuffer => {
                    const hashArray = Array.from(new Uint8Array(hashBuffer));
                    const hashHex = hashArray.map(b => b.toString(16).padStart(2, '0')).join('');
                    
                    if (hashHex === PASSWORD_HASH) {
                        // Correct password
                        sessionStorage.setItem('poketracker_auth', PASSWORD_HASH);
                        document.body.style.display = 'block';
                    } else {
                        // Wrong password
                        alert('Incorrect password');
                        window.location.href = 'about:blank';
                    }
                });
        } else {
            // No password entered
            window.location.href = 'about:blank';
        }
    } else {
        // Already authenticated
        document.body.style.display = 'block';
    }
})();
