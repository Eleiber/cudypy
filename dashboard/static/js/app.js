// Dashboard JavaScript

const API_BASE = '';

// State
let allDevices = [];
let currentFilter = 'all';
let currentView = 'devices';
let pollingPaused = false;
let dataPending = false;
let pollTimer;
let targetGeneration = 0;
const trafficHistory = new CudyHistory.History(180);

// DOM Elements
const elements = {
    devicesGrid: document.getElementById('devicesGrid'),
    filterSelect: document.getElementById('filterSelect'),
    refreshBtn: document.getElementById('refreshBtn'),
    settingsBtn: document.getElementById('settingsBtn'),
    settingsModal: document.getElementById('settingsModal'),
    closeSettings: document.getElementById('closeSettings'),
    cancelSettings: document.getElementById('cancelSettings'),
    saveSettings: document.getElementById('saveSettings'),
    routerUrl: document.getElementById('routerUrl'),
    routerPassword: document.getElementById('routerPassword'),
    connectionStatus: document.getElementById('connectionStatus'),
    totalDevices: document.getElementById('totalDevices'),
    onlineDevices: document.getElementById('onlineDevices'),
    wifiDevices: document.getElementById('wifiDevices'),
    ethernetDevices: document.getElementById('ethernetDevices'),
    networkInfo: document.getElementById('networkInfo'),
    systemInfo: document.getElementById('systemInfo'),
    toastContainer: document.getElementById('toastContainer'),
    pageTitle: document.getElementById('pageTitle'),
};

// Initialize
document.addEventListener('DOMContentLoaded', () => {
    initNavigation();
    initEventListeners();
    loadData();
    document.getElementById('historyClient').addEventListener('change', renderHistory);
    window.addEventListener('resize', renderHistory);
    document.getElementById('clientSearch').addEventListener('input', renderDevices);
    document.getElementById('clientSort').addEventListener('change', renderDevices);
    document.getElementById('pausePolling').addEventListener('click', e => {
        pollingPaused = !pollingPaused;
        e.target.textContent = pollingPaused ? 'Resume' : 'Pause';
        e.target.setAttribute('aria-pressed', String(pollingPaused));
        clearTimeout(pollTimer);
        if (!pollingPaused) loadData();
    });
    document.getElementById('clearHistory').addEventListener('click', () => {
        trafficHistory.clear(); renderHistory();
    });
    document.addEventListener('visibilitychange', () => {
        clearTimeout(pollTimer);
        if (!document.hidden && !pollingPaused) loadData();
    });
});

// Navigation
function initNavigation() {
    document.querySelectorAll('.nav-item').forEach(item => {
        item.addEventListener('click', (e) => {
            e.preventDefault();
            const view = item.dataset.view;
            switchView(view);
        });
    });
}

function switchView(view) {
    // Update nav
    document.querySelectorAll('.nav-item').forEach(item => {
        item.classList.toggle('active', item.dataset.view === view);
    });

    // Update views
    document.querySelectorAll('.view').forEach(v => {
        v.classList.toggle('active', v.id === `${view}View`);
    });

    // Update title
    const titles = {
        devices: 'Devices',
        network: 'Network',
        system: 'System'
    };
    elements.pageTitle.textContent = titles[view] || 'Dashboard';

    currentView = view;

    // Load view data
    if (view === 'network') {
        loadNetworkInfo();
    } else if (view === 'system') {
        loadSystemInfo();
    }
}

// Event Listeners
function initEventListeners() {
    elements.filterSelect.addEventListener('change', (e) => {
        currentFilter = e.target.value;
        renderDevices();
    });

    elements.refreshBtn.addEventListener('click', () => {
        refreshData();
    });

    elements.settingsBtn.addEventListener('click', () => {
        openSettings();
    });

    elements.closeSettings.addEventListener('click', closeSettings);
    elements.cancelSettings.addEventListener('click', closeSettings);
    elements.saveSettings.addEventListener('click', saveSettings);

    // Close modal on outside click
    elements.settingsModal.addEventListener('click', (e) => {
        if (e.target === elements.settingsModal) {
            closeSettings();
        }
    });
}

