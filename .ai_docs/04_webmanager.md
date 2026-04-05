# `webmanager/` Module Documentation
Local user interface for configuring and monitoring TWB.
- `server.py`: Flask app running by default on port 5000. Provides API endpoints for the web UI AND the browser extension.
    - `/api/cookie_webhook`: Receives session cookies from extension.
    - `/api/plugin_report`: Receives forwarded attack reports from extension.
    - `/api/village_attacks`, `/api/force_reports`: Data retrieval for charts and forcing updates.
- `utils.py`: Utility functions for the Flask server to read bot state, compute resources, map building templates, etc.
- `helpfile.py`: Definitions and textual help files provided in the UI.
- `templates/` and `static/`: HTML front-end pages utilizing Bootstrap/JS for configuration editing. It reads from and writes to `config.json`.
