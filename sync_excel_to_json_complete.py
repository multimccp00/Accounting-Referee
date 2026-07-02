#!/usr/bin/env python
"""Sync EVERY game from Excel to JSON, no filtering."""
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
print("COMPLETE SYNC: EXCEL TO JSON")
print("=" * 100)

# Load Excel - read EVERY row
excel_path = Path("games.xlsx")
wb = openpyxl.load_workbook(excel_path)
ws = wb.active

excel_games = []
print("\nReading every row from Excel...")

for row_num in range(4, 100):  # Read up to row 100
    row = ws[row_num]

    # Get raw values
    date_val = row[0].value  # Column A
    game_num = row[1].value  # Column B
    location = row[2].value  # Column C
    transport = row[3].value  # Column D
    food = row[4].value  # Column E
    payment = row[5].value  # Column F
    paid_status = row[6].value  # Column G
    payment_date = row[7].value  # Column H
    observations = row[8].value  # Column I

    # Stop at end marker (Totals or empty game number)
    if not game_num or str(game_num).lower().strip() in ['totals']:
        break

    # Convert date
    if isinstance(date_val, datetime):
        date_val = date_val.strftime('%Y-%m-%d')

    if isinstance(payment_date, datetime):
        payment_date = payment_date.strftime('%Y-%m-%d')

    # Build game
    game = {
        'season': '2025/2026',
        'gameNumber': str(game_num),
        'date': str(date_val) if date_val else '',
        'location': str(location) if location else '',
        'transportation': float(transport) if transport else 0.0,
        'food': float(food) if food else 0.0,
        'gamePayment': float(payment) if payment else 0.0,
        'paidStatus': str(paid_status) if paid_status else '',
        'paymentDate': str(payment_date) if payment_date else None,
        'observations': str(observations) if observations else None
    }

    excel_games.append(game)

print(f"Total games loaded from Excel: {len(excel_games)}")

# Show summary
game_dates = {}
for g in excel_games:
    key = f"{g['gameNumber']}|{g['date']}"
    game_dates[key] = g

print(f"Unique game+date combinations: {len(game_dates)}")

# Save to JSON
json_path = Path("data/all_games.json")
print(f"\nSaving {len(excel_games)} games to JSON...")

with open(json_path, 'w', encoding='utf-8') as f:
    json.dump(excel_games, f, indent=2, ensure_ascii=False)

print(f"Saved to {json_path}")

# Verification
from collections import Counter
combos = [(g['gameNumber'], g['date']) for g in excel_games]
counter = Counter(combos)
duplicates = {k: v for k, v in counter.items() if v > 1}

print(f"\nVerification:")
print(f"  Total games: {len(excel_games)}")
print(f"  Unique combinations: {len(game_dates)}")
print(f"  Duplicates (same number+date): {duplicates if duplicates else 'None'}")

# Show first and last few
print(f"\nFirst 3 games:")
for g in excel_games[:3]:
    print(f"  {g['gameNumber']} | {g['date']} | {g['location'][:30]}")

print(f"\nLast 3 games:")
for g in excel_games[-3:]:
    print(f"  {g['gameNumber']} | {g['date']} | {g['location'][:30]}")

print("\n" + "=" * 100)
print(f"SUCCESS: {len(excel_games)} games synced from Excel to JSON")
print("=" * 100)
