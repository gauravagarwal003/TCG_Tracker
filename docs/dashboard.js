import { ensureLegacyDataSeeded, getUserTransactions } from './firestore-data.js';
import { computeDashboardSnapshot } from './portfolio-data.js';

function escapeHtml(str) {
    return String(str)
        .replace(/&/g, '&amp;').replace(/</g, '&lt;')
        .replace(/>/g, '&gt;').replace(/"/g, '&quot;');
}

const fmtUSD = (v) => '$' + Number(v || 0).toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 });

function getWeekAgoDate() {
    const today = new Date();
    const weekAgo = new Date(today.getTime() - 7 * 24 * 60 * 60 * 1000);
    return weekAgo.toISOString().split('T')[0];
}

function formatWeeklyChange(weekAgoPrice, currentPrice) {
    if (weekAgoPrice == null) return '—';
    const change = currentPrice - weekAgoPrice;
    const changePct = (change / weekAgoPrice) * 100;
    const color = changePct >= 0 ? '#10b981' : '#ef4444';
    return `<span style="color:${color}">${changePct >= 0 ? '+' : ''}${changePct.toFixed(1)}%</span>`;
}

async function loadWeeklyChanges() {
    const rows = document.querySelectorAll('tbody tr[data-product-id]');
    const weekAgoDate = getWeekAgoDate();

    rows.forEach(async (row) => {
        const categoryId = row.getAttribute('data-category-id');
        const groupId = row.getAttribute('data-group-id');
        const productId = row.getAttribute('data-product-id');
        const currentPrice = parseFloat(row.getAttribute('data-latest-price'));

        try {
            const response = await fetch(`prices/${categoryId}/${groupId}/${productId}.json?cb=${Date.now()}`);
            if (!response.ok) return;
            const priceData = await response.json();
            const weekAgoPrice = priceData[weekAgoDate];
            const cell = row.querySelector('.week-change-cell');
            if (cell) {
                cell.innerHTML = formatWeeklyChange(weekAgoPrice, currentPrice);
            }
        } catch (error) {
            console.error(`Error loading prices for product ${productId}:`, error);
        }
    });
}

