"""
Relational database layer for TWB using SQLite + SQLAlchemy.
Replaces the per-file JSON cache for persistent structured data.
Tables: Villages, Attacks, Reports, Units_Lost, Resources_Snapshot
"""
import logging
import os
import json
from datetime import datetime
from typing import Optional, List, Dict, Any

try:
    from sqlalchemy import (
        create_engine, Column, Integer, String, Float, Boolean,
        DateTime, ForeignKey, Text, Index
    )
    from sqlalchemy.dialects.postgresql import JSONB
    from sqlalchemy.orm import DeclarativeBase, relationship, Session, sessionmaker
    HAS_SQLALCHEMY = True
except ImportError:
    HAS_SQLALCHEMY = False

from core.filemanager import FileManager

logger = logging.getLogger("Database")

_engine = None
_SessionLocal = None


# ---------------------------------------------------------------------------
# ORM models
# ---------------------------------------------------------------------------

if HAS_SQLALCHEMY:
    class Base(DeclarativeBase):
        pass

    class DBVillage(Base):
        __tablename__ = "villages"
        id          = Column(String, primary_key=True)   # village_id string
        name        = Column(String, default="")
        x           = Column(Integer, default=0)
        y           = Column(Integer, default=0)
        points      = Column(Integer, default=0)
        wood_prod   = Column(Float, default=0)   # resources/hour from mine levels
        stone_prod  = Column(Float, default=0)
        iron_prod   = Column(Float, default=0)
        last_seen   = Column(DateTime, default=datetime.utcnow)
        is_owned    = Column(Boolean, default=False)  # True = our village
        owner_id    = Column(String, default="0")

        attacks   = relationship("DBAttack", back_populates="target_village",
                                 foreign_keys="DBAttack.target_id",
                                 cascade="all, delete-orphan")
        reports   = relationship("DBReport", back_populates="village",
                                 cascade="all, delete-orphan")
        settings  = relationship("DBVillageSettings", back_populates="village", uselist=False, cascade="all, delete-orphan")

        __table_args__ = (
            Index("ix_village_xy", "x", "y"),
        )

    class DBSession(Base):
        __tablename__ = "sessions"
        id          = Column(Integer, primary_key=True, autoincrement=True)
        endpoint    = Column(String, nullable=False)
        server      = Column(String, nullable=False)
        cookies     = Column(JSONB, default=dict)
        user_agent  = Column(String, nullable=True)
        updated_at  = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    class DBVillageSettings(Base):
        __tablename__ = "village_settings"
        village_id  = Column(String, ForeignKey("villages.id"), primary_key=True)
        settings    = Column(JSONB, default=dict)
        
        village     = relationship("DBVillage", back_populates="settings")

    class DBAttack(Base):
        __tablename__ = "attacks"
        id              = Column(Integer, primary_key=True, autoincrement=True)
        origin_id       = Column(String, ForeignKey("villages.id"), nullable=True)
        target_id       = Column(String, ForeignKey("villages.id"), nullable=False)
        sent_at         = Column(DateTime, default=datetime.utcnow)
        arrived_at      = Column(DateTime, nullable=True)
        loot_wood       = Column(Integer, default=0)
        loot_stone      = Column(Integer, default=0)
        loot_iron       = Column(Integer, default=0)
        troops_sent     = Column(JSONB, default=dict)   # {"axe": 100, ...}
        won             = Column(Boolean, nullable=True)  # None = unknown
        scout_only      = Column(Boolean, default=False)

        target_village  = relationship("DBVillage", back_populates="attacks",
                                       foreign_keys=[target_id])
        losses          = relationship("DBUnitsLost", back_populates="attack",
                                       cascade="all, delete-orphan")

        __table_args__ = (
            Index("ix_attack_target", "target_id"),
            Index("ix_attack_sent",   "sent_at"),
        )

    class DBUnitsLost(Base):
        __tablename__ = "units_lost"
        id          = Column(Integer, primary_key=True, autoincrement=True)
        attack_id   = Column(Integer, ForeignKey("attacks.id"), nullable=False)
        unit_type   = Column(String, nullable=False)
        amount      = Column(Integer, default=0)
        side        = Column(String, default="attacker")  # "attacker" / "defender"

        attack      = relationship("DBAttack", back_populates="losses")

    class DBReport(Base):
        __tablename__ = "reports"
        report_id   = Column(String, primary_key=True)
        village_id  = Column(String, ForeignKey("villages.id"), nullable=True)
        report_type = Column(String, default="")  # "attack", "scout", etc.
        origin_id   = Column(String, nullable=True)
        dest_id     = Column(String, nullable=True)
        raw_extra   = Column(JSONB, default=dict)   # full extra dict from parser
        loot_wood   = Column(Integer, default=0)
        loot_stone  = Column(Integer, default=0)
        loot_iron   = Column(Integer, default=0)
        scout_wood      = Column(Integer, nullable=True)  # resources seen by scouts
        scout_stone     = Column(Integer, nullable=True)
        scout_iron      = Column(Integer, nullable=True)
        scout_buildings = Column(JSONB, nullable=True)
        created_at  = Column(DateTime, default=datetime.utcnow)
        losses_json = Column(JSONB, default=dict)

        village     = relationship("DBVillage", back_populates="reports",
                                   foreign_keys=[village_id])

        __table_args__ = (
            Index("ix_report_dest",  "dest_id"),
            Index("ix_report_type",  "report_type"),
        )

    class DBResourceSnapshot(Base):
        """
        Periodic snapshot of own-village resources (wood/stone/iron).
        Useful for graphs in the dashboard.
        """
        __tablename__ = "resource_snapshots"
        id          = Column(Integer, primary_key=True, autoincrement=True)
        village_id  = Column(String, nullable=False)
        recorded_at = Column(DateTime, default=datetime.utcnow)
        wood        = Column(Integer, default=0)
        stone       = Column(Integer, default=0)
        iron        = Column(Integer, default=0)
        storage     = Column(Integer, default=0)

        __table_args__ = (
            Index("ix_snapshot_village", "village_id"),
        )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def get_engine():
    global _engine
    if _engine is None:
        try:
            config = FileManager.load_json_file("config.json")
            db_config = config.get("database", {})
            db_url = db_config.get("url", "postgresql://postgres:postgres@localhost:5432/twb")
            pool_size = db_config.get("pool_size", 10)
        except Exception:
            db_url = "postgresql://postgres:postgres@localhost:5432/twb"
            pool_size = 10

        _engine = create_engine(
            db_url,
            pool_size=pool_size,
            max_overflow=20
        )
        if HAS_SQLALCHEMY:
            Base.metadata.create_all(_engine)
            logger.info("PostgreSQL database ready at %s", db_url)
        else:
            logger.warning("SQLAlchemy not installed – DB layer disabled")
    return _engine


