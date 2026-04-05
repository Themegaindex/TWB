import sys
import os
import json
from core.request import WebWrapper
from core.extractors import Extractor
from core.database import DatabaseManager, DBSession

db_s = DatabaseManager._session()
session = db_s.query(DBSession).order_by(DBSession.updated_at.desc()).first()
db_s.close()
if not session:
    print("No session in DB")
    sys.exit(1)

wrapper = WebWrapper(session.endpoint)
# start will load from db
wrapper.start()
res = wrapper.get_url("game.php?village=35333&screen=overview")
print("Requested url:", res.url)
print("Game state:", Extractor.game_state(res.text) is not None)

# Save test response
with open('tmp_overview.html', 'w', encoding='utf-8') as f:
    f.write(res.text)

print("Saved HTML to tmp_overview.html")
