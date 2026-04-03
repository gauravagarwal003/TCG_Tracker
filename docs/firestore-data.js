/**
 * firestore-data.js - Firestore CRUD operations for TCG Tracker
 * 
 * Handles per-user collections:
 * - users/{uid}/transactions
 * - users/{uid}/holdings (derived view)
 * - active_products (shared product index)
 */

import {
    getFirestore,
    collection,
    query,
    where,
    getDocs,
    getDoc,
    setDoc,
    updateDoc,
    deleteDoc,
    doc,
    arrayUnion,
    arrayRemove,
    writeBatch,
} from "https://www.gstatic.com/firebasejs/10.12.5/firebase-firestore.js";

let db = null;

export const LEGACY_OWNER_EMAIL = "gagarwal003@gmail.com";
const LEGACY_SEED_URLS = [
    "https://raw.githubusercontent.com/gauravagarwal003/TCG_Tracker/main/transactions.json",
    "data/transactions.json",
];

export function initDB(firebaseDB) {
    db = firebaseDB;
}

/**
 * Get current user's transactions
 */
export async function getUserTransactions(uid) {
    if (!db || !uid) return [];
    try {
        const txnsRef = collection(db, `users/${uid}/transactions`);
        const q = query(txnsRef);
        const snapshot = await getDocs(q);
        return snapshot.docs.map((doc) => ({
            id: doc.id,
            ...doc.data(),
        })).sort((a, b) => String(b.date_received || '').localeCompare(String(a.date_received || '')));
    } catch (error) {
        console.error("Error loading transactions:", error);
        return [];
    }
}

export async function getTransactionById(uid, txnId) {
    if (!db || !uid || !txnId) return null;
    try {
        const txnRef = doc(db, `users/${uid}/transactions`, txnId);
        const snapshot = await getDoc(txnRef);
        if (!snapshot.exists()) return null;
        return {
            id: snapshot.id,
            ...snapshot.data(),
        };
    } catch (error) {
        console.error("Error loading transaction:", error);
        return null;
    }
}

export async function hasUserTransactions(uid) {
    if (!db || !uid) return false;
    const txnsRef = collection(db, `users/${uid}/transactions`);
    const snapshot = await getDocs(query(txnsRef));
    return !snapshot.empty;
}

export async function ensureLegacyDataSeeded(user) {
    if (!db || !user || user.email !== LEGACY_OWNER_EMAIL) {
        return false;
    }

    const seededRef = doc(db, `users/${user.uid}/meta`, "seeded");
    const seededSnapshot = await getDoc(seededRef);
    if (seededSnapshot.exists() && seededSnapshot.data()?.legacy_seeded) {
        return false;
    }

    if (await hasUserTransactions(user.uid)) {
        await setDoc(seededRef, {
            legacy_seeded: true,
            seeded_at: new Date().toISOString(),
            source: "existing_transactions.json",
        }, { merge: true });
        return false;
    }

    let legacyTransactions = null;
    for (const url of LEGACY_SEED_URLS) {
        try {
            const response = await fetch(url + (url.includes("?") ? "" : "?cb=" + Date.now()));
            if (!response.ok) continue;
            const parsed = await response.json();
            if (Array.isArray(parsed) && parsed.length > 0) {
                legacyTransactions = parsed;
                break;
            }
        } catch (error) {
            // try next source
        }
    }

    if (!legacyTransactions) {
        throw new Error("Could not load legacy transactions to seed your account.");
    }

    if (!Array.isArray(legacyTransactions) || legacyTransactions.length === 0) {
        await setDoc(seededRef, {
            legacy_seeded: true,
            seeded_at: new Date().toISOString(),
            source: "empty",
        }, { merge: true });
        return false;
    }

    const batch = writeBatch(db);
    for (const txn of legacyTransactions) {
        if (!txn?.id) continue;
        const txnRef = doc(db, `users/${user.uid}/transactions`, txn.id);
        batch.set(txnRef, {
            ...txn,
            migrated_from: "legacy_public_json",
            migrated_at: new Date().toISOString(),
        });
    }
    batch.set(seededRef, {
        legacy_seeded: true,
        seeded_at: new Date().toISOString(),
        source: "existing_transactions.json",
        total_seeded: legacyTransactions.length,
    }, { merge: true });
    await batch.commit();
    return true;
}

