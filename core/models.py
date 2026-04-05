from datetime import datetime
from sqlalchemy import (
    Column, Integer, String, Float, Boolean,
    DateTime, ForeignKey, Text, Index, JSON, BigInteger
)
from sqlalchemy.orm import DeclarativeBase, relationship

class Base(DeclarativeBase):
    pass

class DBVillage(Base):
    __tablename__ = "villages"
    id          = Column(String, primary_key=True)
    name        = Column(String, default="")
    x           = Column(Integer, default=0)
    y           = Column(Integer, default=0)
    points      = Column(Integer, default=0)
    wood_prod   = Column(Float, default=0)
    stone_prod  = Column(Float, default=0)
    iron_prod   = Column(Float, default=0)
    storage_cap = Column(Integer, default=1000)
    pending_wood  = Column(Integer, default=0)
    pending_stone = Column(Integer, default=0)
    pending_iron  = Column(Integer, default=0)
    last_seen      = Column(DateTime, default=datetime.utcnow)
    is_owned       = Column(Boolean, default=False)
    owner_id       = Column(String, default="0")
    # --- attack flags (migrated from cache/attacks/*.json) ---
    is_safe        = Column(Boolean, default=True)
    high_profile   = Column(Boolean, default=False)
    low_profile    = Column(Boolean, default=False)
    last_attack_at = Column(DateTime, nullable=True)
    attack_count   = Column(Integer, default=0)
    total_loot     = Column(JSON, default=dict)
    total_losses   = Column(Integer, default=0)
    total_sent     = Column(Integer, default=0)

    attacks   = relationship("DBAttack", back_populates="target_village", foreign_keys="DBAttack.target_id", cascade="all, delete-orphan")
    reports   = relationship("DBReport", back_populates="village", cascade="all, delete-orphan")
    settings  = relationship("DBVillageSettings", back_populates="village", uselist=False, cascade="all, delete-orphan")

    __table_args__ = (Index("ix_village_xy", "x", "y"), Index("ix_village_owner", "owner_id"))

class DBPlayer(Base):
    __tablename__ = "players"
    id          = Column(String, primary_key=True)
    name        = Column(String, default="")
    ally_id     = Column(String, default="0")
    villages    = Column(Integer, default=0)
    points      = Column(Integer, default=0)
    rank        = Column(Integer, default=0)
    last_seen   = Column(DateTime, default=datetime.utcnow)

class DBAlly(Base):
    __tablename__ = "allies"
    id          = Column(String, primary_key=True)
    name        = Column(String, default="")
    tag         = Column(String, default="")
    members     = Column(Integer, default=0)
    villages    = Column(Integer, default=0)
    points      = Column(Integer, default=0)
    all_points  = Column(Integer, default=0)
    rank        = Column(Integer, default=0)
    last_seen   = Column(DateTime, default=datetime.utcnow)

class DBSession(Base):
    __tablename__ = "sessions"
    id          = Column(Integer, primary_key=True, autoincrement=True)
    endpoint    = Column(String, nullable=False)
    server      = Column(String, nullable=False)
    cookies     = Column(JSON, default=dict)
    user_agent  = Column(String, nullable=True)
    updated_at  = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class DBVillageSettings(Base):
    __tablename__ = "village_settings"
    village_id  = Column(String, ForeignKey("villages.id"), primary_key=True)
    settings    = Column(JSON, default=dict)
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
    troops_sent     = Column(JSON, default=dict)
    won             = Column(Boolean, nullable=True)
    scout_only      = Column(Boolean, default=False)

    target_village  = relationship("DBVillage", back_populates="attacks", foreign_keys=[target_id])
    losses          = relationship("DBUnitsLost", back_populates="attack", cascade="all, delete-orphan")

    __table_args__ = (Index("ix_attack_target", "target_id"), Index("ix_attack_sent", "sent_at"))

class DBUnitsLost(Base):
    __tablename__ = "units_lost"
    id          = Column(Integer, primary_key=True, autoincrement=True)
    attack_id   = Column(Integer, ForeignKey("attacks.id"), nullable=False)
    unit_type   = Column(String, nullable=False)
    amount      = Column(Integer, default=0)
    side        = Column(String, default="attacker")
    attack      = relationship("DBAttack", back_populates="losses")

class DBReport(Base):
    __tablename__ = "reports"
    report_id   = Column(String, primary_key=True)
    village_id  = Column(String, ForeignKey("villages.id"), nullable=True)
    report_type = Column(String, default="")
    origin_id   = Column(String, nullable=True)
    dest_id     = Column(String, nullable=True)
    raw_extra   = Column(JSON, default=dict)
    loot_wood   = Column(Integer, default=0)
    loot_stone  = Column(Integer, default=0)
    loot_iron   = Column(Integer, default=0)
    scout_wood      = Column(Integer, nullable=True)
    scout_stone     = Column(Integer, nullable=True)
    scout_iron      = Column(Integer, nullable=True)
    scout_buildings = Column(JSON, nullable=True)
    created_at  = Column(DateTime, default=datetime.utcnow)
    losses_json = Column(JSON, default=dict)
    village     = relationship("DBVillage", back_populates="reports", foreign_keys=[village_id])
    __table_args__ = (Index("ix_report_dest", "dest_id"), Index("ix_report_type", "report_type"))

class DBResourceSnapshot(Base):
    __tablename__ = "resource_snapshots"
    id          = Column(Integer, primary_key=True, autoincrement=True)
    village_id  = Column(String, nullable=False)
    recorded_at = Column(DateTime, default=datetime.utcnow)
    wood        = Column(Integer, default=0)
    stone       = Column(Integer, default=0)
    iron        = Column(Integer, default=0)
    storage     = Column(Integer, default=0)
    __table_args__ = (Index("ix_snapshot_village", "village_id"),)


class DBConquer(Base):
    """Tabela podbojów — alimentowana z cache/world/conquer.txt."""
    __tablename__ = "conquers"
    id         = Column(Integer, primary_key=True, autoincrement=True)
    village_id = Column(String, ForeignKey("villages.id"), nullable=False)
    timestamp  = Column(DateTime, nullable=False)
    new_owner  = Column(String, nullable=True)
    old_owner  = Column(String, nullable=True)
    __table_args__ = (
        Index("ix_conquer_village", "village_id"),
        Index("ix_conquer_time", "timestamp"),
    )


class DBKillScore(Base):
    """Punkty ODA/ODD/OD gracza — alimentowane z cache/world/kill_*.txt."""
    __tablename__ = "kill_scores"
    player_id  = Column(String, ForeignKey("players.id"), primary_key=True)
    score_att  = Column(BigInteger, default=0)
    score_def  = Column(BigInteger, default=0)
    score_all  = Column(BigInteger, default=0)
    rank_att   = Column(Integer, default=0)
    rank_def   = Column(Integer, default=0)
    rank_all   = Column(Integer, default=0)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
