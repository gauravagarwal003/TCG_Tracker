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
    setDoc,
    updateDoc,
    deleteDoc,
    doc,
    arrayUnion,
    arrayRemove,
    writeBatch,
} from "https://www.gstatic.com/firebasejs/10.12.5/firebase-firestore.js";

let db = null;

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
        }));
    } catch (error) {
        console.error("Error loading transactions:", error);
        return [];
    }
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
        if (!response.ok) return null;
        const mappings = await response.json();
        return mappings.find((m) => 
            String(m.group_id) === String(groupId) && 
            String(m.product_id) === String(productId)
        );
    } catch (error) {
        console.error("Error loading product mapping:", error);
        return null;
    }
}

/**
 * Get all products in mappings (for search autocomplete)
 */
export async function getAllProductMappings() {
    try {
        const response = await fetch("data/mappings.json?cb=" + Date.now());
        if (!response.ok) return [];
        return await response.json();
    } catch (error) {
        console.error("Error loading mappings:", error);
        return [];
    }
}