// Data Loading
async function loadData() {
    if (dataPending) return;
    clearTimeout(pollTimer);
    dataPending = true;
    const generation = targetGeneration;
    try {
        setLoading(true);
        updateConnectionStatus('connecting');

        const response = await fetch(`${API_BASE}/api/devices`);

        if (!response.ok) {
            throw new Error(`HTTP ${response.status}`);
        }

        const data = await response.json();

        if (data.error) {
            throw new Error(data.error);
        }

        if (generation !== targetGeneration) return;
        allDevices = data.devices || [];
        trafficHistory.add(allDevices);
        updateHistoryClients();
        renderHistory();
        document.getElementById('sampleStatus').textContent = `Last sample: ${new Date().toLocaleTimeString()} · ${trafficHistory.samples.length}/180 samples · 10-second refresh`;
        updateStats();
        renderDevices();
        updateConnectionStatus('connected');

    } catch (error) {
        if (generation !== targetGeneration) return;
        trafficHistory.add(null); renderHistory();
        document.getElementById('sampleStatus').textContent = 'Refresh failed. Previous samples are retained; latest data is unavailable.';
        console.error('Error loading data:', error);
        updateConnectionStatus('error');
        showToast(error.message || 'Failed to connect to router', 'error');
        elements.devicesGrid.innerHTML = `
            <div class="empty-state">
                <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                    <circle cx="12" cy="12" r="10"/>
                    <line x1="12" y1="8" x2="12" y2="12"/>
                    <line x1="12" y1="16" x2="12.01" y2="16"/>
                </svg>
                <p>Failed to load devices. Check your router connection.</p>
            </div>
        `;
    } finally {
        dataPending = false;
        setLoading(false);
        if (!pollingPaused && !document.hidden) pollTimer = setTimeout(loadData, 10000);
    }
}

async function refreshData() {
    try {
        elements.refreshBtn.classList.add('loading');

        await loadData();

    } catch (error) {
        console.error('Error refreshing:', error);
        showToast('Failed to refresh', 'error');
    } finally {
        elements.refreshBtn.classList.remove('loading');
    }
}

async function loadNetworkInfo() {
    try {
        elements.networkInfo.innerHTML = '<div class="loading">Loading network info...</div>';

        const response = await fetch(`${API_BASE}/api/network`);
        const data = await response.json();

        if (data.error) {
            throw new Error(data.error);
        }

        const network = data.network || {};
        renderNetworkInfo(network);

    } catch (error) {
        console.error('Error loading network:', error);
        elements.networkInfo.innerHTML = `<div class="error">Error: ${escapeHtml(error.message)}</div>`;
    }
}

async function loadSystemInfo() {
    try {
        elements.systemInfo.innerHTML = '<div class="loading">Loading system info...</div>';

        const response = await fetch(`${API_BASE}/api/system`);
        const data = await response.json();

        if (data.error) {
            throw new Error(data.error);
        }

        const system = data.system || {};
        renderSystemInfo(system);

    } catch (error) {
        console.error('Error loading system:', error);
        elements.systemInfo.innerHTML = `<div class="error">Error: ${escapeHtml(error.message)}</div>`;
    }
}

// Rendering
function updateStats() {
    const online = allDevices.filter(d => d.is_online).length;
    const wifi = allDevices.filter(d => d.connection_type === 'wifi').length;
    const ethernet = allDevices.filter(d => d.connection_type === 'ethernet').length;

    elements.totalDevices.textContent = allDevices.length;
    elements.onlineDevices.textContent = online;
    elements.wifiDevices.textContent = wifi;
    elements.ethernetDevices.textContent = ethernet;
}

