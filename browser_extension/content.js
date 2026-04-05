// --- TWB Extension Content Script ---
console.info("[TWB-Ext] Content Script loaded for", window.location.hostname);

const DEFAULT_BOT_URL = "http://localhost:5000";

// Pobieranie konfiguracji (URL bota i tryb debugowania)
async function getStorageData() {
    return new Promise(resolve => {
        chrome.storage.local.get(["botUrl", "debugEnabled", "mapRadius"], result => {
            resolve({
                botUrl: result.botUrl || DEFAULT_BOT_URL,
                debugEnabled: result.debugEnabled !== false, // Domyślnie true
                mapRadius: result.mapRadius || 20
            });
        });
    });
}

// Funkcja pomocnicza do logowania (tylko gdy Debug: ON)
function debugLog(...args) {
    getStorageData().then(cfg => {
        if (cfg.debugEnabled) {
            console.log("[TWB-Debug]", ...args);
        }
    });
}

// Wizualne powiadomienie na stronie gry
function showNotification(text, type = 'info') {
    const div = document.createElement('div');
    div.className = 'twb-notification';
    div.style.cssText = `
        position: fixed; top: 20px; right: 20px; background: #16213e; color: #fff;
        padding: 12px 25px; border-left: 5px solid ${type === 'error' ? '#ef9a9a' : '#64b5f6'};
        border-radius: 4px; box-shadow: 0 4px 15px rgba(0,0,0,0.6); z-index: 10000;
        font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
        transition: all 0.4s ease; pointer-events: none; opacity: 0;
        transform: translateX(50px); font-size: 14px;
    `;
    div.innerHTML = `<span style="margin-right:10px;">🛡️</span> <b>TWB:</b> ${text}`;
    document.body.appendChild(div);

    setTimeout(() => {
        div.style.opacity = '1';
        div.style.transform = 'translateX(0)';
    }, 50);

    setTimeout(() => {
        div.style.opacity = '0';
        div.style.transform = 'translateX(50px)';
        setTimeout(() => div.remove(), 400);
    }, 4500);
}

/** 
 * Proxy fetch through background.js to avoid "Mixed Content" issues 
 * (HTTPS game site trying to talk to HTTP bot local IP)
 */
async function sendToBotProxy(endpoint, data) {
    const cfg = await getStorageData();
    const fullUrl = `${cfg.botUrl}${endpoint}`;
    
    return new Promise((resolve, reject) => {
        chrome.runtime.sendMessage({
            action: "fetch_bot",
            payload: { url: fullUrl, body: data, method: "POST" }
        }, response => {
            if (chrome.runtime.lastError) {
                reject(chrome.runtime.lastError);
            } else if (response && response.ok) {
                resolve(response.data);
            } else {
                reject(new Error(response ? response.error : "Unknown error"));
            }
        });
    });
}

// 1. Obsługa Raportów
const reportMatch = window.location.href.match(/(?:view|report_id)=(\d+)/);
if (window.location.href.includes("screen=report") && reportMatch) {
    let currentReportId = reportMatch[1];
    let reportRawHTML = document.documentElement.outerHTML;

    console.info(`[TWB-Ext] Wykryto raport ${currentReportId}. Przesyłanie do bota...`);
    
    sendToBotProxy("/api/plugin_report", {
        "report_id": currentReportId,
        "html": reportRawHTML
    })
    .then(d => {
        debugLog(`Odpowiedź bota (raport):`, d.message);
        if (d.ok) {
            showNotification(`Zaczytano i przetworzono raport ${currentReportId}`);
        } else {
            showNotification(d.message || "Błąd przetwarzania raportu", "error");
        }
    })
    .catch(e => {
        console.error("[TWB-Ext] Błąd połączenia z botem (raport):", e);
        showNotification("Brak połączenia z botem!", "error");
    });
}

// 2. Obsługa Mapy
if (window.location.href.includes("screen=map") || document.getElementById('map_mover')) {
    console.info("[TWB-Ext] Ekran mapy wykryty. Uruchamianie watchera danych...");

    // Request data from map_scraper.js (which runs in MAIN world)
    const requestMapData = async () => {
        const cfg = await getStorageData();
        window.postMessage({ type: "TWB_MAP_DATA_REQUEST", radius: cfg.mapRadius }, "*");
    };

    // Cykliczne sprawdzanie mapy (gdy gracz przesuwa widok)
    setInterval(requestMapData, 6000);
    setTimeout(requestMapData, 1500); // Pierwszy strzał szybciej
}

// Nasłuch na dane z wstrzykniętego skryptu mapy
let lastMapUpdateTS = 0;
let lastVillageCount = 0;

window.addEventListener("message", (event) => {
    if (event.source !== window || !event.data || event.data.type !== "TWB_MAP_DATA_REPLY") return;

    const villages = event.data.villages;
    
    // Debounce: nie wysyłaj identycznych danych zbyt często
    if (Date.now() - lastMapUpdateTS < 5000 && villages.length === lastVillageCount) return;

    lastMapUpdateTS = Date.now();
    lastVillageCount = villages.length;

    console.info(`[TWB-Ext] Przesyłanie ${villages.length} wiosek z mapy do bota...`);

    sendToBotProxy("/api/plugin/map", { villages: villages })
    .then(d => {
        debugLog(`Odpowiedź bota (mapa):`, d.message);
        if (d.ok) {
            showNotification(`Zaktualizowano dane mapy (${villages.length} wiosek)`);
        }
    })
    .catch(e => console.error("[TWB-Ext] Błąd połączenia z botem (mapa):", e));
});
