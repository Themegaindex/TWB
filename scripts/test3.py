from core.extractors import Extractor
import re
with open("report.html") as f:
    report = f.read()

attacker = re.search(r'(?s)(<table id="attack_info_att".+?</table>)', report)
units = re.search(r'(?s)<table id="attack_info_att_units"(.+?)</table>', attacker.group(1))
sent_units = re.findall(r"(?s)<tr[^>]*>(.+?)</tr>", units.group(1))

print("TR 2:", repr(sent_units[2]))

def new_units_in_total(res):
    # This matches generic data-unit-count="..." but also backwards compatibility?
    d = re.findall(r'class=[\'"]?[^\'"]*?\bunit-item unit-item-([a-z]+)\b[^\'"]*?[\'"].*?>\s*(\d+)\s*</td>', res)
    return d

print("NEW:", new_units_in_total(sent_units[2]))
