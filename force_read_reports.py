import sys
import os
import logging
import json

from core.database import DatabaseManager
from core.request import WebWrapper
from game.reports import ReportManager

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("ForceRead")

with open('config.json', 'r') as f:
    cfg = json.load(f)

wrapper = WebWrapper(
    cfg["server"]["endpoint"],
    server=cfg["server"]["server"],
    endpoint=cfg["server"]["endpoint"],
)

# Start reads from cache/session.json automatically
if not wrapper.start():
    logger.error("Błąd logowania na sesję! Upewnij się, że główny bot działa m.in na pl225.")
    sys.exit(1)

villages = list(cfg["villages"].keys())
if not villages:
    logger.error("Brak wiosek skonfigurowanych w config.json")
    sys.exit(1)

my_village = villages[0]
rep_man = ReportManager(wrapper=wrapper, village_id=my_village)

PAGES_TO_READ = 5
if len(sys.argv) > 1:
    try:
        PAGES_TO_READ = int(sys.argv[1])
    except ValueError:
        pass

logger.info(f"Rozpoczynam zczytywanie historycznych raportów (strony: {PAGES_TO_READ}) dla wioski {my_village}...")

for page in range(PAGES_TO_READ):
    logger.info(f"--- Skanuje stronę nr {page} ---")
    rep_man.read(page=page, full_run=True)

logger.info("Zakończono pobieranie raportów! Są one teraz w bazie twb.db.")
