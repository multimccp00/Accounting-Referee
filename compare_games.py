#!/usr/bin/env python
"""Compare Excel and JSON games in detail."""
import json
from pathlib import Path
from datetime import datetime

try:
    import openpyxl
except ImportError:
    import subprocess
    import sys
    subprocess.check_call([sys.executable, "-m", "pip", "install", "openpyxl", "-q"])
    import openpyxl

# Load Excel
excel_path = Path("games.xlsx")
wb = openpyxl.load_workbook(excel_path)
ws = wb.active

# Extract games from Excel
excel_games = []
headers = None

for row_idx, row in enumerate(ws.iter_rows(min_row=3, values_only=True), start=3):
    if row_idx == 3:
        headers = [h for h in row if h]
        continue

    if not row[0]:
        break

    game = {}
    for col_idx, header in enumerate(headers):
        if col_idx < len(row):
            value = row[col_idx]
            if isinstance(value, datetime):
                value = value.strftime('%Y-%m-%d')
            game[header] = value

    if 'season' not in game:
        game['season'] = '2025/2026'

    # Only add if has a valid game number
    if game.get('gameNumber'):
        excel_games.append(game)

# Load JSON
json_path = Path("data/all_games.json")
with open(json_path, 'r', encoding='utf-8') as f:
    json_games = json.load(f)

print("=" * 70)
print("GAME COMPARISON")
print("=" * 70)

print(f"\nExcel games: {len(excel_games)}")
print(f"JSON games: {len(json_games)}")

# Get game numbers
excel_numbers = sorted([str(g.get('gameNumber', '')) for g in excel_games if g.get('gameNumber')])
json_numbers = sorted([str(g.get('gameNumber', '')) for g in json_games if g.get('gameNumber')])

print(f"\nExcel game numbers: {excel_numbers}")
print(f"JSON game numbers: {json_numbers}")

# Find differences
excel_set = set(excel_numbers)
json_set = set(json_numbers)

missing_in_json = excel_set - json_set
extra_in_json = json_set - excel_set

print(f"\nMissing in JSON (in Excel but not JSON): {sorted(missing_in_json)}")
print(f"Extra in JSON (in JSON but not Excel): {sorted(extra_in_json)}")

# Show detailed info about missing games
if missing_in_json:
    print(f"\n{len(missing_in_json)} Games missing from JSON:")
    for game_num in sorted(missing_in_json):
        game = next((g for g in excel_games if str(g.get('gameNumber')) == game_num), None)
        if game:
            print(f"  Game {game_num}: {game.get('date')} - {game.get('location')}")

# Show detailed info about extra games in JSON
if extra_in_json:
    print(f"\n{len(extra_in_json)} Extra games in JSON (not in Excel):")
    for game_num in sorted(extra_in_json):
        game = next((g for g in json_games if str(g.get('gameNumber')) == game_num), None)
        if game:
            print(f"  Game {game_num}: {game.get('date')} - {game.get('location')}")

if not missing_in_json and not extra_in_json:
    print("\n[OK] All games match between Excel and JSON!")
