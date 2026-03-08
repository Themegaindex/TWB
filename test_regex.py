import re

html1 = '<span class="icon header wood" title="Drewno"></span>1 000'
res1 = re.findall(r'<span class="icon header (wood|stone|iron)".+?</span>([\d\.,\s&nbsp;]+)', html1)
print(res1)
