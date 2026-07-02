#!/usr/bin/env python
"""Remove game 1416 from JSON."""
import json
from pathlib import Path

json_path = Path("data/all_games.json")

# Load
with open(json_path, 'r', encoding='utf-8') as f:
    games = json.load(f)

# Remove game 1416
before = len(games)
games = [g for g in games if not (g.get('gameNumber') == '1416' and g.get('date') == '2026-01-24')]
after = len(games)

print(f"Removed {before - after} game(s)")
print(f"Before: {before} games")
print(f"After: {after} games")

# Save
with open(json_path, 'w', encoding='utf-8') as f:
    json.dump(games, f, indent=2, ensure_ascii=False)

print("Done - game 1416 removed from JSON")
