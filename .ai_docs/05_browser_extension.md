# `browser_extension/` Documentation
Chrome/Edge extension enabling seamless cookie sync and passive scraping.
- `manifest.json`: Configuration for Chrome extensions. Requires host permissions for the game domains to read cookies and tabs.
- `background.js`: Service worker. Periodically checks active tabs or cookie changes on `plemiona.pl`, `tribalwars.net`, etc., grabbing the `sid` and `pl_auth` cookies and doing a `POST /api/cookie_webhook` to the local Flask server.
- `content.js`: Injected into Tribal Wars pages. Specifically looks at Report screens (`screen=report`) and extracts HTML of the combat, sending it to `/api/plugin_report`.
- `popup.html` & `popup.js`: Extension interface to configure the local Webmanager IP/Port (default localhost:5000) and displays connection status.
