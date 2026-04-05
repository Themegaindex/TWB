import re
import json

with open("core/extractors.py", "r", encoding="utf-8") as f:
    text = f.read()

text = text.replace("r'TribalWars\.updateGameData\(\s*({.*})\s*\);?', res, re.DOTALL", "r'TribalWars\.updateGameData\(\s*({.*?})\s*\);?', res")
text = text.replace("r'(?:var|window\.)game_data\s*=\s*((\{.*?\})|(\{.*\}))\s*;', res, re.DOTALL", "r'(?:var|window\.)game_data\s*=\s*((\{.*?\}))\s*;', res")

with open("core/extractors.py", "w", encoding="utf-8") as f:
    f.write(text)

