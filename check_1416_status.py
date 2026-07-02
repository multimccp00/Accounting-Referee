#!/usr/bin/env python
"""Check if 1416 is in JSON."""
import json
from pathlib import Path

json_path = Path("data/all_games.json")

with open(json_path, 'r', encoding='utf-8') as f:
    games = json.load(f)

has_1416 = any(g.get('gameNumber') == '1416' for g in games)
total = len(games)

print(f"Total games: {total}")
print(f"Has game 1416: {has_1416}")

if has_1416:
    game_1416 = next(g for g in games if g.get('gameNumber') == '1416')
    print(f"Game 1416: {game_1416['date']} - {game_1416['location']}")
