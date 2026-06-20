/**
 * AI Transaction Pipeline — Dashboard Application
 * Real-time monitoring, file upload, and data visualization.
 */

(() => {
    'use strict';

    // ── Configuration ──────────────────────────────────────────
    const API_BASE = '/api';
    const POLL_INTERVAL = 3000;       // 3s for batch progress
    const STATS_INTERVAL = 10000;     // 10s for stats refresh

    // ── State ──────────────────────────────────────────────────
    let currentPage = 1;
    let currentPageSize = 20;
    let activeFilters = {};
    let pollTimer = null;
    let statsTimer = null;

    // ── DOM Elements ───────────────────────────────────────────
    const $ = (sel) => document.querySelector(sel);
    const $$ = (sel) => document.querySelectorAll(sel);

    const els = {
        // Stats
        totalTransactions: $('#totalTransactions'),
        enrichedCount: $('#enrichedCount'),
        anomalyCount: $('#anomalyCount'),
        totalAmount: $('#totalAmount'),

        // Health
        healthIndicator: $('#healthIndicator'),
        healthText: $('.health-text'),

        // Upload
        uploadZone: $('#uploadZone'),
        fileInput: $('#fileInput'),
        uploadProgress: $('#uploadProgress'),
        uploadProgressText: $('#uploadProgressText'),
        uploadResult: $('#uploadResult'),

        // Batches
        batchList: $('#batchList'),

        // Categories
        categoryChart: $('#categoryChart'),

        // Anomalies
        anomalyList: $('#anomalyList'),
        anomalyBadge: $('#anomalyBadge'),

        // Transactions
        transactionsBody: $('#transactionsBody'),
        searchInput: $('#searchInput'),
        categoryFilter: $('#categoryFilter'),
        statusFilter: $('#statusFilter'),
        pagination: $('#pagination'),

        // Modal
        modalOverlay: $('#modalOverlay'),
        modalBody: $('#modalBody'),
        modalClose: $('#modalClose'),

        // Buttons
        refreshBtn: $('#refreshBtn'),
        refreshBatches: $('#refreshBatches'),

        // Toast
        toastContainer: $('#toastContainer'),
    };

    // ── API Helpers ────────────────────────────────────────────
    async function api(endpoint, options = {}) {
        try {
            const response = await fetch(`${API_BASE}${endpoint}`, {
                headers: { 'Accept': 'application/json', ...options.headers },
                ...options,
            });

            if (!response.ok) {
                const err = await response.json().catch(() => ({ detail: response.statusText }));
                throw new Error(err.detail || `HTTP ${response.status}`);
            }

            return await response.json();
        } catch (error) {
            if (error.name === 'TypeError' && error.message.includes('fetch')) {
                throw new Error('Cannot connect to API server');
            }
            throw error;
        }
    }

    // ── Number Formatting ──────────────────────────────────────
    function formatCurrency(amount) {
        const abs = Math.abs(amount);
        if (abs >= 1_000_000) return `$${(amount / 1_000_000).toFixed(1)}M`;
        if (abs >= 1_000) return `$${(amount / 1_000).toFixed(1)}K`;
        return `$${amount.toFixed(2)}`;
    }

    function formatNumber(n) {
        if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`;
        if (n >= 1_000) return `${(n / 1_000).toFixed(1)}K`;
        return n.toLocaleString();
    }

    function formatDate(dateStr) {
        return new Date(dateStr).toLocaleDateString('en-US', {
            month: 'short', day: 'numeric', year: 'numeric',
        });
    }

    function formatDateTime(dateStr) {
        return new Date(dateStr).toLocaleString('en-US', {
            month: 'short', day: 'numeric', year: 'numeric',
            hour: '2-digit', minute: '2-digit',
        });
    }

    function timeAgo(dateStr) {
        const diff = Date.now() - new Date(dateStr).getTime();
        const minutes = Math.floor(diff / 60000);
        if (minutes < 1) return 'just now';
        if (minutes < 60) return `${minutes}m ago`;
        const hours = Math.floor(minutes / 60);
        if (hours < 24) return `${hours}h ago`;
        const days = Math.floor(hours / 24);
        return `${days}d ago`;
    }

    // ── Toast Notifications ────────────────────────────────────
    function showToast(message, type = 'info') {
        const toast = document.createElement('div');
        toast.className = `toast ${type}`;
        toast.textContent = message;
        els.toastContainer.appendChild(toast);

        setTimeout(() => {
            toast.style.animation = 'toastSlideOut 0.3s ease-in forwards';
            setTimeout(() => toast.remove(), 300);
        }, 4000);
    }

    // ── Health Check ───────────────────────────────────────────
    async function checkHealth() {
        try {
            const data = await api('/health');
            els.healthIndicator.className = `health-indicator ${data.status}`;
            els.healthText.textContent = data.status === 'healthy'
                ? 'All Systems Operational'
                : data.status === 'degraded'
                    ? 'Degraded Performance'
                    : 'System Issues';
        } catch {
            els.healthIndicator.className = 'health-indicator unhealthy';
            els.healthText.textContent = 'Offline';
        }
    }

    // ── Statistics ─────────────────────────────────────────────
    async function loadStats() {
        try {
            const data = await api('/stats');

            animateValue(els.totalTransactions, data.total_transactions);
            animateValue(els.enrichedCount, data.enriched_count);
            animateValue(els.anomalyCount, data.anomaly_count);
            els.totalAmount.textContent = formatCurrency(data.total_amount);

            renderCategoryChart(data.categories);
            updateCategoryFilter(data.categories);
        } catch (err) {
            console.warn('Failed to load stats:', err.message);
        }
    }

    function animateValue(el, target) {
        const current = parseInt(el.textContent.replace(/[^0-9]/g, '')) || 0;
        if (current === target) {
            el.textContent = formatNumber(target);
            return;
        }

        const duration = 600;
        const start = performance.now();

        function step(now) {
            const progress = Math.min((now - start) / duration, 1);
            const eased = 1 - Math.pow(1 - progress, 3); // ease-out cubic
            const value = Math.round(current + (target - current) * eased);
            el.textContent = formatNumber(value);
            if (progress < 1) requestAnimationFrame(step);
        }

        requestAnimationFrame(step);
    }

    // ── Category Chart (horizontal bars) ───────────────────────
    const CATEGORY_COLORS = {
        grocery: 'cat-grocery', dining: 'cat-dining', transportation: 'cat-transportation',
        shopping: 'cat-shopping', utilities: 'cat-utilities', entertainment: 'cat-entertainment',
        healthcare: 'cat-healthcare', finance: 'cat-finance', travel: 'cat-travel',
        subscription: 'cat-subscription', education: 'cat-education', personal_care: 'cat-personal_care',
        other: 'cat-other',
    };

    function renderCategoryChart(categories) {
        if (!categories || categories.length === 0) {
            els.categoryChart.innerHTML = '<div class="empty-state"><p>No category data yet.</p></div>';
            return;
        }

        const maxCount = Math.max(...categories.map(c => c.count));

        els.categoryChart.innerHTML = categories.map(cat => {
            const pct = (cat.count / maxCount * 100).toFixed(1);
            const colorClass = CATEGORY_COLORS[cat.category] || 'cat-other';
            return `
                <div class="category-bar-item">
                    <span class="category-label">${cat.category}</span>
                    <div class="category-bar-track">
                        <div class="category-bar-fill ${colorClass}" style="width: ${pct}%">
                            ${formatCurrency(cat.total_amount)}
                        </div>
                    </div>
                    <span class="category-count">${cat.count}</span>
                </div>
            `;
        }).join('');
    }

    function updateCategoryFilter(categories) {
        const current = els.categoryFilter.value;
        const options = ['<option value="">All Categories</option>'];
        if (categories) {
            categories.forEach(cat => {
                const selected = cat.category === current ? ' selected' : '';
                options.push(`<option value="${cat.category}"${selected}>${cat.category} (${cat.count})</option>`);
            });
        }
        els.categoryFilter.innerHTML = options.join('');
    }

    // ── File Upload ────────────────────────────────────────────
    function initUpload() {
        const zone = els.uploadZone;
        const input = els.fileInput;

        zone.addEventListener('click', () => input.click());

        zone.addEventListener('dragover', (e) => {
            e.preventDefault();
            zone.classList.add('dragover');
        });

        zone.addEventListener('dragleave', () => {
            zone.classList.remove('dragover');
        });

        zone.addEventListener('drop', (e) => {
            e.preventDefault();
            zone.classList.remove('dragover');
            const file = e.dataTransfer.files[0];
            if (file) uploadFile(file);
        });

        input.addEventListener('change', () => {
            const file = input.files[0];
            if (file) uploadFile(file);
            input.value = '';
        });
    }

    async function uploadFile(file) {
        const ext = file.name.split('.').pop().toLowerCase();
        if (!['csv', 'json'].includes(ext)) {
            showToast('Unsupported file type. Please use CSV or JSON.', 'error');
            return;
        }

        // Show progress
        els.uploadProgress.style.display = 'flex';
        els.uploadResult.style.display = 'none';
        els.uploadProgressText.textContent = `Uploading ${file.name}...`;

        const formData = new FormData();
        formData.append('file', file);

        try {
            const data = await api('/upload', {
                method: 'POST',
                body: formData,
                headers: {},  // Let browser set content-type for FormData
            });

            els.uploadProgress.style.display = 'none';
            els.uploadResult.style.display = 'block';
            els.uploadResult.className = 'upload-result success';
            els.uploadResult.textContent = `✓ ${data.message} (Batch #${data.batch_id})`;

            showToast(`File uploaded! Batch #${data.batch_id} is processing.`, 'success');

            // Start polling for this batch
            loadBatches();
            startBatchPolling();

        } catch (err) {
            els.uploadProgress.style.display = 'none';
            els.uploadResult.style.display = 'block';
            els.uploadResult.className = 'upload-result error';
            els.uploadResult.textContent = `✕ Upload failed: ${err.message}`;

            showToast(`Upload failed: ${err.message}`, 'error');
        }
    }

    // ── Batches ────────────────────────────────────────────────
    async function loadBatches() {
        try {
            const data = await api('/batches?limit=10');
            renderBatches(data.batches);

            // Check if any batches are still processing
            const active = data.batches.some(b =>
                ['pending', 'parsing', 'processing', 'enriching'].includes(b.status)
            );

            if (active && !pollTimer) {
                startBatchPolling();
            } else if (!active && pollTimer) {
                stopBatchPolling();
                // Refresh stats and transactions when all batches complete
                loadStats();
                loadTransactions();
                loadAnomalies();
            }
        } catch (err) {
            console.warn('Failed to load batches:', err.message);
        }
    }

    function renderBatches(batches) {
        if (!batches || batches.length === 0) {
            els.batchList.innerHTML = '<div class="empty-state"><p>No batches yet. Upload a file to get started.</p></div>';
            return;
        }

        els.batchList.innerHTML = batches.map(batch => {
            const statusClass = batch.status === 'completed' ? 'completed'
                : batch.status === 'failed' ? 'failed' : '';

            const statusBadge = `<span class="badge badge--${getStatusBadgeType(batch.status)}">${batch.status}</span>`;

            return `
                <div class="batch-item">
                    <div class="batch-info">
                        <div class="batch-name">${batch.original_filename}</div>
                        <div class="batch-meta">${timeAgo(batch.created_at)} · ${batch.total_rows} rows ${statusBadge}</div>
                    </div>
                    <div class="batch-progress">
                        <div class="progress-bar">
                            <div class="progress-fill ${statusClass}" style="width: ${batch.progress_percent}%"></div>
                        </div>
                        <div class="progress-text">${batch.progress_percent}%</div>
                    </div>
                </div>
            `;
        }).join('');
    }

    function getStatusBadgeType(status) {
        const map = {
            pending: 'info', parsing: 'info', processing: 'primary',
            enriching: 'primary', completed: 'success', failed: 'danger',
            partially_completed: 'warning',
        };
        return map[status] || 'info';
    }

    function startBatchPolling() {
        if (pollTimer) return;
        pollTimer = setInterval(() => {
            loadBatches();
            loadStats();
        }, POLL_INTERVAL);
    }

    function stopBatchPolling() {
        if (pollTimer) {
            clearInterval(pollTimer);
            pollTimer = null;
        }
    }

    // ── Transactions ───────────────────────────────────────────
    async function loadTransactions() {
        const params = new URLSearchParams();
        params.set('page', currentPage);
        params.set('page_size', currentPageSize);

        if (activeFilters.search) params.set('search', activeFilters.search);
        if (activeFilters.category) params.set('category', activeFilters.category);
        if (activeFilters.status) params.set('status', activeFilters.status);

        try {
            const data = await api(`/transactions?${params}`);
            renderTransactions(data.transactions);
            renderPagination(data.page, data.total_pages, data.total);
        } catch (err) {
            console.warn('Failed to load transactions:', err.message);
        }
    }

    function renderTransactions(transactions) {
        if (!transactions || transactions.length === 0) {
            els.transactionsBody.innerHTML = `
                <tr class="empty-row"><td colspan="7">No transactions to display.</td></tr>
            `;
            return;
        }

        els.transactionsBody.innerHTML = transactions.map(txn => {
            const amountClass = txn.amount >= 0 ? 'amount-positive' : 'amount-negative';
            const amountStr = txn.amount >= 0 ? `+$${txn.amount.toFixed(2)}` : `-$${Math.abs(txn.amount).toFixed(2)}`;

            const category = txn.enrichment?.category || '—';
            const isAnomaly = txn.enrichment?.is_anomaly || false;

            return `
                <tr data-id="${txn.id}" onclick="window.__openTransaction(${txn.id})">
                    <td>${formatDate(txn.transaction_date)}</td>
                    <td style="max-width: 250px; overflow: hidden; text-overflow: ellipsis;">${txn.description}</td>
                    <td>${txn.merchant || '—'}</td>
                    <td class="${amountClass}">${amountStr}</td>
                    <td><span class="badge badge--${CATEGORY_COLORS[category] ? 'primary' : 'info'}" style="text-transform: capitalize;">${category}</span></td>
                    <td><span class="status-badge status-${txn.status}">${txn.status}</span></td>
                    <td><span class="anomaly-flag ${isAnomaly ? 'yes' : 'no'}">${isAnomaly ? '⚠' : '✓'}</span></td>
                </tr>
            `;
        }).join('');
    }

    function renderPagination(page, totalPages, total) {
        if (totalPages <= 1) {
            els.pagination.innerHTML = `<span class="page-info">${total} transaction${total !== 1 ? 's' : ''}</span>`;
            return;
        }

        let html = '';

        // Previous
        html += `<button class="page-btn" ${page <= 1 ? 'disabled' : ''} onclick="window.__goToPage(${page - 1})">‹</button>`;

        // Page numbers
        const range = getPageRange(page, totalPages);
        range.forEach(p => {
            if (p === '...') {
                html += `<span class="page-info">…</span>`;
            } else {
                html += `<button class="page-btn ${p === page ? 'active' : ''}" onclick="window.__goToPage(${p})">${p}</button>`;
            }
        });

        // Next
        html += `<button class="page-btn" ${page >= totalPages ? 'disabled' : ''} onclick="window.__goToPage(${page + 1})">›</button>`;

        html += `<span class="page-info">${total} total</span>`;

        els.pagination.innerHTML = html;
    }

    function getPageRange(current, total) {
        if (total <= 7) return Array.from({ length: total }, (_, i) => i + 1);

        const pages = [];
        pages.push(1);

        if (current > 3) pages.push('...');

        for (let i = Math.max(2, current - 1); i <= Math.min(total - 1, current + 1); i++) {
            pages.push(i);
        }

        if (current < total - 2) pages.push('...');

        pages.push(total);
        return pages;
    }

    // ── Anomalies ──────────────────────────────────────────────
    async function loadAnomalies() {
        try {
            const data = await api('/transactions?is_anomaly=true&page_size=10');
            renderAnomalies(data.transactions);
            els.anomalyBadge.textContent = data.total;
        } catch (err) {
            console.warn('Failed to load anomalies:', err.message);
        }
    }

    function renderAnomalies(transactions) {
        if (!transactions || transactions.length === 0) {
            els.anomalyList.innerHTML = '<div class="empty-state"><p>No anomalies detected.</p></div>';
            return;
        }

        els.anomalyList.innerHTML = transactions.map(txn => {
            const reason = txn.enrichment?.anomaly_reason || 'Flagged as anomalous';
            const score = txn.enrichment?.anomaly_score || 0;

            return `
                <div class="anomaly-item" onclick="window.__openTransaction(${txn.id})">
                    <div class="anomaly-indicator">⚠</div>
                    <div class="anomaly-info">
                        <div class="anomaly-desc">${txn.description}</div>
                        <div class="anomaly-reason">${reason} (score: ${(score * 100).toFixed(0)}%)</div>
                    </div>
                    <div class="anomaly-amount">$${Math.abs(txn.amount).toFixed(2)}</div>
                </div>
            `;
        }).join('');
    }

    // ── Transaction Detail Modal ───────────────────────────────
    async function openTransaction(id) {
        try {
            const txn = await api(`/transactions/${id}`);

            const amountStr = txn.amount >= 0 ? `+$${txn.amount.toFixed(2)}` : `-$${Math.abs(txn.amount).toFixed(2)}`;

            let html = `
                <div class="detail-row">
                    <span class="detail-label">ID</span>
                    <span class="detail-value">#${txn.id}</span>
                </div>
                <div class="detail-row">
                    <span class="detail-label">Date</span>
                    <span class="detail-value">${formatDateTime(txn.transaction_date)}</span>
                </div>
                <div class="detail-row">
                    <span class="detail-label">Description</span>
                    <span class="detail-value">${txn.description}</span>
                </div>
                <div class="detail-row">
                    <span class="detail-label">Merchant</span>
                    <span class="detail-value">${txn.merchant || '—'}</span>
                </div>
                <div class="detail-row">
                    <span class="detail-label">Amount</span>
                    <span class="detail-value ${txn.amount >= 0 ? 'amount-positive' : 'amount-negative'}">${amountStr}</span>
                </div>
                <div class="detail-row">
                    <span class="detail-label">Type</span>
                    <span class="detail-value" style="text-transform: capitalize;">${txn.transaction_type || '—'}</span>
                </div>
                <div class="detail-row">
                    <span class="detail-label">Status</span>
                    <span class="detail-value"><span class="status-badge status-${txn.status}">${txn.status}</span></span>
                </div>
            `;

            if (txn.enrichment) {
                const e = txn.enrichment;
                html += `
                    <div class="detail-section">
                        <h4>AI Enrichment</h4>
                        <div class="detail-row">
                            <span class="detail-label">Category</span>
                            <span class="detail-value" style="text-transform: capitalize;">${e.category || '—'} / ${e.subcategory || '—'}</span>
                        </div>
                        <div class="detail-row">
                            <span class="detail-label">Confidence</span>
                            <span class="detail-value">${e.confidence ? (e.confidence * 100).toFixed(0) + '%' : '—'}</span>
                        </div>
                        <div class="detail-row">
                            <span class="detail-label">Anomaly</span>
                            <span class="detail-value">${e.is_anomaly ? '⚠ Yes' : '✓ No'} (score: ${e.anomaly_score ? (e.anomaly_score * 100).toFixed(0) + '%' : '0%'})</span>
                        </div>
                        ${e.anomaly_reason ? `<div class="detail-row">
                            <span class="detail-label">Anomaly Reason</span>
                            <span class="detail-value">${e.anomaly_reason}</span>
                        </div>` : ''}
                        ${e.merchant_insight ? `<div class="detail-row">
                            <span class="detail-label">Merchant Insight</span>
                            <span class="detail-value">${e.merchant_insight}</span>
                        </div>` : ''}
                        <div class="detail-row">
                            <span class="detail-label">Model</span>
                            <span class="detail-value">${e.model_used || '—'}</span>
                        </div>
                        <div class="detail-row">
                            <span class="detail-label">Processing Time</span>
                            <span class="detail-value">${e.processing_time_ms ? e.processing_time_ms + 'ms' : '—'}</span>
                        </div>
                    </div>
                `;
            }

            els.modalBody.innerHTML = html;
            els.modalOverlay.classList.add('active');

        } catch (err) {
            showToast(`Failed to load transaction: ${err.message}`, 'error');
        }
    }

    function closeModal() {
        els.modalOverlay.classList.remove('active');
    }

    // ── Event Listeners ────────────────────────────────────────
    function initEvents() {
        // Refresh
        els.refreshBtn.addEventListener('click', () => {
            refreshAll();
            els.refreshBtn.style.animation = 'none';
            els.refreshBtn.offsetHeight; // trigger reflow
            els.refreshBtn.querySelector('svg').style.transition = 'transform 0.5s ease';
            els.refreshBtn.querySelector('svg').style.transform = 'rotate(360deg)';
            setTimeout(() => {
                els.refreshBtn.querySelector('svg').style.transform = '';
            }, 500);
        });

        els.refreshBatches.addEventListener('click', loadBatches);

        // Search with debounce
        let searchTimeout;
        els.searchInput.addEventListener('input', (e) => {
            clearTimeout(searchTimeout);
            searchTimeout = setTimeout(() => {
                activeFilters.search = e.target.value.trim();
                currentPage = 1;
                loadTransactions();
            }, 400);
        });

        // Filters
        els.categoryFilter.addEventListener('change', (e) => {
            activeFilters.category = e.target.value;
            currentPage = 1;
            loadTransactions();
        });

        els.statusFilter.addEventListener('change', (e) => {
            activeFilters.status = e.target.value;
            currentPage = 1;
            loadTransactions();
        });

        // Modal
        els.modalClose.addEventListener('click', closeModal);
        els.modalOverlay.addEventListener('click', (e) => {
            if (e.target === els.modalOverlay) closeModal();
        });
        document.addEventListener('keydown', (e) => {
            if (e.key === 'Escape') closeModal();
        });
    }

    // ── Global Functions (called from inline onclick) ──────────
    window.__openTransaction = openTransaction;
    window.__goToPage = (page) => {
        currentPage = page;
        loadTransactions();
    };

    // ── Refresh All ────────────────────────────────────────────
    function refreshAll() {
        checkHealth();
        loadStats();
        loadBatches();
        loadTransactions();
        loadAnomalies();
    }

    // ── Initialize ─────────────────────────────────────────────
    function init() {
        initUpload();
        initEvents();
        refreshAll();

        // Periodic refresh
        statsTimer = setInterval(() => {
            loadStats();
            loadAnomalies();
            loadTransactions();
        }, STATS_INTERVAL);

        // Health check every 30s
        setInterval(checkHealth, 30000);
    }

    // Boot
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }
})();
