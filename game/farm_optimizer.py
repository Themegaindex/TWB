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
from datetime import datetime
from typing import Optional, Dict, Tuple

logger = logging.getLogger("FarmOptimizer")

# Minimum loot ratio to be considered "healthy" (loot / expected_resources)
HEALTHY_LOOT_RATIO    = 0.4
# If loot ratio falls below this, assume a competitor is farming too
COMPETITOR_THRESHOLD  = 0.15
# Multiplier for the next-attack delay when a competitor is detected
COMPETITOR_DELAY_MULT = 3.0
# After how many consecutive bad runs we flag the village as contested
CONSECUTIVE_BAD_RUNS  = 3


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

    # ------------------------------------------------------------------
    # Core public method
    # ------------------------------------------------------------------

    def evaluate(self, target_id: str, last_attack_ts: int) -> Tuple[int, str]:
        """
        Returns (recommended_wait_seconds, reason_string).
        Uses DatabaseManager to pull attack history.
        """
        try:
            from core.database import DatabaseManager
        except ImportError:
            return self.default_wait, "no_db"

        history = DatabaseManager.get_attack_history(target_id, limit=20)
        if not history:
            return self.default_wait, "no_history"

        village_info = DatabaseManager.get_village(target_id)
        prod = self._get_production(village_info)

        recommendation = self._analyse(history, prod, last_attack_ts)
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

        recent = history[:CONSECUTIVE_BAD_RUNS]
        bad_runs = 0

        for record in recent:
            actual_loot  = record["loot_total"]
            elapsed_h    = self._elapsed_hours(record, last_attack_ts)
            expected     = total_prod_per_hour * elapsed_h

            if expected > 50:                      # only evaluate if we expect something
                ratio = actual_loot / expected
                if ratio < COMPETITOR_THRESHOLD:
                    bad_runs += 1
                elif ratio < HEALTHY_LOOT_RATIO:
                    bad_runs += 0.5               # borderline – count half

        if bad_runs >= CONSECUTIVE_BAD_RUNS:
            delay = int(self.low_prio_wait * COMPETITOR_DELAY_MULT)
            logger.info(
                "Village %s flagged as CONTESTED (%.1f bad runs). "
                "Next attack delayed to %d s",
                self.village_id, bad_runs, delay
            )
            self._flag_contested(history[0]["target_id"])
            return delay, "contested"

        # Standard profitability assessment using average loot
        avg_loot = sum(r["loot_total"] for r in recent) / len(recent) if recent else 0
        if avg_loot > 500:
            return self.high_prio_wait, "high_loot"
        elif avg_loot < 100:
            return self.low_prio_wait, "low_loot"
        return self.default_wait, "normal"

    @staticmethod
    def _elapsed_hours(record: dict, last_attack_ts: int) -> float:
        """Approximate travel + regeneration time in hours."""
        try:
            sent = datetime.fromisoformat(record["sent_at"]).timestamp()
        except Exception:
            sent = last_attack_ts
        prev_ts = last_attack_ts if last_attack_ts else sent - 3600
        diff = max(0, sent - prev_ts)
        return diff / 3600.0

    @staticmethod
    def _flag_contested(target_id: str):
        """Persist the contested flag in the attack cache."""
        try:
            from game.attack import AttackCache
            cache = AttackCache.get_cache(target_id) or {}
            cache["contested"]   = True
            cache["low_profile"] = True
            AttackCache.set_cache(target_id, cache)
        except Exception as e:
            logger.debug("Could not flag contested: %s", e)


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
