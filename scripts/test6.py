import re
from core.extractors import Extractor
from game.reports import ReportManager
import json
import logging

logging.basicConfig(level=logging.INFO)

with open("report.html", "w") as f:
    f.write("""<table align="center" class="vis" width="100%" style="margin-top: -2px;">
... (I'll just pass the full string from problem manually, but wait, the prompt gave it directly!)
""")
