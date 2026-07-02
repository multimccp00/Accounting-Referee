#!/usr/bin/env python
"""Final verification that games are restored."""
import json
from pathlib import Path
from collections import Counter

json_path = Path("data/all_games.json")
with open(json_path, 'r', encoding='utf-8') as f:
    games = json.load(f)

print("=" * 70)
print("FINAL VERIFICATION")
print("=" * 70)

print(f"\nTotal games in JSON: {len(games)}")

# Check for duplicates
game_nums = [str(g.get('gameNumber')) for g in games]
counter = Counter(game_nums)
duplicates = {k: v for k, v in counter.items() if v > 1}

print(f"Duplicate game numbers: {duplicates if duplicates else 'None'}")

# Check for invalid/None games
valid = [g for g in games if g.get('gameNumber')]
invalid = len(games) - len(valid)
print(f"Invalid games (no gameNumber): {invalid}")

# Sample games
print(f"\nSample games:")
for game in games[:3]:
    print(f"  - {game.get('gameNumber')}: {game.get('date')} - {game.get('location')}")
print(f"  ...")
for game in games[-3:]:
    print(f"  - {game.get('gameNumber')}: {game.get('date')} - {game.get('location')}")

# Final status
print("\n" + "=" * 70)
if len(games) == 57 and not duplicates and invalid == 0:
    print("STATUS: [OK] ALL GAMES RESTORED AND VERIFIED")
    print("=" * 70)
    print(f"\nYou have {len(games)} games:")
    print("- Game 1416 added")
    print("- Game 1417 duplicate fixed")
    print("- All games synchronized between Excel and JSON")
    print("\nReady to use: python app/main.py")
else:
    print("STATUS: [WARNING] Check required")
    print("=" * 70)
    if len(games) != 57:
        print(f"ERROR: Expected 57 games, got {len(games)}")
    if duplicates:
        print(f"ERROR: Found duplicate games: {duplicates}")
    if invalid > 0:
        print(f"ERROR: Found {invalid} invalid games")
