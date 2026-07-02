#!/usr/bin/env python
"""Restore ALL games from Excel to JSON properly."""
import json
from pathlib import Path
from datetime import datetime

try:
    import openpyxl
except:
    import subprocess
    import sys
    subprocess.check_call([sys.executable, "-m", "pip", "install", "openpyxl", "-q"])
    import openpyxl

print("=" * 100)
print("RESTORE ALL GAMES FROM EXCEL")
print("=" * 100)

# Load Excel - ALL games including 1416
excel_path = Path("games.xlsx")
wb = openpyxl.load_workbook(excel_path)
ws = wb.active

excel_games = []
print("\nReading Excel...")

for row_idx, row in enumerate(ws.iter_rows(min_row=4, max_row=100), start=4):
    game_num = row[1].value  # Column B = gameNumber

    # Skip empty rows and "Totals" row
    if not game_num or str(game_num).lower() == 'totals' or str(game_num) == 'None':
        continue

    # Extract all fields
    date_val = row[0].value  # Column A = date
    if isinstance(date_val, datetime):
        date_val = date_val.strftime('%Y-%m-%d')
    else:
        date_val = str(date_val)

    game = {
        'season': '2025/2026',
        'gameNumber': str(game_num),
        'date': date_val,
        'location': str(row[2].value) if row[2].value else '',
        'transportation': float(row[3].value) if row[3].value and row[3].value != '' else 0.0,
        'food': float(row[4].value) if row[4].value and row[4].value != '' else 0.0,
        'gamePayment': float(row[5].value) if row[5].value and row[5].value != '' else 0.0,
        'paidStatus': str(row[6].value) if row[6].value else '',
        'paymentDate': None,
        'observations': str(row[8].value) if row[8].value else None,
    }

    # Handle payment date
    if row[7].value:
        payment_date = row[7].value
        if isinstance(payment_date, datetime):
            payment_date = payment_date.strftime('%Y-%m-%d')
        game['paymentDate'] = str(payment_date) if payment_date else None

    excel_games.append(game)

print(f"Found {len(excel_games)} games in Excel")
print(f"Game numbers: {sorted([g['gameNumber'] for g in excel_games])}")

# Check for 1416
has_1416 = any(g['gameNumber'] == '1416' for g in excel_games)
print(f"\nGame 1416 in Excel: {has_1416}")

if has_1416:
    game_1416 = next(g for g in excel_games if g['gameNumber'] == '1416')
    print(f"  - Date: {game_1416['date']}")
    print(f"  - Location: {game_1416['location']}")
    print(f"  - Transportation: {game_1416['transportation']}")
    print(f"  - Food: {game_1416['food']}")
    print(f"  - Payment: {game_1416['gamePayment']}")
    print(f"  - Status: {game_1416['paidStatus']}")

# Save to JSON
json_path = Path("data/all_games.json")

print(f"\nSaving to JSON...")
with open(json_path, 'w', encoding='utf-8') as f:
    json.dump(excel_games, f, indent=2, ensure_ascii=False)

print(f"Saved {len(excel_games)} games to {json_path}")

# Verify
with open(json_path, 'r', encoding='utf-8') as f:
    loaded = json.load(f)

print(f"\nVerification:")
print(f"  Games in JSON: {len(loaded)}")
has_1416_json = any(str(g.get('gameNumber')) == '1416' for g in loaded)
print(f"  Game 1416 in JSON: {has_1416_json}")

# Check for duplicates
from collections import Counter
game_nums = [g['gameNumber'] for g in loaded]
counter = Counter(game_nums)
dups = {k: v for k, v in counter.items() if v > 1}
print(f"  Duplicates: {dups if dups else 'None'}")

print("\n" + "=" * 100)
if len(loaded) == 57 and has_1416_json and not dups:
    print("SUCCESS: All 57 games restored to JSON!")
else:
    print(f"Status: Games={len(loaded)}, 1416={has_1416_json}, Dups={bool(dups)}")
print("=" * 100)
