import requests
import json
import os
from core.filemanager import FileManager

config = FileManager.load_json_file("config.json")
if not config:
    print("No config.json found")
    exit(1)

ua = config["bot"].get("user_agent", "Mozilla/5.0")
cookies = config["villages"].get(list(config["villages"].keys())[0], {}).get("cookies", {})
# Wait, cookies might be in DBSession or provided differently.
# TWB handles it via WebWrapper.

from core.request import WebWrapper
wrapper = WebWrapper(config["server"]["endpoint"], server=config["server"]["server"], endpoint=config["server"]["endpoint"])
# Manually load some session from DB
from core.database import DatabaseManager, DBSession
db_s = DatabaseManager._session()
row = db_s.query(DBSession).order_by(DBSession.updated_at.desc()).first()
if row:
    wrapper.set_cookies(row.cookies)
    wrapper.headers["user-agent"] = row.user_agent
db_s.close()

print(f"Testing URL: {config['server']['endpoint']}game.php?screen=overview_villages")
res = wrapper.get_url("game.php?screen=overview_villages")
print(f"Status: {res.status_code}")
print(f"Final URL: {res.url}")
with open("test_out.html", "w", encoding="utf-8") as f:
    f.write(res.text)
print("Saved to test_out.html")
