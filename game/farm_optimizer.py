"""
Farm optimisation algorithm.
Decides whether attacking a village is profitable based on:
  - estimated ore production (from scout data)
  - expected resources at attack time
  - actual loot received vs expected
  - competition pressure detection (another farmer present)
"""
import logging
import time
from datetime import datetime, timedelta
from typing import Optional, Dict, Tuple

logger = logging.getLogger("FarmOptimizer")

# Unit speeds in minutes per field (World Speed 1.0)
UNIT_SPEEDS = {
    "spy": 9.0,
    "light": 10.0,
    "marcher": 10.0,
    "heavy": 11.0,
    "spear": 18.0,
    "axe": 18.0,
    "archer": 18.0,
    "sword": 22.0,
    "ram": 30.0,
    "catapult": 30.0,
    "snob": 35.0,
    "knight": 10.0,
}

# Minimum loot ratio to be considered "healthy" (loot / expected_resources)
HEALTHY_LOOT_RATIO    = 0.4
# If loot ratio falls below this, assume a competitor is farming too
COMPETITOR_THRESHOLD  = 0.15
# Multiplier for the next-attack delay when a competitor is detected
COMPETITOR_DELAY_MULT = 3.0
# After how many consecutive bad runs we flag the village as contested
CONSECUTIVE_BAD_RUNS  = 3

# Night Bonus settings (pl227)
NIGHT_BONUS_START = 23
NIGHT_BONUS_END = 8


class FarmOptimizer:
    """
    Stateless helper that analyses past attack records stored in the DB
    and recommends a next-attack delay.
    """

    def __init__(self, village_id: str, default_wait: int = 3600,
                 high_prio_wait: int = 1200, low_prio_wait: int = 7200):
        self.village_id      = village_id
        self.default_wait    = default_wait
        self.high_prio_wait  = high_prio_wait
        self.low_prio_wait   = low_prio_wait

    def evaluate(self, target_id: str, last_attack_ts: int, 
                 distance: float = 0, slowest_unit: str = "light") -> Tuple[int, str]:
        """
        Returns (recommended_wait_seconds, reason_string).
        """
        try:
            from core.database import DatabaseManager
        except ImportError:
            return self.default_wait, "no_db"

        # 1. NIGHT BONUS / MORNING RUSH LOGIC
        unit_speed = UNIT_SPEEDS.get(slowest_unit, 10.0)
        travel_time_sec = int(distance * unit_speed * 60)
        
        now = datetime.now()
        arrival_time = now + timedelta(seconds=travel_time_sec)
        
        # Check if arrival is in night bonus
        if arrival_time.hour >= NIGHT_BONUS_START or arrival_time.hour < NIGHT_BONUS_END:
            # It lands in night bonus. 
            # Strategy: Calculate when to send so it lands at 08:00:01
            target_arrival = now.replace(hour=NIGHT_BONUS_END, minute=0, second=1, microsecond=0)
            if now.hour >= NIGHT_BONUS_START:
                target_arrival += timedelta(days=1)
                
            required_wait = (target_arrival - timedelta(seconds=travel_time_sec) - now).total_seconds()
            
            if required_wait > 0:
                logger.debug("Morning Rush: Village %s would land in NB. Waiting %d s to land at 08:00:01", 
                             target_id, int(required_wait))
                return int(required_wait), "morning_rush_wait"

        # 2. RESOURCE ESTIMATION LOGIC
        predicted = DatabaseManager.get_predicted_resources(target_id)
        total_predicted = sum(predicted.values())
        
        # If village is empty (e.g. just farmed by us or someone else), wait
        if total_predicted < 100: # threshold for "worth it"
             # How long to wait until it has 500 resources?
             village_info = DatabaseManager.get_village(target_id)
             prod = sum(self._get_production(village_info).values())
             if prod > 0:
                 wait_needed = int((500 - total_predicted) / prod * 3600)
                 return max(self.high_prio_wait, min(wait_needed, self.low_prio_wait)), "waiting_for_resources"

        # 3. HISTORY ANALYSIS (COMPETITION)
        history = DatabaseManager.get_attack_history(target_id, limit=20)
        if not history:
            return self.high_prio_wait if total_predicted > 1000 else self.default_wait, "no_history"

        village_info = DatabaseManager.get_village(target_id)
        prod_dict = self._get_production(village_info)

        recommendation = self._analyse(history, prod_dict, last_attack_ts)
        return recommendation

    # ------------------------------------------------------------------
    # Internal analysis
    # ------------------------------------------------------------------

    def _get_production(self, village_info: Optional[Dict]) -> Dict[str, float]:
        if not village_info:
            return {"wood": 0, "stone": 0, "iron": 0}
        return {
            "wood":  village_info.get("wood_prod", 0),
            "stone": village_info.get("stone_prod", 0),
            "iron":  village_info.get("iron_prod", 0),
        }

    def _analyse(self, history: list, prod: dict,
                 last_attack_ts: int) -> Tuple[int, str]:
        total_prod_per_hour = sum(prod.values())
        if total_prod_per_hour == 0:
            total_prod_per_hour = 150 # fallback for unknown production

        recent = history[:CONSECUTIVE_BAD_RUNS]
        bad_runs = 0

        for record in recent:
            actual_loot  = record["loot_total"]
            elapsed_h    = self._elapsed_hours(record, last_attack_ts)
            expected     = total_prod_per_hour * elapsed_h

            if expected > 50:
                ratio = actual_loot / expected
                if ratio < COMPETITOR_THRESHOLD:
                    bad_runs += 1
                elif ratio < HEALTHY_LOOT_RATIO:
                    bad_runs += 0.5

        if bad_runs >= CONSECUTIVE_BAD_RUNS:
            delay = int(self.low_prio_wait * COMPETITOR_DELAY_MULT)
            self._flag_contested(history[0].get("target_id") or "unknown")
            return delay, "contested"

        avg_loot = sum(r["loot_total"] for r in recent) / len(recent) if recent else 0
        if avg_loot > 500:
            return self.high_prio_wait, "high_loot"
        elif avg_loot < 100:
            return self.low_prio_wait, "low_loot"
        return self.default_wait, "normal"

    @staticmethod
    def _elapsed_hours(record: dict, last_attack_ts: int) -> float:
        try:
            sent_str = record["sent_at"]
            if "T" in sent_str:
                sent = datetime.fromisoformat(sent_str).timestamp()
            else:
                sent = datetime.strptime(sent_str, "%Y-%m-%d %H:%M:%S").timestamp()
        except Exception:
            sent = time.time()
            
        prev_ts = last_attack_ts if last_attack_ts else sent - 3600
        diff = max(0, sent - prev_ts)
        return diff / 3600.0

    @staticmethod
    def _flag_contested(target_id: str):
        try:
            from game.attack_cache import AttackCache
            cache = AttackCache.get_cache(target_id) or {}
            cache["contested"]   = True
            cache["low_profile"] = True
            AttackCache.set_cache(target_id, cache)
        except Exception:
            pass


