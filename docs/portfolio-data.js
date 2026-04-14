const PRICE_CACHE = new Map();
let MAPPINGS_CACHE = null;

export async function loadMappings() {
    if (MAPPINGS_CACHE) return MAPPINGS_CACHE;
    try {
        const staticPromise = fetch('data/mappings.json?cb=' + Date.now())
            .then((resp) => (resp.ok ? resp.json() : []))
            .catch(() => []);
        const firestorePromise = (globalThis?.TCGFirestore?.getAllProductMappings)
            ? globalThis.TCGFirestore.getAllProductMappings().catch(() => [])
            : Promise.resolve([]);

        const [staticMappings, firestoreMappings] = await Promise.all([staticPromise, firestorePromise]);
        const merged = new Map();
        for (const mapping of [...(Array.isArray(staticMappings) ? staticMappings : []), ...(Array.isArray(firestoreMappings) ? firestoreMappings : [])]) {
            if (!mapping || mapping.group_id == null || mapping.product_id == null) continue;
            const key = asKey(mapping.categoryId || 3, mapping.group_id, mapping.product_id);
            if (!merged.has(key)) merged.set(key, mapping);
        }

        MAPPINGS_CACHE = Array.from(merged.values());
        return MAPPINGS_CACHE;
    } catch (error) {
        console.error('Failed to load mappings:', error);
        return [];
    }
}

function asKey(categoryId, groupId, productId) {
    return `${String(categoryId)}|${String(groupId)}|${String(productId)}`;
}

function asProductKey(groupId, productId) {
    return `${String(groupId)}|${String(productId)}`;
}

function normalizeCategoryId(categoryId) {
    if (categoryId == null || categoryId === '') return null;
    const value = Number(categoryId);
    return Number.isFinite(value) ? String(value) : String(categoryId);
}

function buildMappingByProduct(mappings) {
    const byProduct = new Map();
    for (const mapping of mappings || []) {
        if (!mapping || mapping.group_id == null || mapping.product_id == null) continue;
        const productKey = asProductKey(mapping.group_id, mapping.product_id);
        const current = byProduct.get(productKey);
        const nextCategoryId = normalizeCategoryId(mapping.categoryId);
        const currentCategoryId = normalizeCategoryId(current?.categoryId);
        if (!current || (currentCategoryId == null && nextCategoryId != null)) {
            byProduct.set(productKey, mapping);
        }
    }
    return byProduct;
}

function normalizeProductItem(item, mappingByProduct) {
    if (!item || item.group_id == null || item.product_id == null) return item;
    const mapping = mappingByProduct.get(asProductKey(item.group_id, item.product_id)) || null;
    const categoryId = normalizeCategoryId(mapping?.categoryId) ?? normalizeCategoryId(item.categoryId);
    return {
        ...item,
        categoryId,
        name: item.name || mapping?.name || '',
        imageUrl: item.imageUrl || mapping?.imageUrl || '',
        url: item.url || mapping?.url || '',
    };
}

function normalizeTransactions(transactions, mappings) {
    const mappingByProduct = buildMappingByProduct(mappings);
    return (transactions || []).map((txn) => ({
        ...txn,
        items: (txn.items || []).map((item) => normalizeProductItem(item, mappingByProduct)),
        items_in: (txn.items_in || []).map((item) => normalizeProductItem(item, mappingByProduct)),
        items_out: (txn.items_out || []).map((item) => normalizeProductItem(item, mappingByProduct)),
    }));
}

function parseDate(dateStr) {
    return new Date(`${dateStr}T00:00:00Z`);
}

function formatDate(date) {
    return date.toISOString().slice(0, 10);
}

function addDays(date, days) {
    const next = new Date(date.getTime());
    next.setUTCDate(next.getUTCDate() + days);
    return next;
}

export function extractProductKeys(transactions) {
    const keys = new Set();
    for (const txn of transactions || []) {
        if (txn.type === 'TRADE') {
            for (const item of (txn.items_out || [])) {
                if (item?.categoryId != null && item?.group_id != null && item?.product_id != null) {
                    keys.add(asKey(item.categoryId, item.group_id, item.product_id));
                }
            }
            for (const item of (txn.items_in || [])) {
                if (item?.categoryId != null && item?.group_id != null && item?.product_id != null) {
                    keys.add(asKey(item.categoryId, item.group_id, item.product_id));
                }
            }
        } else {
            for (const item of (txn.items || [])) {
                if (item?.categoryId != null && item?.group_id != null && item?.product_id != null) {
                    keys.add(asKey(item.categoryId, item.group_id, item.product_id));
                }
            }
        }
    }
    return Array.from(keys).map((value) => {
        const [categoryId, groupId, productId] = value.split('|');
        return { categoryId, groupId, productId, key: value };
    });
}

