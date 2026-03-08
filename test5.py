import re

html = """
<table id="attack_results" width="100%" style="border: 1px solid #DED3B9">

<tbody><tr>
 class="nowrap"><span class="icon header wood" data-title="Drewno"> </span>850</span> <span class="nowrap"><span class="icon header stone" data-title="Glina"> </span>850</span> <span class="nowrap"><span class="icon header iron" data-title="Żelazo"> </span>850</span> </td>
 class="grey">.</span>550/2<span class="grey">.</span>730</td>
html.replace('<span class="grey">.</span>', "")
results = re.search(r'(?s)(<table id="attack_results".+?</table>)', report)
if results:
    loot = {}
    for loot_entry in re.findall(
            r'<span class="icon header (wood|stone|iron)".+?</span>([\d\.,\s&nbsp;]+)', report
    ):
        amount = re.sub(r'[^\d]', '', loot_entry[1])
        loot[loot_entry[0]] = amount
    print(loot)
else:
    print("No results")

