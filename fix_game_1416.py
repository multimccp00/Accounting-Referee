#!/usr/bin/env python
"""Fix the duplicate game 1417 - change row 31 to 1416."""
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

print("=" * 70)
print("FIX DUPLICATE GAME 1417")
print("=" * 70)

# Load Excel
excel_path = Path("games.xlsx")
wb = openpyxl.load_workbook(excel_path)
ws = wb.active

print("\n1. Finding duplicate game 1417 in Excel...")
row_to_fix = None

for row_idx, row in enumerate(ws.iter_rows(min_row=4, max_row=100), start=4):
    game_num = row[1].value  # Column B = gameNumber
    date = row[0].value       # Column A = date
    location = row[2].value   # Column C = location

    # Convert date to string if needed
    if isinstance(date, datetime):
        date = date.strftime('%Y-%m-%d')

    if str(game_num) == '1417' and '2026-01-24' in str(date):
        print(f"Found duplicate 1417 at row {row_idx}:")
        print(f"  Date: {date}")
        print(f"  Location: {location}")
        row_to_fix = row_idx
        break

if row_to_fix:
    print(f"\n2. Fixing row {row_to_fix}: changing game number to 1416...")
    ws.cell(row=row_to_fix, column=2).value = '1416'  # Column B = gameNumber

    # Save Excel
    wb.save(excel_path)
    print("[OK] Excel file updated")

    # Now update JSON
    print("\n3. Updating JSON file...")
    json_path = Path("data/all_games.json")

    with open(json_path, 'r', encoding='utf-8') as f:
        games = json.load(f)

    # Find and update/add game 1416
    found_1416 = False
    for game in games:
        if str(game.get('gameNumber')) == '1417' and game.get('date') == '2026-01-24':
            print(f"Found game 1417 (2026-01-24) in JSON, changing to 1416...")
            game['gameNumber'] = '1416'
            found_1416 = True
            break

    if found_1416:
        # Save JSON
        with open(json_path, 'w', encoding='utf-8') as f:
            json.dump(games, f, indent=2, ensure_ascii=False)
        print("[OK] JSON file updated")
    else:
        print("[WARNING] Did not find matching game in JSON")

    # Verify
    print("\n4. Verifying fix...")
    from collections import Counter
    game_numbers = [str(g.get('gameNumber')) for g in games]
    counter = Counter(game_numbers)
    duplicates = {k: v for k, v in counter.items() if v > 1}

    if duplicates:
        print(f"[ERROR] Still have duplicates: {duplicates}")
    else:
        print("[OK] No duplicates! All game numbers are unique")
        print(f"[OK] Total games: {len(games)}")

        # Verify Excel matches JSON
        from datetime import datetime
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

            if game.get('gameNumber'):
                excel_games.append(game)

        excel_nums = set(str(g.get('gameNumber')) for g in excel_games)
        json_nums = set(str(g.get('gameNumber')) for g in games)

        if excel_nums == json_nums:
            print("[OK] Excel and JSON game numbers match!")
        else:
            missing = excel_nums - json_nums
            extra = json_nums - excel_nums
            if missing or extra:
                print(f"[WARNING] Mismatch - missing: {missing}, extra: {extra}")

else:
    print("[ERROR] Could not find the duplicate game to fix")

print("\n" + "=" * 70)
