import re
from core.extractors import Extractor

with open('cache/logs/unknown_screen_debug.html', 'r', encoding='utf-8') as f:
    text = f.read()

print("Using game_state:", Extractor.game_state(text))

grabber1 = re.search(r'TribalWars\.updateGameData\(\s*({.*})\s*\);?', text)
print("grabber1:", bool(grabber1))

grabber2 = re.search(r'TribalWars\.updateGameData\(\s*({.*})\s*\);?', text, re.DOTALL)
print("grabber2 with DOTALL:", bool(grabber2))

