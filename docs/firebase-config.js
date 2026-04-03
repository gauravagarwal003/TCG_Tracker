import { initializeApp } from "https://www.gstatic.com/firebasejs/10.12.5/firebase-app.js";
import {
    getAuth,
    GoogleAuthProvider,
    signInWithPopup,
    signOut,
    onAuthStateChanged,
} from "https://www.gstatic.com/firebasejs/10.12.5/firebase-auth.js";
import {
    getFirestore,
} from "https://www.gstatic.com/firebasejs/10.12.5/firebase-firestore.js";
import { getAnalytics, isSupported } from "https://www.gstatic.com/firebasejs/10.12.5/firebase-analytics.js";

const firebaseConfig = {
    apiKey: "AIzaSyCPrkd6u3GTkE907EkUVQf3i7r4WhACctg",
    authDomain: "tcg-tracker-b1fb3.firebaseapp.com",
    projectId: "tcg-tracker-b1fb3",
    storageBucket: "tcg-tracker-b1fb3.firebasestorage.app",
    messagingSenderId: "1051539984845",
    appId: "1:1051539984845:web:eb15b594d2a687a4b03484",
    measurementId: "G-803J3HNGL7",
};

const app = initializeApp(firebaseConfig);
const auth = getAuth(app);
const db = getFirestore(app);
const provider = new GoogleAuthProvider();

let analytics = null;
isSupported().then((supported) => {
    if (supported) {
        analytics = getAnalytics(app);
    }
}).catch(() => {
    analytics = null;
});

async function loginWithGoogle() {
    return signInWithPopup(auth, provider);
}

async function logoutGoogle() {
    return signOut(auth);
}

window.TCGFirebase = {
    app,
    auth,
    db,
    analytics: () => analytics,
    loginWithGoogle,
    logoutGoogle,
    onAuthStateChanged: (cb) => onAuthStateChanged(auth, cb),
};
