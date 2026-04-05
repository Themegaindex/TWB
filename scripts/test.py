from core.extractors import Extractor
import re

with open("report.html") as f:
    report = f.read()

print("== EXTRACTOR TEST ==")
attacker = re.search(r'(?s)(<table id="attack_info_att".+?</table>)', report)
if not attacker:
    print("NO ATTACKER")
else:
    units = re.search(r'(?s)<table id="attack_info_att_units"(.+?)</table>', attacker.group(1))
    if not units:
        print("NO UNITS")
    else:
        sent_units = re.findall(r"(?s)<tr[^>]*>(.+?)</tr>", units.group(1))
        print("Matches of TR:", len(sent_units))
        for idx, u in enumerate(sent_units):
             print(f"TR {idx}", Extractor.units_in_total(u))
