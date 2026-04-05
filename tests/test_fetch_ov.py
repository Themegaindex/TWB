import sys
from core.request import WebWrapper
from core.extractors import Extractor
from core.database import DatabaseManager, DBSession

db_s = DatabaseManager._session()
session = db_s.query(DBSession).order_by(DBSession.updated_at.desc()).first()
db_s.close()
wrapper = WebWrapper(session.endpoint)
wrapper.start()
res = wrapper.get_url("game.php?screen=overview_villages")
print("Requested url:", res.url)
print("Game state:", Extractor.game_state(res.text) is not None)