function renderDevices() {
    let devices = [...allDevices];
    const search = document.getElementById('clientSearch').value.toLowerCase();
    devices = devices.filter(d => [d.device_name, d.hostname, d.mac_address, d.ip_address]
        .some(value => String(value || '').toLowerCase().includes(search)));
    const sort = document.getElementById('clientSort').value;
    const field = {up: 'bandwidth_up', down: 'bandwidth_down', signal: 'signal_strength'}[sort];
    devices.sort((a, b) => field
        ? (b[field] ?? -Infinity) - (a[field] ?? -Infinity)
        : String(a.device_name || a.hostname || a.mac_address).localeCompare(String(b.device_name || b.hostname || b.mac_address)));

    // Apply filter
    switch (currentFilter) {
        case 'online':
            devices = devices.filter(d => d.is_online);
            break;
        case 'wifi':
            devices = devices.filter(d => d.connection_type === 'wifi');
            break;
        case 'ethernet':
            devices = devices.filter(d => d.connection_type === 'ethernet');
            break;
    }

    if (devices.length === 0) {
        elements.devicesGrid.innerHTML = `
            <div class="empty-state">
                <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                    <rect x="2" y="3" width="20" height="14" rx="2" ry="2"/>
                    <line x1="8" y1="21" x2="16" y2="21"/>
                    <line x1="12" y1="17" x2="12" y2="21"/>
                </svg>
                <p>No devices found</p>
            </div>
        `;
        return;
    }

    elements.devicesGrid.innerHTML = devices.map(device => renderDeviceCard(device)).join('');
}

function renderDeviceCard(device) {
    const name = device.device_name || device.hostname || device.mac_address;
    const statusClass = device.is_online === null || device.is_online === undefined
        ? 'unknown' : device.is_online ? 'online' : 'offline';
    const statusText = device.is_online === null || device.is_online === undefined
        ? 'Activity unknown' : device.is_online ? 'Recently active' : 'Not recently active';
    const connType = device.connection_type || 'unknown';

    return `
        <div class="device-card ${statusClass}">
            <div class="device-header">
                <div class="device-name">${escapeHtml(name)}</div>
                <div class="device-status ${statusClass}">
                    ${device.is_online ? '<svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M22 11.08V12a10 10 0 11-5.93-9.14"/><polyline points="22 4 12 14.01 9 11.01"/></svg>' : ''}
                    ${statusText}
                </div>
            </div>
            <div class="device-ip">${escapeHtml(device.ip_address)}</div>
            <div class="device-mac">${escapeHtml(device.mac_address)}</div>
            <div class="connection-type ${connType}">
                ${connType === 'wifi' ? '<svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M5 12.55a11 11 0 0114.08 0"/><path d="M1.42 9a16 16 0 0121.16 0"/></svg>' : '<svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/></svg>'}
                ${connType}
            </div>
            ${device.signal_strength != null || device.bandwidth_up != null || device.bandwidth_down != null ? `
                <div class="device-stats">
                    ${device.signal_strength !== null ? `
                        <div class="device-stat">
                            <span class="device-stat-label">Signal</span>
                            <span class="device-stat-value signal">${device.signal_strength} dBm</span>
                        </div>
                    ` : ''}
                    ${device.formatted_bandwidth_down ? `
                        <div class="device-stat">
                            <span class="device-stat-label">Download</span>
                            <span class="device-stat-value">${device.formatted_bandwidth_down}</span>
                        </div>
                    ` : ''}
                    ${device.formatted_bandwidth_up ? `
                        <div class="device-stat">
                            <span class="device-stat-label">Upload</span>
                            <span class="device-stat-value">${device.formatted_bandwidth_up}</span>
                        </div>
                    ` : ''}
                    ${device.formatted_bytes_received ? `
                        <div class="device-stat">
                            <span class="device-stat-label" title="Native inbytes counter; direction unverified">Reported inbytes</span>
                            <span class="device-stat-value">${device.formatted_bytes_received}</span>
                        </div>
                    ` : ''}
                </div>
            ` : ''}
        </div>
    `;
}

