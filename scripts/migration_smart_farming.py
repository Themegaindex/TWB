
import logging
import os
import sys

# Ensure project root is in path for imports
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from sqlalchemy import text
from core.database import get_engine

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("Migration")

MIGRATION_SQL = """
-- 1. Add atomic pending resource columns
ALTER TABLE villages 
ADD COLUMN IF NOT EXISTS pending_wood INT DEFAULT 0,
ADD COLUMN IF NOT EXISTS pending_stone INT DEFAULT 0,
ADD COLUMN IF NOT EXISTS pending_iron INT DEFAULT 0;

-- 2. Create partial index for performance optimization
-- Targets only recent attacks to speed up 'get_predicted_resources'
CREATE INDEX IF NOT EXISTS ix_attacks_active_target 
ON attacks (target_id, sent_at DESC) 
WHERE (loot_wood + loot_stone + loot_iron) > 0;

-- 3. Trigger Function: Reset pending resources on new report
CREATE OR REPLACE FUNCTION fn_reset_pending_resources()
RETURNS TRIGGER AS $$
BEGIN
    UPDATE villages 
    SET pending_wood = 0, pending_stone = 0, pending_iron = 0
    WHERE id = NEW.dest_id;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- 4. Attach Trigger to reports table
DROP TRIGGER IF EXISTS tr_reset_pending_on_report ON reports;
CREATE TRIGGER tr_reset_pending_on_report
AFTER INSERT ON reports
FOR EACH ROW EXECUTE FUNCTION fn_reset_pending_resources();

-- 5. Atomic Reservation Function
CREATE OR REPLACE FUNCTION reserve_farm_loot(
    v_id TEXT, 
    req_w INT, req_s INT, req_i INT,
    min_threshold INT DEFAULT 100
) RETURNS TABLE (success BOOLEAN, reserved_w INT, reserved_s INT, reserved_i INT) AS $$
DECLARE
    r_wood INT; r_stone INT; r_iron INT;
    v_cap INT; v_w_prod INT; v_s_prod INT; v_i_prod INT;
    h_delta FLOAT;
    avail_w INT; avail_s INT; avail_i INT;
    latest_report_time TIMESTAMP;
BEGIN
    -- 1. Atomic Lock on Village Row
    SELECT storage_cap, wood_prod, stone_prod, iron_prod, 
           pending_wood, pending_stone, pending_iron
    INTO v_cap, v_w_prod, v_s_prod, v_i_prod, avail_w, avail_s, avail_i
    FROM villages WHERE id = v_id FOR UPDATE;

    -- 2. Get Latest Report Data
    SELECT created_at, scout_wood, scout_stone, scout_iron 
    INTO latest_report_time, r_wood, r_stone, r_iron
    FROM reports WHERE dest_id = v_id ORDER BY created_at DESC LIMIT 1;

    IF NOT FOUND THEN 
        RETURN QUERY SELECT FALSE, 0, 0, 0; 
        RETURN; 
    END IF;

    -- 3. Calculate Real-Time Production & Subtract Pending
    h_delta := EXTRACT(EPOCH FROM (NOW() - latest_report_time)) / 3600.0;
    
    avail_w := LEAST(v_cap, r_wood + (v_w_prod * h_delta)) - avail_w;
    avail_s := LEAST(v_cap, r_stone + (v_s_prod * h_delta)) - avail_s;
    avail_i := LEAST(v_cap, r_iron + (v_i_prod * h_delta)) - avail_i;

    -- 4. Validate and Update (Atomic Reservation)
    IF (avail_w + avail_s + avail_i) >= (req_w + req_s + req_i) OR (avail_w + avail_s + avail_i) >= min_threshold THEN
        UPDATE villages SET 
            pending_wood = pending_wood + req_w,
            pending_stone = pending_stone + req_s,
            pending_iron = pending_iron + req_i
        WHERE id = v_id;
        RETURN QUERY SELECT TRUE, req_w, req_s, req_i;
    ELSE
        RETURN QUERY SELECT FALSE, 0, 0, 0;
    END IF;
END;
$$ LANGUAGE plpgsql;
"""

def run_migration():
    engine = get_engine()
    # Check if it's PostgreSQL
    if "postgresql" not in str(engine.url):
        logger.error("This migration is only for PostgreSQL. Current engine: %s", engine.url)
        return

    logger.info("Starting SQL migration...")
    with engine.connect() as conn:
        transaction = conn.begin()
        try:
            # We split by semicolon but be careful with functions
            # Actually, we can just execute the whole block if the driver supports it
            conn.execute(text(MIGRATION_SQL))
            transaction.commit()
            logger.info("Migration successful!")
        except Exception as e:
            transaction.rollback()
            logger.error("Migration failed: %s", e)
            raise

if __name__ == "__main__":
    run_migration()
