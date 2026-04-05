# `core/` Module Documentation
Handles non-game-specific underlying functionality.
- `database.py`: SQLAlchemy setup & abstraction. Tables for `DBVillage`, `DBAttack`, `DBUnitsLost`, `DBReport`, and `DBResourceSnapshot`. Used to persist farming data and calculate ROI.
- `request.py`: `WebWrapper` class handling all HTTP requests to Tribal Wars. Manages cookies (from extension sync or manual), CSRF tokens (`h` token), rate limiting (randomized sleeps to avoid bans), and API requests.
- `extractors.py`: Massive toolset of Regex and string-parsing methods to read game HTML pages and extract wood/stone/iron, unit counts, building levels, targets, etc., converting HTML into Python dicts.
- `filemanager.py`: Legacy JSON-based cache storage logic (slowly being replaced by `database.py`).
- `notification.py`: Webhook notification systems (Telegram, Discord, etc.).
- `updater.py`: Checks for GitHub updates.
- `twstats.py`: Interacts with twstats.com for maps and village lists.
- `exceptions.py`: Custom exceptions like `UnsupportedPythonVersion`.
