(function() {
    // This script runs in the MAIN world to access game variables like TWMap.
    
    function scrapeMap(radius) {
        if (typeof TWMap === 'undefined' || !TWMap.villages) return;
        
        const limit = radius || 30;
        const centerX = TWMap.pos ? TWMap.pos[0] : 500;
        const centerY = TWMap.pos ? TWMap.pos[1] : 500;

        const villages = [];
        const vCache = TWMap.villages;
        for (let id in vCache) {
            if (Object.prototype.hasOwnProperty.call(vCache, id)) {
                const v = vCache[id];
                if (!v.id) continue;

                // Oblicz dystans od środka mapy
                const dist = Math.sqrt(Math.pow(v.x - centerX, 2) + Math.pow(v.y - centerY, 2));
                
                if (dist <= limit) {
                    villages.push({
                        id: v.id,
                        name: v.name || "",
                        x: v.x,
                        y: v.y,
                        points: v.points || 0,
                        owner: v.owner || "0"
                    });
                }
            }
        }
        
        if (villages.length > 0) {
            window.postMessage({ 
                type: "TWB_MAP_DATA_REPLY", 
                villages: villages, 
                count: villages.length 
            }, "*");
        }
    }

    // Listen for requests from the content script
    window.addEventListener("message", (event) => {
        if (event.source !== window || !event.data || event.data.type !== "TWB_MAP_DATA_REQUEST") return;
        scrapeMap(event.data.radius);
    });

    // Initial check
    setTimeout(scrapeMap, 2000);
})();
