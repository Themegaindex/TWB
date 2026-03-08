/**
 * TWB Cookie Sync – background service worker (Manifest V3)
 *
 * Flow:
 *  1. Listens for cookie changes on Tribal Wars domains.
 *  2. Collects ALL cookies for the changed domain into a single string.
 *  3. POSTs them to the local TWB Flask server (/api/cookie_webhook).
 *  4. Retries once after 5 s if the first attempt fails.
 *  5. Also schedules an alarm every 30 minutes to re-sync proactively.
 */

// -----------------------------------------------------------------------
// Configuration – user can override via popup
// -----------------------------------------------------------------------
const DEFAULT_BOT_URL = "http://localhost:5000"; // Fallback ONLY
const COOKIE_DOMAINS = [
    ".plemiona.pl",
    ".tribalwars.net",
    ".die-staemme.de",
    ".tribalwars.nl",
];
const SYNC_ALARM_NAME = "twb_cookie_sync";
const SYNC_INTERVAL = 30;   // minutes

// -----------------------------------------------------------------------
// Helpers
// -----------------------------------------------------------------------

/** Return bot URL from storage, falling back to default. */
async function getBotUrl() {
    return new Promise(resolve => {
        chrome.storage.local.get(["botUrl"], result => {
            resolve(result.botUrl || DEFAULT_BOT_URL);
        });
    });
}

/**
 * Gets the current active Tribal Wars tab and collects its specific cookies
 */
async function collectCookiesFromActiveTabs() {
    return new Promise(resolve => {
        chrome.tabs.query({ url: "*://*.plemiona.pl/game.php*" }, tabs => {
            if (!tabs || tabs.length === 0) {
                // Return default domain search if no active tab found
                chrome.cookies.getAll({ domain: "plemiona.pl" }, cookies => {
                    if (!cookies || cookies.length === 0) { resolve(null); return; }
                    const cookieStr = cookies.map(c => `${c.name}=${c.value}`).join("; ");
                    resolve({ cookieStr, endpoint: "https://plemiona.pl/game.php" });
                });
                return;
            }
            // Use the first active TW tab's exact URL to get ALL relevant cookies
            const tabUrl = new URL(tabs[0].url);
            chrome.cookies.getAll({ url: tabUrl.href }, cookies => {
                if (!cookies || cookies.length === 0) { resolve(null); return; }
                const cookieStr = cookies.map(c => `${c.name}=${c.value}`).join("; ");
                resolve({ cookieStr, endpoint: tabUrl.origin + "/game.php" });
            });
        });
    });
}

/** POST cookie data to the local bot server. */
async function sendToBot(cookieStr, endpoint, botUrl, retry = true) {
    try {
        const resp = await fetch(`${botUrl}/api/cookie_webhook`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                cookies: cookieStr,
                endpoint: endpoint,
                userAgent: navigator.userAgent
            }),
        });

        if (resp.ok) {
            const json = await resp.json();
            console.log("[TWB] Cookie sync OK:", json.message, `(${json.cookies_count} cookies)`);
            chrome.storage.local.set({
                lastSync: new Date().toISOString(),
                lastStatus: "ok",
            });
            return true;
        }
        console.warn("[TWB] Bot server returned error:", resp.status);
    } catch (err) {
        console.warn("[TWB] Could not reach bot server:", err.message);
        if (retry) {
            console.log("[TWB] Retrying in 5 s …");
            setTimeout(() => sendToBot(cookieStr, endpoint, botUrl, false), 5000);
        } else {
            chrome.storage.local.set({ lastSync: new Date().toISOString(), lastStatus: "error" });
        }
    }
    return false;
}

/** Trigger a full sync using active tabs. */
async function syncAllDomains() {
    const botUrl = await getBotUrl();
    const result = await collectCookiesFromActiveTabs();
    if (result) {
        await sendToBot(result.cookieStr, result.endpoint, botUrl);
    }
}