def get_session() -> Optional[Session]:
    """Return a new SQLAlchemy Session (caller must close/commit)."""
    if not HAS_SQLALCHEMY:
        return None
    global _SessionLocal
    if _SessionLocal is None:
        _SessionLocal = sessionmaker(bind=get_engine())
    return _SessionLocal()


# ---------------------------------------------------------------------------
# Helper functions used by the rest of the bot
# ---------------------------------------------------------------------------

class DatabaseManager:
    """
    High-level helpers so the rest of the codebase doesn't need to import
    SQLAlchemy directly.
    """

    @staticmethod
    def _session():
        return get_session()

    # ----- Villages -----

    @staticmethod
    def upsert_village(vid: str, name: str = "", x: int = 0, y: int = 0,
                       points: int = 0, owner_id: str = "0", is_owned: bool = False,
                       wood_prod: float = 0, stone_prod: float = 0, iron_prod: float = 0):
        if not HAS_SQLALCHEMY:
            return
        s = DatabaseManager._session()
        try:
            row = s.get(DBVillage, vid)
            if not row:
                row = DBVillage(id=vid)
                s.add(row)
            row.name      = name
            row.x         = x
            row.y         = y
            row.points    = points
            row.owner_id  = owner_id
            row.is_owned  = is_owned
            row.last_seen = datetime.utcnow()
            if wood_prod:
                row.wood_prod  = wood_prod
            if stone_prod:
                row.stone_prod = stone_prod
            if iron_prod:
                row.iron_prod  = iron_prod
            s.commit()
        except Exception as e:
            logger.error("upsert_village error: %s", e)
            s.rollback()
        finally:
            s.close()

    @staticmethod
    def get_village(vid: str) -> Optional[Dict]:
        if not HAS_SQLALCHEMY:
            return None
        s = DatabaseManager._session()
        try:
            row = s.get(DBVillage, vid)
            if not row:
                return None
            return {
                "id": row.id, "name": row.name, "x": row.x, "y": row.y,
                "points": row.points, "owner_id": row.owner_id, "is_owned": row.is_owned,
                "wood_prod": row.wood_prod, "stone_prod": row.stone_prod, "iron_prod": row.iron_prod,
                "last_seen": row.last_seen.isoformat() if row.last_seen else None,
            }
        finally:
            s.close()

    # ----- Attacks -----

    @staticmethod
    def save_attack(origin_id: str, target_id: str,
                    troops_sent: dict, loot: dict = None,
                    won: bool = None, scout_only: bool = False,
                    sent_at: datetime = None, arrived_at: datetime = None) -> Optional[int]:
        if not HAS_SQLALCHEMY:
            return None
        s = DatabaseManager._session()
        try:
            # Ensure village row exists
            for vid in [origin_id, target_id]:
                if vid and not s.get(DBVillage, vid):
                    s.add(DBVillage(id=vid))

            loot = loot or {}
            a = DBAttack(
                origin_id   = origin_id,
                target_id   = target_id,
                sent_at     = sent_at or datetime.utcnow(),
                arrived_at  = arrived_at,
                loot_wood   = int(loot.get("wood", 0)),
                loot_stone  = int(loot.get("stone", 0)),
                loot_iron   = int(loot.get("iron", 0)),
                troops_sent = troops_sent,
                won         = won,
                scout_only  = scout_only,
            )
            s.add(a)
            s.commit()
            return a.id
        except Exception as e:
            logger.error("save_attack error: %s", e)
            s.rollback()
            return None
        finally:
            s.close()

    @staticmethod
    def save_units_lost(attack_id: int, losses: dict, side: str = "attacker"):
        if not HAS_SQLALCHEMY or not attack_id:
            return
        s = DatabaseManager._session()
        try:
            for unit_type, amount in losses.items():
                if int(amount) > 0:
                    s.add(DBUnitsLost(
                        attack_id=attack_id,
                        unit_type=unit_type,
                        amount=int(amount),
                        side=side,
                    ))
            s.commit()
        except Exception as e:
            logger.error("save_units_lost error: %s", e)
            s.rollback()
        finally:
            s.close()

    @staticmethod
    def get_attack_history(target_id: str, limit: int = 50) -> List[Dict]:
        if not HAS_SQLALCHEMY:
            return []
        s = DatabaseManager._session()
        try:
            rows = (s.query(DBAttack)
                    .filter(DBAttack.target_id == target_id)
                    .order_by(DBAttack.sent_at.desc())
                    .limit(limit)
                    .all())
            out = []
            for r in rows:
                losses = [{"unit": l.unit_type, "amount": l.amount, "side": l.side} for l in r.losses]
                out.append({
                    "id":          r.id,
                    "origin_id":   r.origin_id,
                    "target_id":   r.target_id,
                    "sent_at":     r.sent_at.isoformat() if r.sent_at else None,
                    "loot_wood":   r.loot_wood,
                    "loot_stone":  r.loot_stone,
                    "loot_iron":   r.loot_iron,
                    "loot_total":  r.loot_wood + r.loot_stone + r.loot_iron,
                    "troops_sent": r.troops_sent,
                    "won":         r.won,
                    "scout_only":  r.scout_only,
                    "losses":      losses,
                })
            return out
        finally:
            s.close()

    # ----- Reports -----

    @classmethod
    def get_report(cls, report_id: str):
        """Check if a report exists in the database"""
        if not HAS_SQLALCHEMY:
            return None
        s = cls._session()
        try:
            return s.get(DBReport, str(report_id))
        finally:
            s.close()

    @classmethod
    def save_report(cls, report_id: str, report_type: str,
                    origin_id: str = None, dest_id: str = None,
                    extra: dict = None, loot: dict = None,
                    losses: dict = None, scout_resources: dict = None,
                    scout_buildings: dict = None):
        if not HAS_SQLALCHEMY:
            return
        s = cls._session()
        try:
            # Ensure village rows exist
            for vid in [origin_id, dest_id]:
                if vid and not s.get(DBVillage, vid):
                    s.add(DBVillage(id=vid))

            existing = s.get(DBReport, str(report_id))
            if existing:
                return  # don't re-process

            loot  = loot or {}
            extra = extra or {}

            r = DBReport(
                report_id   = str(report_id),
                village_id  = dest_id,
                report_type = report_type,
                origin_id   = origin_id,
                dest_id     = dest_id,
                raw_extra   = extra,
                loot_wood   = int(loot.get("wood", 0)),
                loot_stone  = int(loot.get("stone", 0)),
                loot_iron   = int(loot.get("iron", 0)),
                losses_json = losses or {},
                scout_wood  = int(scout_resources.get("wood", 0)) if scout_resources else None,
                scout_stone = int(scout_resources.get("stone", 0)) if scout_resources else None,
                scout_iron  = int(scout_resources.get("iron", 0)) if scout_resources else None,
                scout_buildings = scout_buildings,
            )
            s.add(r)
            s.commit()
        except Exception as e:
            logger.error("save_report error: %s", e)
            s.rollback()
        finally:
            s.close()

    # ----- Resource snapshots -----

    @staticmethod
    def save_resource_snapshot(village_id: str, wood: int, stone: int, iron: int, storage: int):
        if not HAS_SQLALCHEMY:
            return
        s = DatabaseManager._session()
        try:
            s.add(DBResourceSnapshot(
                village_id=village_id, wood=wood, stone=stone, iron=iron, storage=storage
            ))
            s.commit()
        except Exception as e:
            logger.error("save_resource_snapshot error: %s", e)
            s.rollback()
        finally:
            s.close()

    # ----- Production estimation -----

    # Production lookup table per mine level (resources/hour)
    # Values from the official Tribal Wars wiki
    _PROD_TABLE = {
        0: 5, 1: 30, 2: 35, 3: 41, 4: 47, 5: 55, 6: 64, 7: 74, 8: 86,
        9: 100, 10: 117, 11: 136, 12: 158, 13: 184, 14: 214, 15: 249,
        16: 289, 17: 337, 18: 392, 19: 456, 20: 530, 21: 616, 22: 717,
        23: 834, 24: 970, 25: 1128, 26: 1311, 27: 1525, 28: 1773, 29: 2062,
        30: 2400,
    }

    @staticmethod
    def estimate_production(buildings: dict) -> dict:
        """
        Given scanned building levels, return estimated resources/hour.
        `buildings` should have keys like 'wood', 'stone', 'iron'.
        """
        tbl = DatabaseManager._prod_table()
        return {
            "wood":  tbl.get(buildings.get("wood",  0), 0),
            "stone": tbl.get(buildings.get("stone", 0), 0),
            "iron":  tbl.get(buildings.get("iron",  0), 0),
        }

    @staticmethod
    def _prod_table():
        return DatabaseManager._PROD_TABLE

    @staticmethod
    def update_village_production(vid: str, buildings: dict):
        """Recalculate and store estimated production for a village."""
        prod = DatabaseManager.estimate_production(buildings)
        DatabaseManager.upsert_village(
            vid,
            wood_prod=prod["wood"],
            stone_prod=prod["stone"],
            iron_prod=prod["iron"],
        )
        return prod


# Bootstrap DB on import
try:
    get_engine()
except Exception as _e:
    logger.warning("Could not initialise database engine: %s", _e)