function renderDashboard(snapshot) {
    const { summary, holdings } = snapshot;
    const summaryDates = Object.keys(summary || {}).sort();
    const latestDate = summaryDates[summaryDates.length - 1] || null;
    const latestVal = latestDate ? Number(summary[latestDate].total_value || 0) : 0;
    const latestCost = latestDate ? Number(summary[latestDate].cost_basis || 0) : 0;
    const gainLoss = latestVal - latestCost;
    const returnPct = latestCost > 0 ? (gainLoss / latestCost) * 100 : 0;
    const glColour = gainLoss >= 0 ? '#10b981' : '#ef4444';

    document.getElementById('stat-total-value').textContent = fmtUSD(latestVal);
    document.getElementById('stat-cost-basis').textContent = fmtUSD(latestCost);
    const retEl = document.getElementById('stat-return-pct');
    retEl.textContent = (returnPct >= 0 ? '+' : '') + returnPct.toFixed(1) + '%';
    retEl.style.color = glColour;

    const tbody = document.getElementById('holdings-body');
    const countBadge = document.getElementById('holdings-count');

    if (!holdings || holdings.length === 0) {
        tbody.innerHTML = '<tr><td colspan="8" class="text-center py-4 text-muted">No holdings yet.</td></tr>';
    } else {
        tbody.innerHTML = holdings.map((item) => {
            const thumb = item.imageUrl
                ? `<img src="${escapeHtml(item.imageUrl)}" alt="" class="product-thumb">`
                : '<div class="product-thumb-placeholder"></div>';
            const name = item.url
                ? `<a href="${escapeHtml(item.url)}" target="_blank" class="text-decoration-none">${escapeHtml(item.name)}</a>`
                : escapeHtml(item.name);
            const avgBuy = item.avg_buy_price != null ? `$${Number(item.avg_buy_price).toFixed(2)}` : '—';
            let gainPctHtml = '—';
            if (item.avg_buy_price != null && item.avg_buy_price > 0) {
                const pct = ((item.latest_price - item.avg_buy_price) / item.avg_buy_price) * 100;
                const glColor = pct >= 0 ? '#10b981' : '#ef4444';
                gainPctHtml = `<span style="color:${glColor}">${pct >= 0 ? '+' : '-'}${Math.abs(pct).toFixed(1)}%</span>`;
            }
            return `<tr data-product-id="${item.product_id}" data-category-id="${item.categoryId}" data-group-id="${item.group_id}" data-latest-price="${item.latest_price}">
                <td>${thumb}</td>
                <td class="fw-medium">${name}</td>
                <td class="text-end">${Math.round(item.quantity)}</td>
                <td class="text-end">${avgBuy}</td>
                <td class="text-end">${fmtUSD(item.latest_price)}</td>
                <td class="text-end">${gainPctHtml}</td>
                <td class="text-end week-change-cell">—</td>
                <td class="text-end fw-bold">${fmtUSD(item.total_value)}</td>
            </tr>`;
        }).join('');
        countBadge.textContent = `${holdings.length} items`;
        loadWeeklyChanges();
    }

    const dates = summaryDates;
    const values = dates.map((d) => summary[d].total_value);
    const costBasis = dates.map((d) => summary[d].cost_basis);

    if (window.Plotly) {
        Plotly.newPlot('portfolioChart', [
            {
                x: dates,
                y: values,
                type: 'scatter',
                mode: 'lines',
                name: 'Total Value',
                line: { color: '#10b981', width: 2 },
                fill: 'tozeroy',
                fillcolor: 'rgba(16, 185, 129, 0.12)',
            },
            {
                x: dates,
                y: costBasis,
                type: 'scatter',
                mode: 'lines',
                name: 'Cost Basis',
                line: { color: '#ef4444', width: 2, dash: 'dot' },
            },
        ], {
            margin: { t: 30, r: 20, b: 40, l: 60 },
            xaxis: { title: '', color: '#94a3b8', gridcolor: '#334155', linecolor: '#334155' },
            yaxis: { title: '', tickprefix: '$', color: '#94a3b8', gridcolor: '#334155', linecolor: '#334155' },
            legend: { x: 0.02, y: 0.98, font: { color: '#e2e8f0' } },
            hovermode: 'x unified',
            hoverlabel: { bgcolor: '#0f1114', bordercolor: '#222222', font: { color: '#e6eef8', size: 12 } },
            plot_bgcolor: 'rgba(0,0,0,0)',
            paper_bgcolor: 'rgba(0,0,0,0)',
            font: { color: '#e2e8f0' },
        }, { responsive: true });
    }
}

function setupNavbarAuth() {
    const logoutBtn = document.getElementById('logoutBtn');
    const userInfo = document.getElementById('userInfo');
    const userEmail = document.getElementById('userEmail');

    if (logoutBtn) {
        logoutBtn.addEventListener('click', async () => {
            if (window.TCGAuth) {
                await window.TCGAuth.logout();
                window.location.reload();
            }
        });
    }

    if (window.TCGAuth) {
        window.TCGAuth.onAuthStateChange((user) => {
            if (user) {
                if (userEmail) userEmail.textContent = user.email || user.uid;
                if (userInfo) userInfo.style.display = 'flex';
            } else if (userInfo) {
                userInfo.style.display = 'none';
            }
        });
    }
}

async function loadUserDashboard(user) {
    const statusEl = document.getElementById('holdings-count');
    if (statusEl) statusEl.textContent = 'Loading...';

    await ensureLegacyDataSeeded(user);
    const transactions = await getUserTransactions(user.uid);
    const snapshot = await computeDashboardSnapshot(transactions);
    renderDashboard(snapshot);
}

function bootstrapDashboard() {
    setupNavbarAuth();
    if (!window.TCGAuth) return;
    window.TCGAuth.onAuthStateChange(async (user) => {
        if (user) {
            await loadUserDashboard(user);
        }
    });
}

bootstrapDashboard();
