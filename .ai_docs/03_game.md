# `game/` Module Documentation
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