function loadPriceMap(categoryId, groupId, productId) {
    const key = asKey(categoryId, groupId, productId);
    if (!PRICE_CACHE.has(key)) {
        PRICE_CACHE.set(
            key,
            fetch(`prices/${categoryId}/${groupId}/${productId}.json?cb=${Date.now()}`)
                .then((resp) => (resp.ok ? resp.json() : {}))
                .catch(() => ({}))
        );
    }
    return PRICE_CACHE.get(key);
}

function getLatestPriceOnOrBefore(priceMap, dateStr) {
    let bestDate = null;
    let bestPrice = 0;
    for (const [d, price] of Object.entries(priceMap || {})) {
        if (!price || price <= 0) continue;
        if (d <= dateStr && (!bestDate || d > bestDate)) {
            bestDate = d;
            bestPrice = Number(price) || 0;
        }
    }
    return bestPrice;
}

function getLatestPriceDate(priceMaps) {
    let bestDate = null;
    for (const priceMap of priceMaps.values()) {
        for (const [d, price] of Object.entries(priceMap || {})) {
            if (!price || Number(price) <= 0) continue;
            if (!bestDate || d > bestDate) {
                bestDate = d;
            }
        }
    }
    return bestDate;
}

function computeInventoryTimeline(transactions) {
    const deltas = new Map();
    for (const txn of transactions || []) {
        const txnDate = txn.date_received;
        const txnType = String(txn.type || '').toUpperCase();
        if (!txnDate) continue;
        const addDelta = (item, delta) => {
            if (!item?.categoryId || !item?.group_id || !item?.product_id) return;
            const key = asKey(item.categoryId, item.group_id, item.product_id);
            if (!deltas.has(key)) deltas.set(key, []);
            deltas.get(key).push([txnDate, delta]);
        };

        if (txnType === 'BUY') {
            for (const item of (txn.items || [])) addDelta(item, Number(item.quantity || 0));
        } else if (txnType === 'SELL' || txnType === 'OPEN') {
            for (const item of (txn.items || [])) addDelta(item, -Number(item.quantity || 0));
        } else if (txnType === 'TRADE') {
            for (const item of (txn.items_out || [])) addDelta(item, -Number(item.quantity || 0));
            for (const item of (txn.items_in || [])) addDelta(item, Number(item.quantity || 0));
        }
    }

    const inventory = new Map();
    for (const [key, changes] of deltas.entries()) {
        changes.sort((a, b) => a[0].localeCompare(b[0]));
        let running = 0;
        const snapshot = new Map();
        for (const [dateStr, delta] of changes) {
            running += delta;
            snapshot.set(dateStr, running);
        }
        inventory.set(key, snapshot);
    }
    return inventory;
}

function getQuantityOnDate(inventoryForProduct, dateStr) {
    if (!inventoryForProduct) return 0;
    let bestDate = null;
    for (const d of inventoryForProduct.keys()) {
        if (d <= dateStr && (!bestDate || d > bestDate)) {
            bestDate = d;
        }
    }
    return bestDate ? (inventoryForProduct.get(bestDate) || 0) : 0;
}

function computeCostBasisDeltas(transactions) {
    const deltas = new Map();
    const add = (dateStr, delta) => {
        if (!deltas.has(dateStr)) deltas.set(dateStr, 0);
        deltas.set(dateStr, deltas.get(dateStr) + delta);
    };
    for (const txn of transactions || []) {
        const type = String(txn.type || '').toUpperCase();
        const dateStr = txn.date_received;
        if (!dateStr) continue;
        if (type === 'BUY') add(dateStr, Number(txn.amount || 0));
        else if (type === 'SELL') add(dateStr, -Number(txn.amount || 0));
        else if (type === 'TRADE') {
            add(dateStr, -Number(txn.cost_basis_out || 0));
            add(dateStr, Number(txn.cost_basis_in || 0));
        }
    }
    return deltas;
}

async function loadPriceMaps(keys) {
    const entries = await Promise.all(keys.map(async (key) => {
        const priceMap = await loadPriceMap(key.categoryId, key.groupId, key.productId);
        return [key.key, priceMap || {}];
    }));
    return new Map(entries);
}

