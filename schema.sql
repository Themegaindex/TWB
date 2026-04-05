-- Schema for TWB PostgreSQL Database
-- Matches core/models.py definitions

-- Players table
CREATE TABLE IF NOT EXISTS players (
    id VARCHAR(20) PRIMARY KEY,
    name VARCHAR(255) DEFAULT '',
    ally_id VARCHAR(20) DEFAULT '0',
    villages INTEGER DEFAULT 0,
    points INTEGER DEFAULT 0,
    rank INTEGER DEFAULT 0,
    last_seen TIMESTAMP WITHOUT TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Villages table
CREATE TABLE IF NOT EXISTS villages (
    id VARCHAR(20) PRIMARY KEY,
    name VARCHAR(255) DEFAULT '',
    x INTEGER DEFAULT 0,
    y INTEGER DEFAULT 0,
    points INTEGER DEFAULT 0,
    wood_prod FLOAT DEFAULT 0,
    stone_prod FLOAT DEFAULT 0,
    iron_prod FLOAT DEFAULT 0,
    last_seen TIMESTAMP WITHOUT TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    is_owned BOOLEAN DEFAULT FALSE,
    owner_id VARCHAR(20) DEFAULT '0'
);

-- Allies table
CREATE TABLE IF NOT EXISTS allies (
    id VARCHAR(20) PRIMARY KEY,
    name VARCHAR(255) DEFAULT '',
    tag VARCHAR(255) DEFAULT '',
    members INTEGER DEFAULT 0,
    villages INTEGER DEFAULT 0,
    points INTEGER DEFAULT 0,
    all_points INTEGER DEFAULT 0,
    rank INTEGER DEFAULT 0,
    last_seen TIMESTAMP WITHOUT TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Sessions table
CREATE TABLE IF NOT EXISTS sessions (
    id SERIAL PRIMARY KEY,
    endpoint VARCHAR(255) NOT NULL,
    server VARCHAR(255) NOT NULL,
    cookies JSON DEFAULT '{}',
    user_agent TEXT,
    updated_at TIMESTAMP WITHOUT TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Village Settings table
CREATE TABLE IF NOT EXISTS village_settings (
    village_id VARCHAR(20) PRIMARY KEY REFERENCES villages(id),
    settings JSON DEFAULT '{}'
);

-- Attacks table
CREATE TABLE IF NOT EXISTS attacks (
    id SERIAL PRIMARY KEY,
    origin_id VARCHAR(20) REFERENCES villages(id),
    target_id VARCHAR(20) NOT NULL REFERENCES villages(id),
    sent_at TIMESTAMP WITHOUT TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    arrived_at TIMESTAMP WITHOUT TIME ZONE,
    loot_wood INTEGER DEFAULT 0,
    loot_stone INTEGER DEFAULT 0,
    loot_iron INTEGER DEFAULT 0,
    troops_sent JSON DEFAULT '{}',
    won BOOLEAN,
    scout_only BOOLEAN DEFAULT FALSE
);

-- Units Lost table
CREATE TABLE IF NOT EXISTS units_lost (
    id SERIAL PRIMARY KEY,
    attack_id INTEGER NOT NULL REFERENCES attacks(id),
    unit_type VARCHAR(50) NOT NULL,
    amount INTEGER DEFAULT 0,
    side VARCHAR(20) DEFAULT 'attacker'
);

-- Reports table
CREATE TABLE IF NOT EXISTS reports (
    report_id VARCHAR(20) PRIMARY KEY,
    village_id VARCHAR(20) REFERENCES villages(id),
    report_type VARCHAR(50) DEFAULT '',
    origin_id VARCHAR(20),
    dest_id VARCHAR(20),
    raw_extra JSON DEFAULT '{}',
    loot_wood INTEGER DEFAULT 0,
    loot_stone INTEGER DEFAULT 0,
    loot_iron INTEGER DEFAULT 0,
    scout_wood INTEGER,
    scout_stone INTEGER,
    scout_iron INTEGER,
    scout_buildings JSON,
    created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    losses_json JSON DEFAULT '{}'
);

-- Resource Snapshots table
CREATE TABLE IF NOT EXISTS resource_snapshots (
    id SERIAL PRIMARY KEY,
    village_id VARCHAR(20) NOT NULL,
    recorded_at TIMESTAMP WITHOUT TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    wood INTEGER DEFAULT 0,
    stone INTEGER DEFAULT 0,
    iron INTEGER DEFAULT 0,
    storage INTEGER DEFAULT 0
);

-- Indexes for performance
CREATE INDEX IF NOT EXISTS ix_village_xy ON villages (x, y);
CREATE INDEX IF NOT EXISTS ix_village_owner ON villages (owner_id);
CREATE INDEX IF NOT EXISTS ix_attack_target ON attacks (target_id);
CREATE INDEX IF NOT EXISTS ix_attack_sent ON attacks (sent_at);
CREATE INDEX IF NOT EXISTS ix_report_dest ON reports (dest_id);
CREATE INDEX IF NOT EXISTS ix_report_type ON reports (report_type);
CREATE INDEX IF NOT EXISTS ix_snapshot_village ON resource_snapshots (village_id);
