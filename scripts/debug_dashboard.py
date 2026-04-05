
import sys
import os
from sqlalchemy import text

# Dodaj root projektu do path
sys.path.append(os.getcwd())

from core.database import get_engine

DEBUG_SQL = """
-- 1. Create v_unit_costs
CREATE OR REPLACE VIEW v_unit_costs AS
SELECT * FROM (VALUES 
    ('spear', 50, 30, 10),
    ('sword', 30, 30, 70),
    ('axe', 60, 30, 40),
    ('spy', 50, 50, 20),
    ('light', 125, 100, 250),
    ('marcher', 250, 100, 150),
    ('heavy', 200, 150, 600),
    ('ram', 300, 200, 200),
    ('catapult', 320, 400, 100)
) AS t(unit_type, wood, stone, iron);

-- 2. Create v_farming_roi
CREATE OR REPLACE VIEW v_farming_roi AS
SELECT 
    r.dest_id as target_id,
    (r.loot_wood + r.loot_stone + r.loot_iron) as gross_loot,
    r.created_at,
    r.report_id
FROM reports r
WHERE r.report_type = 'attack' AND r.created_at > NOW() - INTERVAL '7 days';

-- Uwaga: Wersja uproszczona ROI do debugowania, żeby sprawdzić czy dane w ogóle płyną
-- Można ją rozbudować o odejmowanie kosztów z units_lost później
"""

def debug_dashboard():
    print("--- Dashboard Debug Tool ---")
    engine = get_engine()
    print(f"Connecting to: {engine.url}")
    
    try:
        with engine.connect() as conn:
            print("[1/3] Testing basic connection... OK")
            
            print("[2/3] Creating missing views (v_unit_costs, v_farming_roi)...")
            conn.execute(text(DEBUG_SQL))
            conn.commit()
            print("Views created/updated successfully.")
            
            print("[3/3] Checking if there is any data in 'reports'...")
            count = conn.execute(text("SELECT COUNT(*) FROM reports")).scalar()
            print(f"Found {count} reports in database.")
            
            if count == 0:
                print("WARNING: 'reports' table is empty! Dashboard won't show anything until bot collects reports.")
            
            print("\nDebug finished. Restart the bot and check /api/dashboard/stats in your browser.")
            
    except Exception as e:
        print(f"\nERROR: {e}")

if __name__ == "__main__":
    debug_dashboard()