export async function saveUserTransaction(uid, txnData) {
    if (!db || !uid) throw new Error("User not authenticated");
    const txnRef = doc(collection(db, `users/${uid}/transactions`));
    await setDoc(txnRef, {
        ...txnData,
        id: txnRef.id,
        created_at: new Date().toISOString(),
        updated_at: new Date().toISOString(),
    });
    return txnRef.id;
}

/**
 * Add a new transaction
 */
export async function addTransaction(uid, txn) {
    if (!db || !uid) throw new Error("User not authenticated");
    try {
        const txnRef = doc(collection(db, `users/${uid}/transactions`));
        await setDoc(txnRef, {
            ...txn,
            id: txnRef.id,
            created_at: new Date().toISOString(),
            updated_at: new Date().toISOString(),
        });
        
        // Update active_products index
        await updateActiveProductsIndex(uid, txn, "add");
        
        return txnRef.id;
    } catch (error) {
        console.error("Error adding transaction:", error);
        throw error;
    }
}

/**
 * Update an existing transaction
 */
export async function updateTransaction(uid, txnId, updates) {
    if (!db || !uid) throw new Error("User not authenticated");
    try {
        const txnRef = doc(db, `users/${uid}/transactions`, txnId);
        const oldTxn = (await getDocs(query(collection(db, `users/${uid}/transactions`), where("id", "==", txnId)))).docs[0]?.data();
        
        await updateDoc(txnRef, {
            ...updates,
            updated_at: new Date().toISOString(),
        });
        
        // Update active_products index
        if (oldTxn) {
            await updateActiveProductsIndex(uid, oldTxn, "remove");
        }
        await updateActiveProductsIndex(uid, updates, "add");
        
        return txnId;
    } catch (error) {
        console.error("Error updating transaction:", error);
        throw error;
    }
}

/**
 * Delete a transaction
 */
export async function deleteTransaction(uid, txnId) {
    if (!db || !uid) throw new Error("User not authenticated");
    try {
        const txnRef = doc(db, `users/${uid}/transactions`, txnId);
        const txnSnapshot = await getDocs(query(collection(db, `users/${uid}/transactions`), where("id", "==", txnId)));
        const txn = txnSnapshot.docs[0]?.data();
        
        await deleteDoc(txnRef);
        
        // Update active_products index
        if (txn) {
            await updateActiveProductsIndex(uid, txn, "remove");
        }
        
        return true;
    } catch (error) {
        console.error("Error deleting transaction:", error);
        throw error;
    }
}

/**
 * Update active_products index to track which products are held
 * Used by daily fetch to build union of all products
 */
async function updateActiveProductsIndex(uid, txn, operation) {
    if (!db) return;
    
    const products = extractProductKeys(txn);
    if (!products.length) return;
    
    try {
        const batch = writeBatch(db);
        
        for (const [cat, gid, pid] of products) {
            const docId = `${cat}_${gid}_${pid}`;
            const productRef = doc(db, "active_products", docId);
            
            if (operation === "add") {
                // Increment or create count
                const current = (await getDocs(query(collection(db, "active_products")))).docs
                    .find((d) => d.id === docId)?.data();
                batch.set(productRef, {
                    categoryId: cat,
                    group_id: gid,
                    product_id: pid,
                    count: (current?.count || 0) + 1,
                    users: arrayUnion(uid),
                    last_updated: new Date().toISOString(),
                }, { merge: true });
            } else if (operation === "remove") {
                // Decrement count
                const current = (await getDocs(query(collection(db, "active_products")))).docs
                    .find((d) => d.id === docId)?.data();
                if (current) {
                    const newCount = Math.max(0, (current.count || 1) - 1);
                    batch.update(productRef, {
                        count: newCount,
                        users: arrayRemove(uid),
                        last_updated: new Date().toISOString(),
                    });
                }
            }
        }
        
        await batch.commit();
    } catch (error) {
        console.error("Error updating active products index:", error);
    }
}