export async function computeDashboardSnapshot(transactions) {
    const rawTxns = Array.isArray(transactions) ? transactions.slice() : [];
    if (!rawTxns.length) {
        return { summary: {}, holdings: [], latestDate: null };
    }

    const mappings = await loadMappings();
    const txns = normalizeTransactions(rawTxns, mappings);
    const mappingByKey = new Map(
        mappings.map((m) => [asKey(m.categoryId || 3, m.group_id, m.product_id), m])
    );
    const metadataByKey = new Map();
    for (const txn of txns) {
        const collect = (item) => {
            if (item?.categoryId == null || item?.group_id == null || item?.product_id == null) return;
            const key = asKey(item.categoryId, item.group_id, item.product_id);
            const existing = metadataByKey.get(key) || {};
            metadataByKey.set(key, {
                name: item.name || existing.name || '',
                imageUrl: item.imageUrl || existing.imageUrl || '',
                url: item.url || existing.url || '',
            });
        };

        for (const item of (txn.items || [])) collect(item);
        for (const item of (txn.items_out || [])) collect(item);
        for (const item of (txn.items_in || [])) collect(item);
    }

    const keys = extractProductKeys(txns);
    const priceMaps = await loadPriceMaps(keys);
    const inventory = computeInventoryTimeline(txns);
    const costBasisDeltas = computeCostBasisDeltas(txns);

    const sortedTxDates = txns.map((t) => t.date_received).filter(Boolean).sort();
    const startDate = parseDate(sortedTxDates[0]);
    const todayDateStr = formatDate(new Date());
    const lastPriceDate = getLatestPriceDate(priceMaps);
    const endDateStr = lastPriceDate && lastPriceDate < todayDateStr ? lastPriceDate : todayDateStr;
    const endDate = parseDate(endDateStr);

    const summary = {};
    const lastKnownPrice = new Map();
    let runningCostBasis = 0;

    for (let current = startDate; current <= endDate; current = addDays(current, 1)) {
        const dateStr = formatDate(current);
        runningCostBasis += Number(costBasisDeltas.get(dateStr) || 0);
        let totalValue = 0;

        for (const [key, inv] of inventory.entries()) {
            const qty = getQuantityOnDate(inv, dateStr);
            if (qty <= 0) continue;
            const priceMap = priceMaps.get(key) || {};
            const exact = priceMap[dateStr];
            if (exact && exact > 0) {
                lastKnownPrice.set(key, Number(exact));
                totalValue += qty * Number(exact);
            } else if (lastKnownPrice.has(key)) {
                totalValue += qty * Number(lastKnownPrice.get(key));
            }
        }

        summary[dateStr] = {
            total_value: Math.round(totalValue * 100) / 100,
            cost_basis: Math.round(runningCostBasis * 100) / 100,
        };
    }

    const holdings = [];
    for (const [key, inv] of inventory.entries()) {
        const qty = getQuantityOnDate(inv, endDateStr);
        if (qty <= 0) continue;
        const [categoryId, groupId, productId] = key.split('|');
        const priceMap = priceMaps.get(key) || {};
        const latestPrice = getLatestPriceOnOrBefore(priceMap, endDateStr);
        const mapping = mappingByKey.get(key) || null;
        const metadata = metadataByKey.get(key) || null;

        let buyUnits = 0;
        let buyCost = 0;
        let tradeUnits = 0;
        let tradeCost = 0;
        let viaTrade = false;

        for (const txn of txns) {
            const type = String(txn.type || '').toUpperCase();
            const dateStr = txn.date_received || '';
            if (type === 'BUY') {
                const items = txn.items || [];
                const totalQty = items.reduce((sum, item) => sum + Number(item.quantity || 0), 0);
                for (const item of items) {
                    if (asKey(item.categoryId, item.group_id, item.product_id) !== key) continue;
                    const itemQty = Number(item.quantity || 0);
                    const prorated = totalQty > 0 ? (Number(txn.amount || 0) * (itemQty / totalQty)) : 0;
                    buyUnits += itemQty;
                    buyCost += prorated;
                }
            } else if (type === 'TRADE' && dateStr) {
                for (const item of (txn.items_in || [])) {
                    if (asKey(item.categoryId, item.group_id, item.product_id) !== key) continue;
                    const itemQty = Number(item.quantity || 0);
                    const priceAtTrade = getLatestPriceOnOrBefore(priceMap, dateStr);
                    if (priceAtTrade > 0) {
                        viaTrade = true;
                        tradeUnits += itemQty;
                        tradeCost += itemQty * priceAtTrade;
                    }
                }
            }
        }

        const totalUnits = buyUnits + tradeUnits;
        const totalCost = buyCost + tradeCost;
        const avgBuyPrice = totalUnits > 0 ? Math.round((totalCost / totalUnits) * 100) / 100 : null;

        holdings.push({
            categoryId,
            group_id: groupId,
            product_id: productId,
            name: mapping?.name || metadata?.name || `Unknown (${groupId}/${productId})`,
            imageUrl: mapping?.imageUrl || metadata?.imageUrl || '',
            url: mapping?.url || metadata?.url || '',
            quantity: qty,
            latest_price: latestPrice,
            total_value: Math.round(qty * latestPrice * 100) / 100,
            avg_buy_price: avgBuyPrice,
            via_trade: viaTrade,
        });
    }

    holdings.sort((a, b) => b.latest_price - a.latest_price);

    return { summary, holdings, latestDate: endDateStr };
}
