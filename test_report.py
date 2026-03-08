import re
from core.extractors import Extractor

report = """
            <tr class="center">
                <td></td>
    # explicitly bypass requests cookie jar and slap the header directlyki kawalerzysta"></a></td><td width="35"><a class="unit_link" href="#" data-unit="ram"><img src="https://dspl.innogamescdn.com/asset/4dd1f0b2/graphic/unit/unit_ram.webp" class="faded" data-title="Taran"></a></td><td width="35"><a class="unit_link" href="#" data-unit="catapult"><img src="https://dspl.innogamescdn.com/asset/4dd1f0b2/graphic/unit/unit_catapult.webp" class="faded" data-title="Katapulta"></a></td><td width="35"><a class="unit_link" href="#" data-unit="knight"><img src="https://dspl.innogamescdn.com/asset/4dd1f0b2/graphic/unit/unit_knight.webp" class="faded" data-title="Rycerz"></a></td><td width="35"><a class="unit_link" href="#" data-unit="snob"><img src="https://dspl.innogamescdn.com/asset/4dd1f0b2/graphic/unit/unit_snob.webp" class="faded" data-title="Szlachcic"></a></td>
            </tr>
            <tr>
                <td width="20%">Ilość:</td>
                                    <td style="text-align:center" data-unit-count="10" class="unit-item unit-item-spear">10</td><td style="text-align:center" data-unit-count="1" class="unit-item unit-item-sword">1</td><td style="text-align:center" data-unit-count="0" class="unit-item unit-item-axe hidden">0</td><td style="text-align:center" data-unit-count="0" class="unit-item unit-item-archer hidden">0</td><td style="text-align:center" data-unit-count="0" class="unit-item unit-item-spy hidden">0</td><td style="text-align:center" data-unit-count="0" class="unit-item unit-item-light hidden">0</td><td style="text-align:center" data-unit-count="0" class="unit-item unit-item-marcher hidden">0</td><td style="text-align:center" data-unit-count="0" class="unit-item unit-item-heavy hidden">0</td><td style="text-align:center" data-unit-count="0" class="unit-item unit-item-ram hidden">0</td><td style="text-align:center" data-unit-count="0" class="unit-item unit-item-catapult hidden">0</td><td style="text-align:center" data-unit-count="0" class="unit-item unit-item-knight hidden">0</td><td style="text-align:center" data-unit-count="0" class="unit-item unit-item-snob hidden">0</td>
                            </tr>
            <tr>
                <td align="left" width="20%">Straty:</td>
                                    <td style="text-align:center" data-unit-count="1" class="unit-item unit-item-spear">1</td><td style="text-align:center" data-unit-count="0" class="unit-item unit-item-sword hidden">0</td><td style="text-align:center" data-unit-count="0" class="unit-item unit-item-axe hidden">0</td><td style="text-align:center" data-unit-count="0" class="unit-item unit-item-archer hidden">0</td><td style="text-align:center" data-unit-count="0" class="unit-item unit-item-spy hidden">0</td><td style="text-align:center" data-unit-count="0" class="unit-item unit-item-light hidden">0</td><td style="text-align:center" data-unit-count="0" class="unit-item unit-item-marcher hidden">0</td><td style="text-align:center" data-unit-count="0" class="unit-item unit-item-heavy hidden">0</td><td style="text-align:center" data-unit-count="0" class="unit-item unit-item-ram hidden">0</td><td style="text-align:center" data-unit-count="0" class="unit-item unit-item-catapult hidden">0</td><td style="text-align:center" data-unit-count="0" class="unit-item unit-item-knight hidden">0</td><td style="text-align:center" data-unit-count="0" class="unit-item unit-item-snob hidden">0</td>
                            </tr>
"""
print("REGEX SPLIT")
sent_units = re.findall("(?s)<tr>(.+?)</tr>", report)
print(len(sent_units))
for i, u in enumerate(sent_units):
    print(f"Row {i}:", Extractor.units_in_total(u))

print("BETTER SPLIT")
rows = re.findall(r'(?s)<tr[^>]*>(.+?)</tr>', report)
print(len(rows))
for i, u in enumerate(rows):
    print(f"Row {i}:", Extractor.units_in_total(u))