function renderNetworkInfo(network) {
    // Network info structure depends on router response
    const interfaces = [];

    // Try to parse common structures
    for (const [key, value] of Object.entries(network)) {
        if (typeof value === 'object' && value !== null) {
            interfaces.push(`
                <div class="info-card">
                    <div class="info-card-title">${escapeHtml(key)}</div>
                    <div class="info-card-value">
                        ${Object.entries(value).map(([k, v]) => `${escapeHtml(k)}: ${escapeHtml(String(v))}`).join('<br>')}
                    </div>
                </div>
            `);
        } else {
            interfaces.push(`
                <div class="info-card">
                    <div class="info-card-title">${escapeHtml(key)}</div>
                    <div class="info-card-value">${escapeHtml(String(value))}</div>
                </div>
            `);
        }
    }

    elements.networkInfo.innerHTML = interfaces.length > 0
        ? interfaces.join('')
        : '<div class="empty-state"><p>No network information available</p></div>';
}

function renderSystemInfo(system) {
    const infoCards = [];

    for (const [key, value] of Object.entries(system)) {
        infoCards.push(`
            <div class="info-card">
                <div class="info-card-title">${escapeHtml(formatKey(key))}</div>
                <div class="info-card-value">${escapeHtml(String(value))}</div>
            </div>
        `);
    }

    elements.systemInfo.innerHTML = infoCards.length > 0
        ? infoCards.join('')
        : '<div class="empty-state"><p>No system information available</p></div>';
}

// Settings
function openSettings() {
    fetch(`${API_BASE}/api/config`)
        .then(res => res.json())
        .then(data => {
            elements.routerUrl.value = data.url || '';
            elements.routerPassword.value = '';
        });
    elements.settingsModal.classList.add('active');
}

function closeSettings() {
    elements.settingsModal.classList.remove('active');
}

async function saveSettings() {
    const url = elements.routerUrl.value.trim();
    const password = elements.routerPassword.value;

    if (!url || !password) {
        showToast('Please enter both URL and password', 'warning');
        return;
    }

    try {
        const response = await fetch(`${API_BASE}/api/config`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ url, password })
        });

        if (response.ok) {
            targetGeneration++;
            trafficHistory.clear(); allDevices = []; updateStats(); renderHistory(); renderDevices();
            document.getElementById('historyClient').replaceChildren(new Option('All clients', ''));
            closeSettings();
            showToast('Settings saved', 'success');
            refreshData();
        } else {
            throw new Error('Failed to save settings');
        }
    } catch (error) {
        showToast('Failed to save settings', 'error');
    }
}

// UI Helpers
function setLoading(loading) {
    elements.refreshBtn.disabled = loading;
}

function updateConnectionStatus(status) {
    elements.connectionStatus.className = `connection-status ${status}`;
    const statusText = {
        connecting: 'Connecting...',
        connected: 'Connected',
        error: 'Connection Error'
    };
    elements.connectionStatus.querySelector('.status-text').textContent = statusText[status] || status;
}

function showToast(message, type = 'info') {
    const toast = document.createElement('div');
    toast.className = `toast ${type}`;
    toast.innerHTML = `
        <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            ${type === 'success' ? '<path d="M22 11.08V12a10 10 0 11-5.93-9.14"/><polyline points="22 4 12 14.01 9 11.01"/>' : ''}
            ${type === 'error' ? '<circle cx="12" cy="12" r="10"/><line x1="15" y1="9" x2="9" y2="15"/><line x1="9" y1="9" x2="15" y2="15"/>' : ''}
            ${type === 'warning' ? '<path d="M10.29 3.86L1.82 18a2 2 0 001.71 3h16.94a2 2 0 001.71-3L13.71 3.86a2 2 0 00-3.42 0z"/><line x1="12" y1="9" x2="12" y2="13"/><line x1="12" y1="17" x2="12.01" y2="17"/>' : ''}
            ${type === 'info' ? '<circle cx="12" cy="12" r="10"/><line x1="12" y1="16" x2="12" y2="12"/><line x1="12" y1="8" x2="12.01" y2="8"/>' : ''}
        </svg>
        <span>${escapeHtml(message)}</span>
    `;
    elements.toastContainer.appendChild(toast);

    setTimeout(() => {
        toast.style.opacity = '0';
        setTimeout(() => toast.remove(), 300);
    }, 3000);
}

