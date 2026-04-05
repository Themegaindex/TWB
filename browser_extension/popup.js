const botUrlEl = document.getElementById('bot-url');
const statusEl = document.getElementById('status');
const debugToggle = document.getElementById('debug-toggle');
const mapRadiusEl = document.getElementById('map-radius');

// Load saved values
chrome.storage.local.get(['botUrl', 'lastSync', 'lastStatus', 'debugEnabled', 'mapRadius'], data => {
    botUrlEl.value = data.botUrl || 'http://localhost:5000';
    debugToggle.checked = data.debugEnabled !== false; // Default true
    mapRadiusEl.value = data.mapRadius || 20;
    
    // Auto-save debug status if not set
    if (data.debugEnabled === undefined) {
        chrome.storage.local.set({ debugEnabled: true, mapRadius: 20 });
    }
    
    if (data.lastSync) {
        const ts = new Date(data.lastSync).toLocaleTimeString();
        const st = data.lastStatus || 'unknown';
        const cls = st === 'ok' ? 'ok' : 'err';
        statusEl.innerHTML = `Last sync: <span class="${cls}">${ts} (${st})</span>`;
    } else {
        statusEl.innerHTML = `Not synced yet.`;
    }
});

document.getElementById('save-btn').addEventListener('click', () => {
    const url = botUrlEl.value.trim().replace(/\/$/, '');
    chrome.runtime.sendMessage({ action: 'set_bot_url', url }, resp => {
        statusEl.innerHTML = resp && resp.ok
            ? '<span class="ok">URL saved ✓</span>'
            : '<span class="err">Error saving URL</span>';
    });
});

debugToggle.addEventListener('change', () => {
    chrome.storage.local.set({ debugEnabled: debugToggle.checked });
});

mapRadiusEl.addEventListener('change', () => {
    chrome.storage.local.set({ mapRadius: parseInt(mapRadiusEl.value) || 20 });
});

document.getElementById('sync-btn').addEventListener('click', () => {
    statusEl.innerHTML = '⏳ Syncing…';
    chrome.runtime.sendMessage({ action: 'sync_now' }, resp => {
        statusEl.innerHTML = resp && resp.ok
            ? '<span class="ok">Sync triggered ✓</span>'
            : '<span class="err">Could not trigger sync</span>';
    });
});

document.getElementById('test-btn').addEventListener('click', async () => {
    const url = botUrlEl.value.trim().replace(/\/$/, '');
    if (!url) {
        statusEl.innerHTML = '<span class="err">Please enter URL first</span>';
        return;
    }
    statusEl.innerHTML = `🔍 Testing ${url}...`;
    try {
        const resp = await fetch(`${url}/api/cookie_webhook`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ test: true })
        });
        if (resp.ok) {
            statusEl.innerHTML = '<span class="ok">Connection OK! ✓</span>';
        } else {
            statusEl.innerHTML = `<span class="err">Server error: ${resp.status}</span>`;
        }
    } catch (err) {
        statusEl.innerHTML = `<span class="err">Failed: ${err.message}</span>`;
    }
});

document.getElementById('open-panel-btn').addEventListener('click', () => {
    const url = botUrlEl.value.trim().replace(/\/$/, '');
    if (url) {
        window.open(url, '_blank');
    } else {
        statusEl.innerHTML = '<span class="err">Enter URL first!</span>';
    }
});
