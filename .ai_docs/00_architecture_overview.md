# TWB - Tribal Wars Bot: AI Architecture Overview
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