// Utilities
function updateHistoryClients() {
    const select = document.getElementById('historyClient');
    const selected = select.value;
    const oldLabel = select.selectedOptions[0]?.textContent;
    select.replaceChildren(new Option('All clients', ''));
    for (const device of allDevices) {
        select.add(new Option(device.device_name || device.hostname || device.mac_address, device.mac_address));
    }
    if (selected && !allDevices.some(d => d.mac_address === selected)) {
        select.add(new Option(oldLabel || selected, selected));
    }
    select.value = selected;
}

function renderHistory() {
    const svg = document.getElementById('trafficGraph');
    svg.replaceChildren();
    const width = Math.max(300, svg.clientWidth);
    const right = width - 20;
    svg.setAttribute('viewBox', `0 0 ${width} 210`);
    const samples = trafficHistory.series(document.getElementById('historyClient').value);
    function node(tag, attributes, text) {
        const element = document.createElementNS('http://www.w3.org/2000/svg', tag);
        for (const [key, value] of Object.entries(attributes)) element.setAttribute(key, String(value));
        if (text !== undefined) element.textContent = text;
        svg.appendChild(element); return element;
    }
    if (!samples.length) {
        node('text', {x: width / 2, y: 100, 'text-anchor': 'middle', fill: 'currentColor', 'font-size': 12}, 'Waiting for samples');
        document.getElementById('historySummary').textContent = 'No samples';
        return;
    }
    const rates = samples.flatMap(s => [s.up, s.down]).filter(v => v !== null);
    const peak = Math.max(0, ...rates), max = Math.max(1, peak);
    const start = samples[0].time, end = Math.max(start + 10000, samples.at(-1).time);
    const x = t => 80 + (t - start) / (end - start) * (right - 80);
    const y = v => 175 - v / max * 140;
    for (let i = 0; i <= 4; i++) {
        const value = max * i / 4;
        node('line', {x1: 80, x2: right, y1: y(value), y2: y(value), stroke: 'currentColor', opacity: 0.12});
        node('text', {x: 72, y: y(value) + 4, 'text-anchor': 'end', fill: 'currentColor', 'font-size': 11}, formatRate(value));
    }
    for (const [field, color] of [['down', '#38bdf8'], ['up', '#a78bfa']]) {
        for (const path of CudyHistory.segments(samples, field, x, y)) {
            node('path', {d: path, fill: 'none', stroke: color, 'stroke-width': 2.5});
        }
        for (const s of samples) {
            if (s[field] === null) continue;
            const dot = node('circle', {cx: x(s.time), cy: y(s[field]), r: 2.5, fill: color});
            const title = document.createElementNS('http://www.w3.org/2000/svg', 'title');
            title.textContent = `${new Date(s.time).toLocaleTimeString()} · ${field}: ${formatRate(s[field])}`;
            dot.appendChild(title);
        }
    }
    node('text', {x: 80, y: 202, fill: 'currentColor', 'font-size': 12}, new Date(start).toLocaleTimeString());
    node('text', {x: right, y: 202, 'text-anchor': 'end', fill: 'currentColor', 'font-size': 12}, new Date(end).toLocaleTimeString());
    const latest = samples.at(-1);
    document.getElementById('historySummary').textContent = `Latest ↓ ${formatRate(latest.down)} / ↑ ${formatRate(latest.up)} · Peak ${rates.length ? formatRate(peak) : 'unknown'}`;
}

function formatRate(value) {
    if (value === null || value === undefined) return 'unknown';
    let rate = value;
    for (const unit of ['B/s', 'KiB/s', 'MiB/s', 'GiB/s']) {
        if (rate < 1024 || unit === 'GiB/s') return `${rate.toFixed(1)} ${unit}`;
        rate /= 1024;
    }
}

function escapeHtml(text) {
    if (!text) return '';
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

function formatKey(key) {
    return key
        .replace(/_/g, ' ')
        .replace(/\b\w/g, l => l.toUpperCase());
}
