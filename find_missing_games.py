#!/usr/bin/env python
"""Find missing games by checking all sources."""
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

print("=" * 100)
print("MISSING GAMES ANALYSIS")
print("=" * 100)

# 1. Load Excel
excel_path = Path("games.xlsx")
wb = openpyxl.load_workbook(excel_path)
ws = wb.active

excel_games = []
for row_idx, row in enumerate(ws.iter_rows(min_row=4, max_row=200), start=4):
    game_num = row[1].value  # Column B
    if not game_num or str(game_num).lower() == 'totals':
        continue

    date_val = row[0].value
    if isinstance(date_val, datetime):
        date_val = date_val.strftime('%Y-%m-%d')

    excel_games.append({
        'gameNumber': str(game_num),
        'date': str(date_val),
        'location': str(row[2].value) if row[2].value else '',
        'row': row_idx
    })

print(f"\n1. EXCEL FILE (games.xlsx)")
print(f"   Total games found: {len(excel_games)}")
print(f"   Game numbers: {sorted([g['gameNumber'] for g in excel_games])[:20]}...")

# 2. Load JSON
json_path = Path("data/all_games.json")
with open(json_path, 'r', encoding='utf-8') as f:
    json_games = json.load(f)

valid_json = [g for g in json_games if g.get('gameNumber')]
print(f"\n2. JSON FILE (data/all_games.json)")
print(f"   Total games: {len(valid_json)}")
print(f"   Game numbers: {sorted([str(g['gameNumber']) for g in valid_json])[:20]}...")

# 3. Compare
excel_set = set(g['gameNumber'] for g in excel_games)
json_set = set(str(g['gameNumber']) for g in valid_json)

missing_in_json = excel_set - json_set
missing_in_excel = json_set - excel_set

print(f"\n3. COMPARISON")
print(f"   Excel only: {sorted(missing_in_json)}")
print(f"   JSON only: {sorted(missing_in_excel)}")

# 4. Show missing game details
if missing_in_json:
    print(f"\n4. MISSING IN JSON ({len(missing_in_json)} games):")
    for game_num in sorted(missing_in_json):
        game = next(g for g in excel_games if g['gameNumber'] == game_num)
        print(f"   - Game {game_num}: {game['date']} - {game['location']} (Row {game['row']})")

# 5. List ALL Excel games
print(f"\n5. ALL {len(excel_games)} GAMES IN EXCEL (for reference):")
for i, game in enumerate(sorted(excel_games, key=lambda g: int(g['gameNumber']) if g['gameNumber'].isdigit() else 0), 1):
    print(f"   {i:2d}. {game['gameNumber']:5s} | {game['date']} | {game['location'][:30]}")

print(f"\n" + "=" * 100)
print(f"SUMMARY: {len(missing_in_json)} games missing from JSON that are in Excel")
print("=" * 100)
