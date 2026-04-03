/**
 * firebase-auth.js - Firebase Google Authentication for TCG Tracker
 * 
 * Replaces password-based auth with Google Login
 */

import { onAuthStateChanged, signOut as firebaseSignOut } from "https://www.gstatic.com/firebasejs/10.12.5/firebase-auth.js";
import { initDB } from "./firestore-data.js";

(function() {
    "use strict";

    let currentUser = null;
    let authCallbacks = [];

    /**
     * Initialize Firebase auth listener
     */
    async function initFirebaseAuth() {
        // Wait for firebase-config.js to initialize
        const waitForFirebase = () => {
            return new Promise((resolve) => {
                const checkInterval = setInterval(() => {
                    if (window.TCGFirebase) {
                        clearInterval(checkInterval);
                        resolve();
                    }
                }, 100);
                setTimeout(() => {
                    clearInterval(checkInterval);
                    resolve();
                }, 5000);
            });
        };

        await waitForFirebase();

        if (!window.TCGFirebase) {
            console.error("Firebase not initialized");
            return;
        }

        // Initialize Firestore data layer
        initDB(window.TCGFirebase.db);

        // Listen for auth state changes
        window.TCGFirebase.onAuthStateChanged((user) => {
            currentUser = user;
            
            if (user) {
                // User is signed in
                sessionStorage.setItem("tcg_user_id", user.uid);
                document.documentElement.style.overflow = "";
                notifyAuthStateChange(user);
            } else {
                // User is signed out
                sessionStorage.removeItem("tcg_user_id");
                showLoginPrompt();
            }
        });
    }

    /**
     * Show login overlay
     */
    function showLoginPrompt() {
        // Prevent scrolling
        document.documentElement.style.overflow = "hidden";

        let overlay = document.getElementById("firebaseAuthOverlay");
        if (overlay) overlay.remove();

        overlay = document.createElement("div");
        overlay.id = "firebaseAuthOverlay";
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
            visibility: visible;
        `;

        overlay.innerHTML = `
            <div style="background: white; padding: 40px; border-radius: 16px; box-shadow: 0 25px 50px -12px rgba(0,0,0,0.5); max-width: 400px; width: 90%; font-family: 'Inter', -apple-system, sans-serif; text-align: center;">
                <div style="font-size: 48px; margin-bottom: 16px;">🔐</div>
                <h2 style="margin: 0 0 8px 0; color: #1e293b; font-size: 24px;">TCG Tracker</h2>
                <p style="color: #64748b; margin: 0 0 32px 0;">Sign in with Google to continue</p>
                <button id="googleLoginBtn" style="width: 100%; padding: 12px; font-size: 16px; border-radius: 8px; background: #4285f4; border: none; color: white; cursor: pointer; font-weight: 500; display: flex; align-items: center; justify-content: center; gap: 8px;">
                    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
                        <path d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z" fill="white"/>
                        <path d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z" fill="white"/>
                        <path d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z" fill="white"/>
                        <path d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z" fill="white"/>
                    </svg>
                    Sign in with Google
                </button>
                <div id="loginError" style="color: #ef4444; margin-top: 16px; text-align: center; display: none; font-size: 14px;"></div>
            </div>
        `;

        document.body.appendChild(overlay);

        const loginBtn = document.getElementById("googleLoginBtn");
        const errorDiv = document.getElementById("loginError");

        loginBtn.addEventListener("click", async () => {
            loginBtn.disabled = true;
            loginBtn.innerHTML = '<span style="display: inline-block; width: 16px; height: 16px; border: 2px solid #fff; border-radius: 50%; border-top-color: transparent; animation: spin 0.8s linear infinite;"></span> Signing in...';

            try {
                const result = await window.TCGFirebase.loginWithGoogle();
                currentUser = result.user;
                sessionStorage.setItem("tcg_user_id", result.user.uid);
                overlay.remove();
                document.documentElement.style.overflow = "";
                notifyAuthStateChange(result.user);
            } catch (error) {
                console.error("Login error:", error);
                errorDiv.style.display = "block";
                errorDiv.textContent = error.message || "Login failed. Please try again.";
                loginBtn.disabled = false;
                loginBtn.innerHTML = '<svg width="20" height="20" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg"><path d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z" fill="white"/><path d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z" fill="white"/><path d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z" fill="white"/><path d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z" fill="white"/></svg> Sign in with Google';
            }
        });
    }

    /**
     * Register callback for auth state changes
     */
    function onAuthStateChange(callback) {
        authCallbacks.push(callback);
        if (currentUser) {
            callback(currentUser);
        }
    }

    /**
     * Notify all listeners of auth state change
     */
    function notifyAuthStateChange(user) {
        authCallbacks.forEach((cb) => cb(user));
    }

    /**
     * Get current user
     */
    function getCurrentUser() {
        return currentUser;
    }

    /**
     * Logout
     */
    async function logout() {
        try {
            await window.TCGFirebase.logoutGoogle();
            currentUser = null;
            sessionStorage.removeItem("tcg_user_id");
        } catch (error) {
            console.error("Logout error:", error);
        }
    }

    // Expose to global scope
    window.TCGAuth = {
        onAuthStateChange,
        getCurrentUser,
        logout,
        init: initFirebaseAuth,
    };

    // Initialize when DOM is ready
    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", initFirebaseAuth);
    } else {
        initFirebaseAuth();
    }
})();
