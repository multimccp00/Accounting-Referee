#!/usr/bin/env python
"""Import games from Excel to JSON, avoiding duplicates."""
import json
import sys
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent))

try:
    import openpyxl
except:
    import subprocess
    subprocess.check_call([sys.executable, "-m", "pip", "install", "openpyxl", "-q"])
    import openpyxl

print("=" * 100)
print("IMPORT GAMES FROM EXCEL")
print("=" * 100)

# Load Excel
excel_path = Path("games.xlsx")
wb = openpyxl.load_workbook(excel_path)
ws = wb.active

excel_games = []
print("\n1. Reading games from Excel...")

for row_num in range(4, 100):
    row = ws[row_num]

    game_num = row[1].value
    if not game_num or str(game_num).lower().strip() == 'totals':
        break

    # Extract all fields
    date_val = row[0].value
    if isinstance(date_val, datetime):
        date_val = date_val.strftime('%Y-%m-%d')

    game = {
        'season': '2025/2026',
        'gameNumber': str(game_num),
        'date': str(date_val) if date_val else '',
        'location': str(row[2].value) if row[2].value else '',
        'transportation': float(row[3].value) if row[3].value else 0.0,
        'food': float(row[4].value) if row[4].value else 0.0,
        'gamePayment': float(row[5].value) if row[5].value else 0.0,
        'paidStatus': str(row[6].value) if row[6].value else '',
        'paymentDate': None,
        'observations': str(row[8].value) if row[8].value else None
    }

    if row[7].value:
        payment_date = row[7].value
        if isinstance(payment_date, datetime):
            payment_date = payment_date.strftime('%Y-%m-%d')
        game['paymentDate'] = str(payment_date)

    excel_games.append(game)

print(f"   Found {len(excel_games)} games in Excel")

# Load JSON
json_path = Path("data/all_games.json")
with open(json_path, 'r', encoding='utf-8') as f:
    json_games = json.load(f)

print(f"\n2. Current JSON games: {len(json_games)}")

# Find games to add (not in JSON)
excel_combos = set((g['gameNumber'], g['date']) for g in excel_games)
json_combos = set((str(g.get('gameNumber')), g.get('date')) for g in json_games)

games_to_add = excel_combos - json_combos
games_already_there = excel_combos & json_combos
games_only_in_json = json_combos - excel_combos

print(f"\n3. Comparison:")
print(f"   Games in Excel: {len(excel_games)}")
print(f"   Games in JSON: {len(json_games)}")
print(f"   Already in JSON: {len(games_already_there)}")
print(f"   New games to add: {len(games_to_add)}")
print(f"   Only in JSON (not in Excel): {len(games_only_in_json)}")

# Show what's being added
if games_to_add:
    print(f"\n4. Games to add ({len(games_to_add)}):")
    for gnum, gdate in sorted(games_to_add):
        excel_game = next(g for g in excel_games if g['gameNumber'] == gnum and g['date'] == gdate)
        print(f"   {gnum} | {gdate} | {excel_game['location'][:40]}")

    # Add them
    print(f"\n5. Adding games to JSON...")
    for gnum, gdate in games_to_add:
        excel_game = next(g for g in excel_games if g['gameNumber'] == gnum and g['date'] == gdate)
        json_games.append(excel_game)

    # Save
    with open(json_path, 'w', encoding='utf-8') as f:
        json.dump(json_games, f, indent=2, ensure_ascii=False)

    print(f"   Added {len(games_to_add)} games")
    print(f"   Total now: {len(json_games)}")
else:
    print(f"\n4. No new games to add - all Excel games already in JSON")

print("\n" + "=" * 100)
print(f"COMPLETE: JSON now has {len(json_games)} games")
print("=" * 100)
