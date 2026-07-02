#!/usr/bin/env python
"""Final: Restore all 57 games from Excel including game 1416."""
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

print("RESTORING ALL 57 GAMES FROM EXCEL")
print("=" * 100)

# Read Excel - starting from row 4 and going until Totals row
excel_path = Path("games.xlsx")
wb = openpyxl.load_workbook(excel_path)
ws = wb.active

all_games = []

# Manually read rows 4 through 60 to catch all games
for row_num in range(4, 61):
    row = ws[row_num]

    # Extract values
    date_val = row[0].value  # Column A
    game_num_val = row[1].value  # Column B
    location_val = row[2].value  # Column C
    transport_val = row[3].value  # Column D
    food_val = row[4].value  # Column E
    payment_val = row[5].value  # Column F
    paid_status_val = row[6].value  # Column G
    payment_date_val = row[7].value  # Column H
    observations_val = row[8].value  # Column I

    # Skip if game number is empty or "Totals"
    if not game_num_val or str(game_num_val).strip().lower() in ['totals', 'none', '']:
        continue

    # Convert date if needed
    if isinstance(date_val, datetime):
        date_val = date_val.strftime('%Y-%m-%d')

    # Convert payment date if needed
    if isinstance(payment_date_val, datetime):
        payment_date_val = payment_date_val.strftime('%Y-%m-%d')

    # Build game object
    game = {
        'season': '2025/2026',
        'gameNumber': str(game_num_val).strip(),
        'date': str(date_val).strip() if date_val else '',
        'location': str(location_val).strip() if location_val else '',
        'transportation': float(transport_val) if transport_val and transport_val != '' else 0.0,
        'food': float(food_val) if food_val and food_val != '' else 0.0,
        'gamePayment': float(payment_val) if payment_val and payment_val != '' else 0.0,
        'paidStatus': str(paid_status_val).strip() if paid_status_val else '',
        'paymentDate': str(payment_date_val).strip() if payment_date_val else None,
        'observations': str(observations_val).strip() if observations_val else None
    }

    all_games.append(game)

    # Show first few and last few
    if len(all_games) <= 3 or len(all_games) > len(list(range(4, 61))) - 3:
        print(f"Game {game['gameNumber']:5s}: {game['date']} - {game['location'][:30]}")

print(f"...\n")
print(f"Total games read from Excel: {len(all_games)}")

# Check for game 1416
has_1416 = any(g['gameNumber'] == '1416' for g in all_games)
print(f"Game 1416 included: {has_1416}")

# Save to JSON
json_path = Path("data/all_games.json")
print(f"\nSaving to {json_path}...")

with open(json_path, 'w', encoding='utf-8') as f:
    json.dump(all_games, f, indent=2, ensure_ascii=False)

print(f"Saved {len(all_games)} games")

# Verify
from collections import Counter
game_nums = [g['gameNumber'] for g in all_games]
counter = Counter(game_nums)
duplicates = {k: v for k, v in counter.items() if v > 1}

print(f"\nVerification:")
print(f"  Total games: {len(all_games)}")
print(f"  Game 1416 present: {has_1416}")
print(f"  Duplicates: {duplicates if duplicates else 'None'}")

print("\n" + "=" * 100)
if len(all_games) == 57 and has_1416 and not duplicates:
    print("SUCCESS! All 57 games restored including game 1416")
    print(f"Game numbers: {sorted(game_nums)}")
else:
    print(f"Check: {len(all_games)} games, 1416={has_1416}, dups={bool(duplicates)}")
print("=" * 100)
