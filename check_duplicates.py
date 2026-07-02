#!/usr/bin/env python
"""Check for duplicate games."""
import json
from pathlib import Path
from datetime import datetime
from collections import Counter

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

    if game.get('gameNumber'):
        excel_games.append(game)

# Load JSON
json_path = Path("data/all_games.json")
with open(json_path, 'r', encoding='utf-8') as f:
    json_games = json.load(f)

print("=" * 70)
print("DUPLICATE CHECK")
print("=" * 70)

# Check for duplicate game numbers
excel_numbers = [str(g.get('gameNumber', '')) for g in excel_games]
json_numbers = [str(g.get('gameNumber', '')) for g in json_games]

excel_counter = Counter(excel_numbers)
json_counter = Counter(json_numbers)

excel_dups = {k: v for k, v in excel_counter.items() if v > 1}
json_dups = {k: v for k, v in json_counter.items() if v > 1}

print(f"\nExcel duplicates: {excel_dups}")
print(f"JSON duplicates: {json_dups}")

# Show duplicate games from Excel
if excel_dups:
    print("\nDuplicate games in Excel:")
    for game_num, count in excel_dups.items():
        print(f"\n  Game {game_num} appears {count} times:")
        games = [g for g in excel_games if str(g.get('gameNumber')) == game_num]
        for i, g in enumerate(games, 1):
            print(f"    {i}. {g.get('date')} - {g.get('location')}")

# Summary
print("\n" + "=" * 70)
print("SUMMARY")
print("=" * 70)
print(f"Excel: {len(excel_games)} games, {len(excel_dups)} duplicate game numbers")
print(f"JSON: {len(json_games)} games, {len(json_dups)} duplicate game numbers")

if not excel_dups and not json_dups:
    print("\n[OK] No duplicate games found!")
else:
    print("\n[WARNING] Duplicate games detected!")
