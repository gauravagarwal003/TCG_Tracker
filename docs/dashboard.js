import { ensureLegacyDataSeeded, getUserTransactions } from './firestore-data.js';
import { computeDashboardSnapshot } from './portfolio-data.js';

function escapeHtml(str) {
    return String(str)
        .replace(/&/g, '&amp;').replace(/</g, '&lt;')
        .replace(/>/g, '&gt;').replace(/"/g, '&quot;');
}

const fmtUSD = (v) => '$' + Number(v || 0).toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 });

let currentSnapshot = null;
let activeTimeframe = 'ALL';
let activeAllocationMode = 'franchise';

function getFranchiseName(catId) {
    const id = String(catId);
    if (id === '3') return 'Pokémon (English)';
    if (id === '85') return 'Pokémon (Japanese)';
    if (id === '68') return 'One Piece';
    if (id === '80') return 'Dragon Ball Super';
    return 'Other TCGs';
}

function getProductType(name) {
    const n = (name || '').toLowerCase();
    if (n.includes('booster box') || n.includes('booster display') || n.includes('high class booster')) return 'Booster Boxes';
    if (n.includes('elite trainer box') || n.includes('etb')) return 'Elite Trainer Boxes';
    if (n.includes('booster bundle')) return 'Booster Bundles';
    if (n.includes('tin')) return 'Tins';
    if (n.includes('collection') || n.includes('poster') || n.includes('surprise box') || n.includes('pouch')) return 'Collection Sets';
    if (n.includes('blister') || n.includes('sleeved') || n.includes('booster pack')) return 'Packs & Blisters';
    if (n.includes('deck')) return 'Starter Decks';
    return 'Other Products';
}

function renderAllocationChart(holdings, mode = 'franchise') {
    if (!window.Plotly || !holdings || holdings.length === 0) return;

    const groupTotals = {};
    for (const item of holdings) {
        const key = mode === 'franchise' ? getFranchiseName(item.categoryId) : getProductType(item.name);
        groupTotals[key] = (groupTotals[key] || 0) + Number(item.total_value || 0);
    }

    const sortedEntries = Object.entries(groupTotals).sort((a, b) => b[1] - a[1]);
    const labels = sortedEntries.map(e => e[0]);
    const values = sortedEntries.map(e => Math.round(e[1] * 100) / 100);

    const franchiseColors = {
        'Pokémon (English)': '#3b82f6',
        'Pokémon (Japanese)': '#8b5cf6',
        'One Piece': '#f59e0b',
        'Dragon Ball Super': '#ef4444',
        'Other TCGs': '#10b981'
    };

    const typeColors = {
        'Booster Boxes': '#3b82f6',
        'Elite Trainer Boxes': '#8b5cf6',
        'Booster Bundles': '#10b981',
        'Collection Sets': '#ec4899',
        'Tins': '#f59e0b',
        'Packs & Blisters': '#06b6d4',
        'Starter Decks': '#64748b',
        'Other Products': '#a855f7'
    };

    const colorMap = mode === 'franchise' ? franchiseColors : typeColors;
    const defaultPalette = ['#3b82f6', '#8b5cf6', '#10b981', '#f59e0b', '#ec4899', '#06b6d4', '#64748b', '#a855f7'];
    const colors = labels.map((l, i) => colorMap[l] || defaultPalette[i % defaultPalette.length]);

    Plotly.react('allocationChart', [{
        labels: labels,
        values: values,
        type: 'pie',
        hole: 0.55,
        textinfo: 'percent',
        textposition: 'inside',
        hoverinfo: 'label+value+percent',
        hovertemplate: '<b>%{label}</b><br>Value: $%{value:,.2f}<br>Share: %{percent}<extra></extra>',
        marker: { colors: colors, line: { color: '#0f172a', width: 2 } },
        textfont: { color: '#ffffff', size: 12, family: 'Inter, sans-serif' }
    }], {
        margin: { t: 10, r: 10, b: 30, l: 10 },
        showlegend: true,
        legend: {
            orientation: 'h',
            x: 0.5,
            xanchor: 'center',
            y: -0.15,
            font: { color: '#94a3b8', size: 12 }
        },
        hoverlabel: { bgcolor: '#0f1114', bordercolor: '#334155', font: { color: '#e6eef8', size: 12 } },
        plot_bgcolor: 'rgba(0,0,0,0)',
        paper_bgcolor: 'rgba(0,0,0,0)',
    }, { responsive: true, displayModeBar: false });
}

