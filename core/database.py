"""
Relational database layer for TWB using SQLite + SQLAlchemy.
"""
import logging
from datetime import datetime
from typing import Optional, List, Dict
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from core.filemanager import FileManager

try:
    from core.models import (
        Base, DBVillage, DBPlayer, DBAlly, DBSession, DBVillageSettings,
        DBAttack, DBUnitsLost, DBReport, DBResourceSnapshot,
        DBConquer, DBKillScore
    )
    HAS_SQLALCHEMY = True
except ImportError:
    HAS_SQLALCHEMY = False

logger = logging.getLogger("Database")
_engine = None
_SessionLocal = None

def get_engine():
    global _engine
    if _engine is None:
        db_url = "postgresql://twb_user:twb_password@127.0.0.1:5432/twb_db"
        pool_size = 10
        try:
            config = FileManager.load_json_file("config.json")
            if config:
                db_config = config.get("database", {})
                db_url = db_config.get("url", db_url).replace("localhost", "127.0.0.1")
                pool_size = db_config.get("pool_size", pool_size)
        except Exception: pass
        try:
            _engine = create_engine(db_url, pool_size=pool_size, max_overflow=20)
            if HAS_SQLALCHEMY:
                with _engine.connect() as conn: pass
                Base.metadata.create_all(_engine)
                logger.info("Database ready at %s", db_url)
        except Exception as e:
            logger.warning("Falling back to SQLite: %s", e)
            _engine = create_engine("sqlite:///twb.sqlite")
            if HAS_SQLALCHEMY: Base.metadata.create_all(_engine)
    return _engine

def get_session():
    if not HAS_SQLALCHEMY: return None
    global _SessionLocal
    if _SessionLocal is None: _SessionLocal = sessionmaker(bind=get_engine())
    return _SessionLocal()

