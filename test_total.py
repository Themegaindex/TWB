import sys, json
from core.request import WebWrapper
from core.extractors import Extractor

with open('/root/TWB/config.json', 'r') as f: cfg = json.load(f)

wrapper = WebWrapper(cfg["server"]["endpoint"], server=cfg["server"]["server"], endpoint=cfg["server"]["endpoint"])
res = wrapper.start()
if not res:
    print("FAILED TO START")
    sys.exit(1)

village_id = list(cfg["villages"].keys())[0]

res = wrapper.get_url(f"game.php?village={village_id}&screen=train")
r_data = Extractor.recruit_data(res.text)
if r_data:
    for k in list(r_data.keys())[:3]:
        print("RECRUIT KEY:", k, r_data[k])
