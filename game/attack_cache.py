"""
AttackCache — warstwa persystencji flag ataku.

Strategia migracji:
  - Odczyt: najpierw DB, fallback do pliku JSON (dla istniejących danych).
  - Zapis:  zapisuje DO OBU (DB + plik JSON) przez okres przejściowy.
  - cache_grab: agreguje z DB (główne), uzupełnia brakującymi plikami.
"""
import logging
import time
from datetime import datetime
from core.filemanager import FileManager

logger = logging.getLogger(__name__)

try:
    from core.database import DatabaseManager
    _DB_AVAILABLE = True
except Exception:
    _DB_AVAILABLE = False

# Klucze które trzymamy w DBVillage (nie w JSON payload)
_DB_FLAG_KEYS = {"is_safe", "safe", "high_profile", "low_profile",
                 "last_attack", "last_attack_at",
                 "attack_count", "total_loot", "total_losses", "total_sent"}


def _file_to_db_flags(file_entry: dict) -> dict:
    """Konwertuje starą strukturę pliku JSON do słownika flag DB."""
    flags: dict = {}
    if "safe" in file_entry:
        flags["is_safe"] = bool(file_entry["safe"])
    if "high_profile" in file_entry:
        flags["high_profile"] = bool(file_entry["high_profile"])
    if "low_profile" in file_entry:
        flags["low_profile"] = bool(file_entry["low_profile"])
    if "last_attack" in file_entry and file_entry["last_attack"]:
        try:
            flags["last_attack_at"] = datetime.fromtimestamp(float(file_entry["last_attack"]))
        except (ValueError, OSError):
            pass
    for k in ("attack_count", "total_losses", "total_sent"):
        if k in file_entry:
            flags[k] = file_entry[k]
    if "total_loot" in file_entry:
        flags["total_loot"] = file_entry["total_loot"]
    return flags


def _db_to_file_entry(db_flags: dict) -> dict:
    """Konwertuje flagi z DB do formatu zgodnego ze starym kodem (backward compat)."""
    entry: dict = {
        "scout":        db_flags.get("scout", False),
        "safe":         db_flags.get("is_safe", True),
        "high_profile": db_flags.get("high_profile", False),
        "low_profile":  db_flags.get("low_profile", False),
        "last_attack":  0,
        "attack_count": db_flags.get("attack_count", 0),
        "total_loot":   db_flags.get("total_loot") or {},
        "total_losses": db_flags.get("total_losses", 0),
        "total_sent":   db_flags.get("total_sent", 0),
    }
    lat = db_flags.get("last_attack_at")
    if lat:
        if isinstance(lat, datetime):
            entry["last_attack"] = int(lat.timestamp())
        elif isinstance(lat, (int, float)):
            entry["last_attack"] = int(lat)
    return entry


class AttackCache:
    """
    Cache flag ataku dla wiosek barbarzyńskich.

    Hierarchia źródeł danych:
      1. PostgreSQL / SQLite (DBVillage.attack_flags)  ← primary
      2. cache/attacks/{village_id}.json               ← fallback / legacy
    """

    @staticmethod
    def get_cache(village_id) -> dict | None:
        """Zwraca entry cache dla wioski. Priorytet: DB → plik JSON."""
        vid = str(village_id)

        # 1. Próba odczytu z DB
        if _DB_AVAILABLE:
            try:
                db_flags = DatabaseManager.get_attack_flags(vid)
                if db_flags and db_flags.get("last_attack_at") is not None:
                    return _db_to_file_entry(db_flags)
            except Exception as e:
                logger.debug("AttackCache DB read failed for %s: %s", vid, e)

        # 2. Fallback: plik JSON
        file_entry = FileManager.load_json_file(f"cache/attacks/{vid}.json")
        if file_entry and _DB_AVAILABLE:
            # Oportunistyczna migracja: zapisz do DB jeśli jeszcze tam nie ma
            try:
                flags = _file_to_db_flags(file_entry)
                if flags:
                    DatabaseManager.upsert_attack_flags(vid, **flags)
            except Exception as e:
                logger.debug("AttackCache opportunistic migration failed for %s: %s", vid, e)
        return file_entry

    @staticmethod
    def set_cache(village_id, entry: dict) -> None:
        """Zapisuje entry do DB (primary) i do pliku JSON (backward compat)."""
        vid = str(village_id)

        # 1. Zapis do DB
        if _DB_AVAILABLE:
            try:
                flags = _file_to_db_flags(entry)
                if flags:
                    DatabaseManager.upsert_attack_flags(vid, **flags)
            except Exception as e:
                logger.warning("AttackCache DB write failed for %s: %s", vid, e)

        # 2. Zapis do pliku (backward compat dla dashboardu i innych modułów)
        FileManager.save_json_file(entry, f"cache/attacks/{vid}.json")

    @staticmethod
    def cache_grab() -> dict:
        """Zwraca wszystkie wpisy cache.

        Priorytet: dane z DB (pełne), uzupełnione plikami JSON które nie są w DB.
        """
        output: dict = {}

        # 1. Pobierz z DB
        if _DB_AVAILABLE:
            try:
                db_all = DatabaseManager.get_all_attack_flags()
                for vid, flags in db_all.items():
                    output[vid] = _db_to_file_entry(flags)
            except Exception as e:
                logger.debug("AttackCache.cache_grab DB read failed: %s", e)

        # 2. Uzupełnij plikami JSON (wioski których jeszcze nie ma w DB)
        for filename in FileManager.list_directory("cache/attacks", ends_with=".json"):
            vid = filename.replace(".json", "")
            if vid not in output:
                entry = FileManager.load_json_file(f"cache/attacks/{filename}")
                if entry:
                    output[vid] = entry

        return output
