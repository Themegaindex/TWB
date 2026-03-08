import logging
import json
import re

# We will apply the new extraction logic locally as a complete test.
from game.reports import ReportManager

html = """
<table align="center" class="vis" width="100%" style="margin-top: -2px;">
<tbody><tr>
<th width="140">Temat</th>
<th width="400">
nogamescdn.com/asset/4dd1f0b2/graphic/dots/green.webp" class="" data-title="Pe&lstrok;na wygrana"> 
 data-id="">
 class="quickedit-content">
 class="quickedit-label">
umBK (Wioska MagnumBK 001 (575|370) K35 ) atakuje Wioska Ksajeno (573|367) K35 
>
>
>
</th>
</tr>
<tr>
<td>Czas bitwy</td>
<td>03.03.26 16:30:04<span class="small grey">:711</span></td>
</tr>
<tr>
    <td colspan="2" valign="top" height="160" style="border: solid 1px black; padding: 4px;" class="report_ReportAttack">
umBK wygra&lstrok;</h3>

<table id="attack_info_att" width="100%" style="border: 1px solid #DED3B9">
<tbody><tr>
<th style="width:20%">Agresor:</th>
<th><a href="/game.php?village=20427&amp;screen=info_player&amp;id=849088513" data-title="Piekielne Alpaki!">MagnumBK</a></th>
</tr>
<tr>
<td>Pochodzenie:</td>
<td><span class="village_anchor contexted" data-player="849088513" data-id="20427"><a href="#">Wioska MagnumBK 001 (575|370) K35 </a></span></td>
</tr>

    <tr><td colspan="2" style="padding:0px">
        <table id="attack_info_att_units" class="vis" style="border-collapse:collapse">
            <tbody><tr class="center">
                <td></td>
                <td width="35"><a class="unit_link" href="#" data-unit="spear"><img src="xyz" class="" data-title="Pikinier"></a></td>
            </tr>
            <tr>
                <td width="20%">Ilo&sacute;&cacute;:</td>
                <td style="text-align:center" data-unit-count="58" class="unit-item unit-item-spear">58</td>
            </tr>
            <tr>
                <td align="left" width="20%">Straty:</td>
                <td style="text-align:center" data-unit-count="0" class="unit-item unit-item-spear hidden">0</td>
            </tr>
        </tbody></table>
    </td></tr>
</tbody></table>

<table id="attack_info_def" width="100%" style="border: 1px solid #DED3B9">
<tbody><tr>
<th style="width:20%">Obro&nacute;ca:</th>
<th><a href="/game.php?village=20427&amp;screen=info_player&amp;id=849304095">Ksajeno</a></th>
</tr>
<tr>
<td>Cel:</td>
<td><span class="village_anchor contexted" data-player="849304095" data-id="20575"><a href="#">Wioska Ksajeno (573|367) K35 </a></span></td>
</tr>

    <tr><td colspan="2" style="padding:0px">
        <table id="attack_info_def_units" class="vis" style="border-collapse:collapse">
            <tbody><tr class="center">
                <td></td>
                <td width="35"><a class="unit_link" href="#" data-unit="spear"><img src="xyz" class="faded" data-title="Pikinier"></a></td>
            </tr>
            <tr>
                <td width="20%">Ilo&sacute;&cacute;:</td>
                <td style="text-align:center" data-unit-count="0" class="unit-item unit-item-spear hidden">0</td>
            </tr>
            <tr>
                <td align="left" width="20%">Straty:</td>
                <td style="text-align:center" data-unit-count="0" class="unit-item unit-item-spear hidden">0</td>
            </tr>
        </tbody></table>
    </td></tr>
</tbody></table>

<table id="attack_results" width="100%" style="border: 1px solid #DED3B9">
<tbody><tr>
        <span class="nowrap"><span class="icon header wood" data-title="Drewno"> </span>850</span>
           <span class="nowrap"><span class="icon header stone" data-title="Glina"> </span>850</span>
           <span class="nowrap"><span class="icon header iron" data-title="&Zdot;elazo"> </span>850</span>
        </td>
</tr>
</tbody></table>
"""

logging.basicConfig(level=logging.INFO)
rm = ReportManager()
rm.logger = logging.getLogger("Test")
rm.game_state = {"player": {"id": "849088513"}}

print("==== PARSOWANIE RAPORTU ====")
result = rm.attack_report(html, 6053254)
print("Wynik ataku (Czy poprawnie odczytał wygraną/straty i wojska):")
print(json.dumps(rm.last_reports, indent=2))