# ---------------------------------------------------------------------------
# Standalone helper to patch AttackManager with DB-aware evaluation
# ---------------------------------------------------------------------------

def patch_attack_manager_with_optimizer(attack_manager_instance):
    """
    Monkey-patches an AttackManager instance so that can_attack() uses
    FarmOptimizer for the next-attack wait time.
    """
    original_can_attack = attack_manager_instance.can_attack

    def enhanced_can_attack(vid, clear=False):
        result = original_can_attack(vid, clear=clear)
        if result is False:
            return False

        optimizer = FarmOptimizer(
            attack_manager_instance.village_id,
            default_wait=attack_manager_instance.farm_default_wait,
            high_prio_wait=attack_manager_instance.farm_high_prio_wait,
            low_prio_wait=attack_manager_instance.farm_low_prio_wait,
        )
        from game.attack import AttackCache
        cache_entry = AttackCache.get_cache(vid)
        last_ts = cache_entry.get("last_attack", 0) if cache_entry else 0

        recommended_wait, reason = optimizer.evaluate(vid, last_ts)

        # Override min_time with the optimizer's recommendation
        if cache_entry and cache_entry.get("last_attack"):
            if cache_entry["last_attack"] + recommended_wait > int(time.time()):
                logger.debug(
                    "FarmOptimizer: skip %s (reason=%s, wait=%ds)",
                    vid, reason, recommended_wait
                )
                return False

        return result

    attack_manager_instance.can_attack = enhanced_can_attack
    return attack_manager_instance