// -----------------------------------------------------------------------
// Event: capture raw Cookie headers directly via WebRequest
// This perfectly catches all hidden, Host-Only or exotic cookies
// -----------------------------------------------------------------------
chrome.webRequest.onSendHeaders.addListener(
    async (details) => {
        const urlObj = new URL(details.url);
        const domain = urlObj.hostname;

        // Debounce: only fire once per 3 s per domain
        const storeKey = `debounce_webreq_${domain}`;
        const stored = await new Promise(r => chrome.storage.local.get([storeKey], r));
        const last = stored[storeKey] || 0;
        const now = Date.now();

        if (now - last < 3000) return;
        chrome.storage.local.set({ [storeKey]: now });

        let cookieStr = null;
        if (details.requestHeaders) {
            for (let header of details.requestHeaders) {
                if (header.name.toLowerCase() === 'cookie') {
                    cookieStr = header.value;
                    break;
                }
            }
        }

        if (cookieStr) {
            const botUrl = await getBotUrl();
            const endpoint = urlObj.origin + "/game.php";
            console.log(`[TWB] Intercepted full raw Cookie header for ${domain}`);
            console.log(`[TWB] Payload: `, cookieStr);
            await sendToBot(cookieStr, endpoint, botUrl);
        }
    },
    { urls: ["*://*.plemiona.pl/game.php*", "*://*.tribalwars.net/game.php*", "*://*.die-staemme.de/game.php*", "*://*.tribalwars.nl/game.php*"] },
    ["requestHeaders", "extraHeaders"]
);

// -----------------------------------------------------------------------
// Event: cookie change on any monitored domain (Fallback for manual sync)
// -----------------------------------------------------------------------
chrome.cookies.onChanged.addListener(async changeInfo => {
    if (changeInfo.removed) return;  // ignore deletions

    const cookie = changeInfo.cookie;
    const matched = COOKIE_DOMAINS.some(d => cookie.domain.includes(d.replace(/^\./, "")));
    if (!matched) return;

    // Debounce: only fire once per 3 s per domain to avoid hammering the bot
    const storeKey = `debounce_${cookie.domain}`;
    const stored = await new Promise(r => chrome.storage.local.get([storeKey], r));
    const last = stored[storeKey] || 0;
    const now = Date.now();

    if (now - last < 3000) return;
    chrome.storage.local.set({ [storeKey]: now });

    // Use the active tab sync
    syncAllDomains();
});

// -----------------------------------------------------------------------
// Alarm: proactive re-sync every 30 minutes
// -----------------------------------------------------------------------
chrome.alarms.create(SYNC_ALARM_NAME, {
    delayInMinutes: 1,
    periodInMinutes: SYNC_INTERVAL,
});

chrome.alarms.onAlarm.addListener(alarm => {
    if (alarm.name === SYNC_ALARM_NAME) {
        syncAllDomains();
    }
});

// -----------------------------------------------------------------------
// Message from popup: manual sync trigger or settings save
// -----------------------------------------------------------------------
chrome.runtime.onMessage.addListener((msg, _sender, sendResponse) => {
    if (msg.action === "sync_now") {
        syncAllDomains().then(() => sendResponse({ ok: true }));
        return true;  // keep channel open for async response
    }
    if (msg.action === "set_bot_url") {
        chrome.storage.local.set({ botUrl: msg.url }, () => {
            sendResponse({ ok: true });
        });
        return true;
    }
    if (msg.action === "fetch_bot") {
        const { url, method, body } = msg.payload;
        console.log(`[TWB-Background] Fetching: ${url} (${method})`);
        
        fetch(url, {
            method: method || "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(body),
            mode: 'cors'
        })
        .then(r => {
            if (!r.ok) throw new Error(`HTTP Error: ${r.status}`);
            return r.json();
        })
        .then(d => {
            console.log(`[TWB-Background] Success response from ${url}`);
            sendResponse({ ok: true, data: d });
        })
        .catch(e => {
            console.error(`[TWB-Background] Fetch error for ${url}:`, e.message);
            sendResponse({ ok: false, error: e.message });
        });
        return true;
    }
});