/**
 * Extract product keys from transaction
 */
function extractProductKeys(txn) {
    const keys = [];
    
    if (txn.items) {
        for (const item of txn.items) {
            if (item.categoryId && item.group_id && item.product_id) {
                keys.push([String(item.categoryId), String(item.group_id), String(item.product_id)]);
            }
        }
    }
    
    if (txn.items_out) {
        for (const item of txn.items_out) {
            if (item.categoryId && item.group_id && item.product_id) {
                keys.push([String(item.categoryId), String(item.group_id), String(item.product_id)]);
            }
        }
    }
    
    if (txn.items_in) {
        for (const item of txn.items_in) {
            if (item.categoryId && item.group_id && item.product_id) {
                keys.push([String(item.categoryId), String(item.group_id), String(item.product_id)]);
            }
        }
    }
    
    // Deduplicate
    const seen = new Set();
    const deduped = [];
    for (const key of keys) {
        const keyStr = key.join("_");
        if (!seen.has(keyStr)) {
            seen.add(keyStr);
            deduped.push(key);
        }
    }
    
    return deduped;
}

/**
 * Get shared product metadata (via static prices from GitHub Pages)
 */
export async function getProductMapping(groupId, productId) {
    try {
        const response = await fetch("data/mappings.json?cb=" + Date.now());
        const staticMappings = response.ok ? await response.json() : [];
        const staticMatch = staticMappings.find((m) => 
            String(m.group_id) === String(groupId) && 
            String(m.product_id) === String(productId)
        );
        if (staticMatch) return staticMatch;

        if (db) {
            const mappingRef = doc(db, "product_mappings", `${groupId}_${productId}`);
            const mappingSnap = await getDoc(mappingRef);
            if (mappingSnap.exists()) return mappingSnap.data();
        }

        return null;
    } catch (error) {
        console.error("Error loading product mapping:", error);
        return null;
    }
}

export async function saveProductMapping(mapping) {
    if (!db) throw new Error("Firestore not initialized");
    const mappingRef = doc(db, "product_mappings", `${mapping.group_id}_${mapping.product_id}`);
    await setDoc(mappingRef, {
        ...mapping,
        updated_at: new Date().toISOString(),
        created_at: new Date().toISOString(),
    }, { merge: true });
    return mapping;
}

/**
 * Get all products in mappings (for search autocomplete)
 */
export async function getAllProductMappings() {
    try {
        const response = await fetch("data/mappings.json?cb=" + Date.now());
        const staticMappings = response.ok ? await response.json() : [];

        let firestoreMappings = [];
        if (db) {
            const snapshot = await getDocs(query(collection(db, "product_mappings")));
            firestoreMappings = snapshot.docs.map((docSnap) => ({ id: docSnap.id, ...docSnap.data() }));
        }

        const byKey = new Map();
        for (const mapping of [...staticMappings, ...firestoreMappings]) {
            const key = `${String(mapping.group_id)}_${String(mapping.product_id)}`;
            if (!byKey.has(key)) byKey.set(key, mapping);
        }
        return Array.from(byKey.values());
    } catch (error) {
        console.error("Error loading mappings:", error);
        return [];
    }
}

window.TCGFirestore = {
    ensureLegacyDataSeeded,
    getUserTransactions,
    getTransactionById,
    hasUserTransactions,
    saveUserTransaction,
    addTransaction,
    updateTransaction,
    deleteTransaction,
    getAllProductMappings,
    getProductMapping,
    saveProductMapping,
};