class DatabaseManager:
    @staticmethod
    def _session(): return get_session()

    @staticmethod
    def upsert_village(vid, **kwargs):
        if not HAS_SQLALCHEMY: return
        s = DatabaseManager._session()
        try:
            row = s.get(DBVillage, vid) or DBVillage(id=vid)
            if row not in s: s.add(row)
            for k, v in kwargs.items(): setattr(row, k, v)
            row.last_seen = datetime.utcnow()
            s.commit()
        except Exception as e:
            logger.error("upsert_village error: %s", e)
            s.rollback()
        finally: s.close()

    @staticmethod
    def get_village(vid):
        if not HAS_SQLALCHEMY: return None
        s = DatabaseManager._session()
        try:
            row = s.get(DBVillage, vid)
            return {"id": row.id, "name": row.name, "location": [row.x, row.y], "points": row.points, "owner_id": row.owner_id, "is_owned": row.is_owned} if row else None
        finally: s.close()

    @staticmethod
    def get_all_villages(limit=25000):
        if not HAS_SQLALCHEMY: return {}
        s = DatabaseManager._session()
        try:
            results = (s.query(DBVillage, DBPlayer.name, DBAlly.name).outerjoin(DBPlayer, DBVillage.owner_id == DBPlayer.id).outerjoin(DBAlly, DBPlayer.ally_id == DBAlly.id).limit(limit).all())
            return {v.id: {"id": v.id, "name": v.name, "location": [v.x, v.y], "points": v.points, "player": p or "Barbarzyńca", "ally": a or ""} for v, p, a in results}
        finally: s.close()

    @staticmethod
    def save_attack(origin_id, target_id, troops_sent, loot=None, **kwargs):
        if not HAS_SQLALCHEMY: return None
        s = DatabaseManager._session()
        try:
            for vid in [origin_id, target_id]:
                if vid and not s.get(DBVillage, vid): s.add(DBVillage(id=vid))
            loot = loot or {}
            a = DBAttack(origin_id=origin_id, target_id=target_id, troops_sent=troops_sent, loot_wood=int(loot.get("wood", 0)), loot_stone=int(loot.get("stone", 0)), loot_iron=int(loot.get("iron", 0)), **kwargs)
            s.add(a)
            s.commit()
            return a.id
        except Exception as e:
            logger.error("save_attack error: %s", e); s.rollback(); return None
        finally: s.close()

    @staticmethod
    def get_attack_history(target_id, limit=50):
        if not HAS_SQLALCHEMY: return []
        s = DatabaseManager._session()
        try:
            rows = s.query(DBAttack).filter(DBAttack.target_id == target_id).order_by(DBAttack.sent_at.desc()).limit(limit).all()
            return [{"id": r.id, "sent_at": r.sent_at.isoformat(), "loot_total": r.loot_wood + r.loot_stone + r.loot_iron, "troops_sent": r.troops_sent, "won": r.won, "losses": [{"unit": l.unit_type, "amount": l.amount, "side": l.side} for l in r.losses]} for r in rows]
        finally: s.close()

    @staticmethod
    def save_report(report_id, **kwargs):
        if not HAS_SQLALCHEMY: return
        s = DatabaseManager._session()
        try:
            if s.get(DBReport, str(report_id)): return
            for vid in [kwargs.get("origin_id"), kwargs.get("dest_id")]:
                if vid and not s.get(DBVillage, vid): s.add(DBVillage(id=vid))
            loot = kwargs.get("loot", {})
            scout_res = kwargs.get("scout_resources")
            r = DBReport(report_id=str(report_id), village_id=kwargs.get("dest_id"), report_type=kwargs.get("report_type"), origin_id=kwargs.get("origin_id"), dest_id=kwargs.get("dest_id"), raw_extra=kwargs.get("extra"), loot_wood=int(loot.get("wood", 0)), loot_stone=int(loot.get("stone", 0)), loot_iron=int(loot.get("iron", 0)), losses_json=kwargs.get("losses", {}), scout_wood=int(scout_res.get("wood", 0)) if scout_res else None, scout_stone=int(scout_res.get("stone", 0)) if scout_res else None, scout_iron=int(scout_res.get("iron", 0)) if scout_res else None, scout_buildings=kwargs.get("scout_buildings"), created_at=kwargs.get("created_at") or datetime.utcnow())
            s.add(r)
            s.commit()
        except Exception as e:
            logger.error("save_report error: %s", e); s.rollback()
        finally: s.close()

    @staticmethod
    def get_predicted_resources(vid):
        if not HAS_SQLALCHEMY: return {"wood": 0, "stone": 0, "iron": 0}
        s = DatabaseManager._session()
        try:
            report = s.query(DBReport).filter(DBReport.dest_id == str(vid)).order_by(DBReport.created_at.desc()).first()
            if not report: return {"wood": 0, "stone": 0, "iron": 0}
            res = {"wood": report.scout_wood or 0, "stone": report.scout_stone or 0, "iron": report.scout_iron or 0}
            village = s.get(DBVillage, vid)
            if village and village.wood_prod > 0:
                h = (datetime.utcnow() - report.created_at).total_seconds() / 3600.0
                res["wood"] += int(village.wood_prod * h); res["stone"] += int(village.stone_prod * h); res["iron"] += int(village.iron_prod * h)
            attacks = s.query(DBAttack).filter(DBAttack.target_id == str(vid), DBAttack.sent_at > report.created_at).all()
            for a in attacks:
                res["wood"] = max(0, res["wood"] - a.loot_wood); res["stone"] = max(0, res["stone"] - a.loot_stone); res["iron"] = max(0, res["iron"] - a.loot_iron)
            limit = 400000
            if report.scout_buildings:
                lvl = report.scout_buildings.get("storage", 1)
                limit = 400000 if lvl >= 30 else int(1000 * (1.23 ** (max(0, lvl - 1))))
            return {k: min(v, limit) for k, v in res.items()}
        finally: s.close()

    @staticmethod
    def reserve_farm_loot(vid: str, req_w: int, req_s: int, req_i: int, min_threshold: int = 100):
        """
        Calls PostgreSQL atomic reservation function.
        Returns (success, reserved_w, reserved_s, reserved_i)
        """
        if not HAS_SQLALCHEMY: return False, 0, 0, 0
        s = DatabaseManager._session()
        try:
            from sqlalchemy import text
            query = text("SELECT success, reserved_w, reserved_s, reserved_i FROM reserve_farm_loot(:v_id, :w, :s, :i, :t)")
            res = s.execute(query, {"v_id": str(vid), "w": req_w, "s": req_s, "i": req_i, "t": min_threshold}).fetchone()
            s.commit()
            if res:
                return bool(res[0]), int(res[1]), int(res[2]), int(res[3])
            return False, 0, 0, 0
        except Exception as e:
            logger.error("reserve_farm_loot error: %s", e)
            return False, 0, 0, 0
        finally: s.close()

    @staticmethod
    def get_lva_jitter(vid: str) -> float:
        """
        Analyzes last 5 loot runs for Z-Score competition detection.
        Returns random jitter percentage if competition detected.
        """
        if not HAS_SQLALCHEMY: return 0.0
        s = DatabaseManager._session()
        try:
            from sqlalchemy import text
            import random
            import math
            query = text("SELECT (loot_wood + loot_stone + loot_iron) as total FROM attacks WHERE target_id = :vid AND (loot_wood + loot_stone + loot_iron) > 0 ORDER BY sent_at DESC LIMIT 5")
            rows = s.execute(query, {"vid": str(vid)}).fetchall()
            if len(rows) < 5: return 0.0
            
            loots = [float(r[0]) for r in rows]
            current_loot = loots[0]
            historical = loots[1:]
            
            mean = sum(historical) / len(historical)
            variance = sum((x - mean) ** 2 for x in historical) / len(historical)
            std = math.sqrt(variance)
            
            if std == 0: return 0.0
            z_score = (current_loot - mean) / std
            
            if z_score < -1.5:
                return random.uniform(0.05, 0.15)
            return 0.0
        except Exception as e:
            logger.error("get_lva_jitter error: %s", e)
            return 0.0
        finally: s.close()

    @staticmethod
    def get_report(report_id):
        if not HAS_SQLALCHEMY: return None
        s = DatabaseManager._session()
        try:
            r = s.get(DBReport, str(report_id))
            if not r: return None
            return {
                "type": r.report_type,
                "origin": r.origin_id,
                "dest": r.village_id,
                "losses": r.losses_json,
                "extra": r.raw_extra
            }
        finally: s.close()

    @staticmethod
    def save_units_lost(attack_id, losses, side="attacker"):
        if not HAS_SQLALCHEMY: return
        s = DatabaseManager._session()
        try:
            for unit, amount in losses.items():
                ul = DBUnitsLost(attack_id=attack_id, unit_type=unit, amount=amount, side=side)
                s.add(ul)
            s.commit()
        except Exception as e:
            logger.error("save_units_lost error: %s", e)
            s.rollback()
        finally: s.close()

    @staticmethod
    def update_village_production(vid, buildings):
        if not HAS_SQLALCHEMY: return
        prod = DatabaseManager.estimate_production(buildings)
        DatabaseManager.upsert_village(vid, 
            wood_prod=prod["wood"], 
            stone_prod=prod["stone"], 
            iron_prod=prod["iron"]
        )

    @staticmethod
    def estimate_production(buildings):
        # Base production for speed 1.0
        tbl = {0: 5, 1: 30, 2: 35, 3: 41, 4: 47, 5: 55, 6: 64, 7: 74, 8: 86, 9: 100, 10: 117, 11: 136, 12: 158, 13: 184, 14: 214, 15: 249, 16: 289, 17: 337, 18: 392, 19: 456, 20: 530, 21: 616, 22: 717, 23: 834, 24: 970, 25: 1128, 26: 1311, 27: 1525, 28: 1773, 29: 2062, 30: 2400}
        
        # Scaling based on world speed (pl227 has speed 1.0)
        speed = 1.0
        try:
            config = FileManager.load_json_file("config.json")
            # In a real scenario we'd get this from a world settings provider
            # but for now we use speed 1.0 as confirmed by user
        except: pass

        return {
            "wood": int(tbl.get(buildings.get("wood", 0), 5) * speed),
            "stone": int(tbl.get(buildings.get("stone", 0), 5) * speed),
            "iron": int(tbl.get(buildings.get("iron", 0), 5) * speed)
        }

    # ------------------------------------------------------------------
    # Attack flags  (migrated from cache/attacks/*.json)
    # ------------------------------------------------------------------

    @staticmethod
    def upsert_attack_flags(village_id: str, **flags) -> None:
        """Persist attack-profiling flags for a target village to the DB.

        Accepted keyword args mirror the columns added to DBVillage:
        is_safe, high_profile, low_profile, last_attack_at,
        attack_count, total_loot, total_losses, total_sent.
        """
        if not HAS_SQLALCHEMY:
            return
        s = DatabaseManager._session()
        try:
            row = s.get(DBVillage, str(village_id))
            if row is None:
                row = DBVillage(id=str(village_id))
                s.add(row)
            for k, v in flags.items():
                if hasattr(row, k):
                    setattr(row, k, v)
            s.commit()
        except Exception as e:
            logger.error("upsert_attack_flags error: %s", e)
            s.rollback()
        finally:
            s.close()

    @staticmethod
    def get_attack_flags(village_id: str) -> dict | None:
        """Return attack-profiling flags for a village, or None if not found."""
        if not HAS_SQLALCHEMY:
            return None
        s = DatabaseManager._session()
        try:
            row = s.get(DBVillage, str(village_id))
            if row is None:
                return None
            return {
                "is_safe":        row.is_safe,
                "high_profile":   row.high_profile,
                "low_profile":    row.low_profile,
                "last_attack_at": row.last_attack_at,
                "attack_count":   row.attack_count,
                "total_loot":     row.total_loot or {},
                "total_losses":   row.total_losses,
                "total_sent":     row.total_sent,
            }
        finally:
            s.close()

    @staticmethod
    def get_all_attack_flags() -> dict:
        """Return attack-profiling flags for every village in the DB.

        Returns a dict keyed by village_id string.
        """
        if not HAS_SQLALCHEMY:
            return {}
        s = DatabaseManager._session()
        try:
            rows = s.query(DBVillage).filter(
                DBVillage.last_attack_at.isnot(None)
            ).all()
            return {
                str(r.id): {
                    "is_safe":        r.is_safe,
                    "high_profile":   r.high_profile,
                    "low_profile":    r.low_profile,
                    "last_attack_at": r.last_attack_at,
                    "attack_count":   r.attack_count,
                    "total_loot":     r.total_loot or {},
                    "total_losses":   r.total_losses,
                    "total_sent":     r.total_sent,
                }
                for r in rows
            }
        finally:
            s.close()

    # ------------------------------------------------------------------
    # Kill scores  (cache/world/kill_*.txt)
    # ------------------------------------------------------------------

    @staticmethod
    def upsert_kill_scores(player_id: str, **scores) -> None:
        """Upsert ODA/ODD/OD kill-score data for a player.

        Keyword args: score_att, score_def, score_all, rank_att, rank_def, rank_all.
        """
        if not HAS_SQLALCHEMY:
            return
        s = DatabaseManager._session()
        try:
            row = s.get(DBKillScore, str(player_id))
            if row is None:
                row = DBKillScore(player_id=str(player_id))
                s.add(row)
            for k, v in scores.items():
                if hasattr(row, k):
                    setattr(row, k, v)
            s.commit()
        except Exception as e:
            logger.error("upsert_kill_scores error: %s", e)
            s.rollback()
        finally:
            s.close()

    @staticmethod
    def get_kill_scores(player_id: str) -> dict | None:
        """Return kill-score data for a player."""
        if not HAS_SQLALCHEMY:
            return None
        s = DatabaseManager._session()
        try:
            row = s.get(DBKillScore, str(player_id))
            if row is None:
                return None
            return {
                "score_att": row.score_att,
                "score_def": row.score_def,
                "score_all": row.score_all,
                "rank_att":  row.rank_att,
                "rank_def":  row.rank_def,
                "rank_all":  row.rank_all,
            }
        finally:
            s.close()

    # ------------------------------------------------------------------
    # Conquers  (cache/world/conquer.txt)
    # ------------------------------------------------------------------

    @staticmethod
    def bulk_upsert_conquers(rows: list[dict]) -> int:
        """Insert conquer records that are not yet in the DB.

        Each dict must have keys: village_id, timestamp (datetime), new_owner, old_owner.
        Returns the number of newly inserted rows.
        """
        if not HAS_SQLALCHEMY or not rows:
            return 0
        s = DatabaseManager._session()
        inserted = 0
        try:
            for rec in rows:
                exists = (
                    s.query(DBConquer)
                    .filter(
                        DBConquer.village_id == str(rec["village_id"]),
                        DBConquer.timestamp == rec["timestamp"],
                        DBConquer.new_owner == str(rec.get("new_owner", "")),
                    )
                    .first()
                )
                if exists:
                    continue
                # Ensure the village row exists (bare stub)
                if not s.get(DBVillage, str(rec["village_id"])):
                    s.add(DBVillage(id=str(rec["village_id"])))
                s.add(
                    DBConquer(
                        village_id=str(rec["village_id"]),
                        timestamp=rec["timestamp"],
                        new_owner=str(rec.get("new_owner", "")),
                        old_owner=str(rec.get("old_owner", "")),
                    )
                )
                inserted += 1
            s.commit()
        except Exception as e:
            logger.error("bulk_upsert_conquers error: %s", e)
            s.rollback()
        finally:
            s.close()
        return inserted

    @staticmethod
    def get_recent_conquers(limit: int = 100) -> list[dict]:
        """Return the most recent conquer events."""
        if not HAS_SQLALCHEMY:
            return []
        s = DatabaseManager._session()
        try:
            rows = (
                s.query(DBConquer)
                .order_by(DBConquer.timestamp.desc())
                .limit(limit)
                .all()
            )
            return [
                {
                    "village_id": r.village_id,
                    "timestamp":  r.timestamp.isoformat() if r.timestamp else None,
                    "new_owner":  r.new_owner,
                    "old_owner":  r.old_owner,
                }
                for r in rows
            ]
        finally:
            s.close()

# Bootstrap
try: get_engine()
except Exception as e: logger.warning("DB init failed: %s", e)
