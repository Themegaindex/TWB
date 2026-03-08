import os
import datetime

DOCS_DIR = ".ai_docs"

os.makedirs(DOCS_DIR, exist_ok=True)

docs = {
    "00_architecture_overview.md": """# TWB - Tribal Wars Bot: AI Architecture Overview
## Purpose
TWB is an automated bot for the browser game Tribal Wars. It is designed to act on behalf of the user, managing villages, farming resources, upgrading buildings, recruiting troops, and sending attacks. 

## High-Level Architecture
1. **Bot Core (`twb.py`)**: The main entry point. Initializes the request wrapper, loads the configuration from `config.json`, starts the local `webmanager`, and loops through the configured villages.
2. **Core Logic (`core/`)**: Handles HTTP requests, session management, database (SQLite + SQLAlchemy), regex/extractor utilities, and file management.
3. **Game Mechanics (`game/`)**: Individual modules representing game entities like `Village`, `BuildingManager`, `TroopManager`, `FarmOptimizer`, `ReportsManager`, etc.
4. **Local Web Interface (`webmanager/`)**: A Flask-based local web server (`localhost:5000`) enabling users to configure the bot, view map data, history, and status without editing JSON directly.
5. **Browser Extension (`browser_extension/`)**: A Chrome extension that syncs cookies from the user's active browser session to the webmanager (and consequently the bot) to prevent logging out the main account. It also parses attack reports from the user's browser in real time.

## Data Persistence
- `config.json` stores user directives, village settings, what to build, how much to recruit, farming radii, etc.
- `cache/session.json` stores the active cookie and endpoint.
- `cache/twb.db` stores villages, attacks, unit losses, and reports using SQLAlchemy.
""",

    "01_twb_root.md": """# Root Directory Files
- `twb.py`: Main bot loop. Initializes `WebWrapper` (request session), reads `config.json`, determines villages from the overview page, updates world options (flags, knights, etc.), and launches `Village.run()` for each village. Also starts the `webmanager` as a subprocess.
- `manager.py`: Contains `VillageManager`, which handles cross-village actions like `farm_manager` (for automated farming) and `resource_balancer` (balancing resources between owned villages).
- `force_read_reports.py`: Script to forcibly scan historical reports from the game and save them to the database.
- `config.json` / `config.example.json`: File containing user configurations.
- `installer.bat` / `start.bat` / `activate_env.bat`: Windows execution scripts.
- `reset_bot.sh` / `requirements.txt`: Unix helpers and Python dependencies.
""",

    "02_core.md": """# `core/` Module Documentation
Handles non-game-specific underlying functionality.
- `database.py`: SQLAlchemy setup & abstraction. Tables for `DBVillage`, `DBAttack`, `DBUnitsLost`, `DBReport`, and `DBResourceSnapshot`. Used to persist farming data and calculate ROI.
- `request.py`: `WebWrapper` class handling all HTTP requests to Tribal Wars. Manages cookies (from extension sync or manual), CSRF tokens (`h` token), rate limiting (randomized sleeps to avoid bans), and API requests.
- `extractors.py`: Massive toolset of Regex and string-parsing methods to read game HTML pages and extract wood/stone/iron, unit counts, building levels, targets, etc., converting HTML into Python dicts.
- `filemanager.py`: Legacy JSON-based cache storage logic (slowly being replaced by `database.py`).
- `notification.py`: Webhook notification systems (Telegram, Discord, etc.).
- `updater.py`: Checks for GitHub updates.
- `twstats.py`: Interacts with twstats.com for maps and village lists.
- `exceptions.py`: Custom exceptions like `UnsupportedPythonVersion`.
""",

    "03_game.md": """# `game/` Module Documentation
Handles Tribal Wars specific objects and automation logic.
- `village.py`: Wrapper for a single village. Reads resources, troops, and triggers other managers (builder, recruitment, attacks) within its `run()` loop.
- `buildingmanager.py`: Automates building queue. Reads `Village` requirements and queues construction if resources are sufficient.
- `troopmanager.py`: Automates unit recruitment based on user-defined target numbers.
- `reports.py`: `ReportManager`. Automatically checks incoming reports. Reads battle outcomes, parses loot, updates internal cache/DB, and calculates losses.
- `attack.py`: Functions to send units automatically. Computes unit speeds, arrival times, payload sizes, and sends the POST payload.
- `farm_optimizer.py`: Handles farming algorithms, finding inactive villages or barbs based on the `map.py` cache. Generates efficient attack payloads.
- `resources.py`: Helper class for Wood/Stone/Iron state and storage capacity.
- `map.py`: Reads the local map sectors to discover neighbors, barbs, and active players.
- `simulator.py`: (Potentially) the simulator wrapper for calculating battle odds.
- `defence_manager.py`: Detects incoming attacks and handles dodging or calling for support based on config.
- `hunter.py` / `snobber.py` / `warehouse_balancer.py`: Specialized components for sniping, noble management, and resource balancing.
""",

    "04_webmanager.md": """# `webmanager/` Module Documentation
Local user interface for configuring and monitoring TWB.
- `server.py`: Flask app running by default on port 5000. Provides API endpoints for the web UI AND the browser extension.
    - `/api/cookie_webhook`: Receives session cookies from extension.
    - `/api/plugin_report`: Receives forwarded attack reports from extension.
    - `/api/village_attacks`, `/api/force_reports`: Data retrieval for charts and forcing updates.
- `utils.py`: Utility functions for the Flask server to read bot state, compute resources, map building templates, etc.
- `helpfile.py`: Definitions and textual help files provided in the UI.
- `templates/` and `static/`: HTML front-end pages utilizing Bootstrap/JS for configuration editing. It reads from and writes to `config.json`.
""",

    "05_browser_extension.md": """# `browser_extension/` Documentation
Chrome/Edge extension enabling seamless cookie sync and passive scraping.
- `manifest.json`: Configuration for Chrome extensions. Requires host permissions for the game domains to read cookies and tabs.
- `background.js`: Service worker. Periodically checks active tabs or cookie changes on `plemiona.pl`, `tribalwars.net`, etc., grabbing the `sid` and `pl_auth` cookies and doing a `POST /api/cookie_webhook` to the local Flask server.
- `content.js`: Injected into Tribal Wars pages. Specifically looks at Report screens (`screen=report`) and extracts HTML of the combat, sending it to `/api/plugin_report`.
- `popup.html` & `popup.js`: Extension interface to configure the local Webmanager IP/Port (default localhost:5000) and displays connection status.
""",
    
    "06_pages.md": """# `pages/` Module Documentation
- `overview.py`: Interacts with the `screen=overview` page in the game interface. Extracts the list of villages the user owns so that the bot knows which local objects to instantiate.
"""
}

for filename, content in docs.items():
    filepath = os.path.join(DOCS_DIR, filename)
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(content)

print("AI documentation files written successfully.")
