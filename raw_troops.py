import json
import requests
import re

with open('/root/TWB/config.json', 'r') as f:
    cfg = json.load(f)

with open('/root/TWB/cache/session.json', 'r') as f:
    session = json.load(f)

village_id = list(cfg["villages"].keys())[0]
endpoint = cfg["server"]["endpoint"]
cookie_dict = session["cookies"]

url = f"{endpoint}?village={village_id}&screen=train"
headers = {"User-Agent": "Mozilla/5.0"}
res = requests.get(url, cookies=cookie_dict, headers=headers)

data = re.search(r'(?s)unit_managers.units = (\{.+?\});', res.text)
if data:
    raw = data.group(1)
    processed = re.sub(r'([\{\s,])(\w+)(:)', r'\1"\2"\3', raw)
    unit_data = json.loads(processed, strict=False)
    for k in list(unit_data.keys())[:2]:
        print("KEY:", k)
        print("in_village:", unit_data[k].get("in_village"))
        print("in_total:", unit_data[k].get("in_total"))
else:
    print("No unit data found!")