function updatePortfolioChart(summary, timeframe = 'ALL') {
    if (!window.Plotly || !summary) return;

    const summaryDates = Object.keys(summary).sort();
    if (summaryDates.length === 0) return;

    const latestDate = summaryDates[summaryDates.length - 1];
    let startDate = summaryDates[0];

    const targetDate = new Date(latestDate);
    if (timeframe === '1M') targetDate.setUTCDate(targetDate.getUTCDate() - 30);
    else if (timeframe === '3M') targetDate.setUTCDate(targetDate.getUTCDate() - 90);
    else if (timeframe === '6M') targetDate.setUTCDate(targetDate.getUTCDate() - 180);
    else if (timeframe === '1Y') targetDate.setUTCDate(targetDate.getUTCDate() - 365);
    else if (timeframe === 'YTD') {
        startDate = `${latestDate.slice(0, 4)}-01-01`;
    }

    if (timeframe !== 'ALL' && timeframe !== 'YTD') {
        startDate = targetDate.toISOString().slice(0, 10);
    }

    const filteredDates = summaryDates.filter(d => d >= startDate);
    const chartDates = filteredDates.length > 0 ? filteredDates : summaryDates;

    const values = chartDates.map(d => summary[d].total_value);
    const costBasis = chartDates.map(d => summary[d].cost_basis);

    // Period performance
    const perfEl = document.getElementById('timeframe-performance');
    if (perfEl && values.length > 1) {
        const startVal = values[0];
        const endVal = values[values.length - 1];
        const diff = endVal - startVal;
        const diffPct = startVal > 0 ? (diff / startVal) * 100 : 0;
        const sign = diff >= 0 ? '+' : '';
        const color = diff >= 0 ? '#10b981' : '#ef4444';
        perfEl.innerHTML = `<span style="color:${color}">${timeframe}: ${sign}${fmtUSD(diff)} (${sign}${diffPct.toFixed(1)}%)</span>`;
    } else if (perfEl) {
        perfEl.textContent = '';
    }

    Plotly.react('portfolioChart', [
        {
            x: chartDates,
            y: values,
            type: 'scatter',
            mode: 'lines',
            name: 'Total Value',
            line: { color: '#10b981', width: 2 },
            fill: 'tozeroy',
            fillcolor: 'rgba(16, 185, 129, 0.12)',
        },
        {
            x: chartDates,
            y: costBasis,
            type: 'scatter',
            mode: 'lines',
            name: 'Cost Basis',
            line: { color: '#ef4444', width: 2, dash: 'dot' },
        },
    ], {
        margin: { t: 20, r: 20, b: 40, l: 60 },
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

function renderDashboard(snapshot) {
    currentSnapshot = snapshot;
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

            // Directly rendered precomputed 1-week change (zero network requests)
            let weekChangeHtml = '—';
            if (item.change_7d_pct != null) {
                const wColor = item.change_7d_pct >= 0 ? '#10b981' : '#ef4444';
                weekChangeHtml = `<span style="color:${wColor}">${item.change_7d_pct >= 0 ? '+' : ''}${item.change_7d_pct.toFixed(1)}%</span>`;
            }

            return `<tr data-product-id="${item.product_id}" data-category-id="${item.categoryId}" data-group-id="${item.group_id}" data-latest-price="${item.latest_price}">
                <td>${thumb}</td>
                <td class="fw-medium">${name}</td>
                <td class="text-end">${Math.round(item.quantity)}</td>
                <td class="text-end">${avgBuy}</td>
                <td class="text-end">${fmtUSD(item.latest_price)}</td>
                <td class="text-end">${gainPctHtml}</td>
                <td class="text-end week-change-cell">${weekChangeHtml}</td>
                <td class="text-end fw-bold">${fmtUSD(item.total_value)}</td>
            </tr>`;
        }).join('');
        countBadge.textContent = `${holdings.length} items`;
    }

    updatePortfolioChart(summary, activeTimeframe);
    renderAllocationChart(holdings, activeAllocationMode);
}

function setupEventListeners() {
    // Timeframe selector buttons
    const tfButtons = document.querySelectorAll('#timeframeButtons button');
    tfButtons.forEach(btn => {
        btn.addEventListener('click', () => {
            tfButtons.forEach(b => b.classList.remove('active'));
            btn.classList.add('active');
            activeTimeframe = btn.dataset.tf;
            if (currentSnapshot && currentSnapshot.summary) {
                updatePortfolioChart(currentSnapshot.summary, activeTimeframe);
            }
        });
    });

    // Allocation toggle buttons
    const allocFranchiseBtn = document.getElementById('allocByFranchise');
    const allocTypeBtn = document.getElementById('allocByType');
    if (allocFranchiseBtn && allocTypeBtn) {
        allocFranchiseBtn.addEventListener('click', () => {
            allocFranchiseBtn.classList.add('active');
            allocTypeBtn.classList.remove('active');
            activeAllocationMode = 'franchise';
            if (currentSnapshot && currentSnapshot.holdings) {
                renderAllocationChart(currentSnapshot.holdings, 'franchise');
            }
        });
        allocTypeBtn.addEventListener('click', () => {
            allocTypeBtn.classList.add('active');
            allocFranchiseBtn.classList.remove('active');
            activeAllocationMode = 'type';
            if (currentSnapshot && currentSnapshot.holdings) {
                renderAllocationChart(currentSnapshot.holdings, 'type');
            }
        });
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

async function loadStaticDashboard() {
    try {
        const [sumResp, holdResp] = await Promise.all([
            fetch('data/daily_summary.json?cb=' + Date.now()),
            fetch('data/holdings.json?cb=' + Date.now())
        ]);
        if (sumResp.ok && holdResp.ok) {
            const summary = await sumResp.json();
            const holdings = await holdResp.json();
            renderDashboard({ summary, holdings });
        }
    } catch (e) {
        console.error('Failed to load static dashboard data:', e);
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
    setupEventListeners();

    if (!window.TCGAuth) {
        loadStaticDashboard();
        return;
    }

    let authResolved = false;
    window.TCGAuth.onAuthStateChange(async (user) => {
        authResolved = true;
        if (user) {
            await loadUserDashboard(user);
        } else {
            await loadStaticDashboard();
        }
    });

    // Fallback if auth takes long or runs offline
    setTimeout(() => {
        if (!authResolved && !currentSnapshot) {
            loadStaticDashboard();
        }
    }, 1500);
}

bootstrapDashboard();
