# Root Directory Files
- `twb.py`: Main bot loop. Initializes `WebWrapper` (request session), reads `config.json`, determines villages from the overview page, updates world options (flags, knights, etc.), and launches `Village.run()` for each village. Also starts the `webmanager` as a subprocess.
- `manager.py`: Contains `VillageManager`, which handles cross-village actions like `farm_manager` (for automated farming) and `resource_balancer` (balancing resources between owned villages).
- `force_read_reports.py`: Script to forcibly scan historical reports from the game and save them to the database.
- `config.json` / `config.example.json`: File containing user configurations.
- `installer.bat` / `start.bat` / `activate_env.bat`: Windows execution scripts.
- `reset_bot.sh` / `requirements.txt`: Unix helpers and Python dependencies.
