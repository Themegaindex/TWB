import re
from core.extractors import Extractor

html = """
<table class="vis">
src="https://dspl.innogamescdn.com/asset/4dd1f0b2/graphic/dots/green.webp" class="" data-title="Pełna wygrana"> 
 data-id="">
 class="quickedit-content">
 class="quickedit-label">
umBK (Wioska MagnumBK 001 (575|370) K35 ) atakuje Wioska Ksajeno (573|367) K35 
>
>
>
16:30:04<span class="small grey">:711</span>                <td colspan="2" valign="top" height="160" style="border: solid 1px black; padding: 4px;" class="report_ReportAttack">
<h3>MagnumBK wygrał</h3>

<table id="attack_info_att" width="100%" style="border: 1px solid #DED3B9">
<tbody><tr>
<th style="width:20%">Agresor:</th>
<th><a href="/game.php?village=20427&amp;screen=info_player&amp;id=849088513" data-title="Piekielne Alpaki!">MagnumBK</a></th>
</tr>
<tr>
<td>Pochodzenie:</td>
<td><span class="village_anchor contexted" data-player="849088513" data-id="20427"><a href="/game.php?village=20427&amp;screen=info_village&amp;id=20427">Wioska MagnumBK 001 (575|370) K35 </a><a class="ctx" href="#"></a></span></td>
</tr>

    <tr><td colspan="2" style="padding:0px">
        <table id="attack_info_att_units" class="vis" style="border-collapse:collapse">
            <tbody><tr class="center">
                <td></td>
                <td width="35"><a class="unit_link" href="#" data-unit="spear"><img src="https://dspl.innogamescdn.com/asset/4dd1f0b2/graphic/unit/unit_spear.webp" class="" data-title="Pikinier"></a></td>
            </tr>
            <tr>
                <td width="20%">Ilość:</td>
                                    <td style="text-align:center" data-unit-count="58" class="unit-item unit-item-spear">58</td>
            </tr>
            <tr>
                <td align="left" width="20%">Straty:</td>
                                    <td style="text-align:center" data-unit-count="0" class="unit-item unit-item-spear hidden">0</td>
            </tr>
        </tbody></table>
    </td></tr>
</tbody></table>
"""

attacker = re.search(r'(?s)(<table id="attack_info_att".+?</table>)', html)
units = re.search(r'(?s)<table id="attack_info_att_units"(.+?)</table>', attacker.group(1))
sent_units = re.findall(r"(?s)<tr[^>]*>(.+?)</tr>", units.group(1))

print("Extractor on sent:", Extractor.units_in_total(sent_units[1]))
print("Extractor on lost:", Extractor.units_in_total(sent_units[2]))

def fix(res):
    # original: data = re.findall(r'(?s)class=\Wunit-item unit-item-([a-z]+)\W.+?(\d+)</td>', res)
    return re.findall(r'(?s)class=[\'"]?[^\'"]*?\bunit-item unit-item-([a-z]+)\b[^\'"]*?[\'"].*?(?<=>)\s*(\d+)\s*</td>', res)

print("Fix on sent:", fix(sent_units[1]))
print("Fix on lost:", fix(sent_units[2]))

