#!/usr/bin/env python
"""Restore missing games from Excel to database and JSON."""
import json
import sys
from pathlib import Path
from datetime import datetime

try:
    import openpyxl
except ImportError:
    import subprocess
    subprocess.check_call([sys.executable, "-m", "pip", "install", "openpyxl", "-q"])
    import openpyxl

print("=" * 70)
print("GAME RESTORATION SCRIPT")
print("=" * 70)

# Load Excel
excel_path = Path("games.xlsx")
if not excel_path.exists():
    print("ERROR: Excel file not found")
    sys.exit(1)

print("\n1. Reading Excel file...")
wb = openpyxl.load_workbook(excel_path)
ws = wb.active

# Extract games from Excel (headers in row 3, data starts row 4)
headers = None
excel_games = []

for row_idx, row in enumerate(ws.iter_rows(min_row=3, values_only=True), start=3):
    if row_idx == 3:
        # Header row
        headers = [h for h in row if h]  # Filter None values
        print(f"Headers: {headers}")
        continue

    # Skip empty rows
    if not row[0]:
        break

    # Create game dict
    game = {}
    for col_idx, header in enumerate(headers):
        if col_idx < len(row):
            value = row[col_idx]
            # Convert date to string if it's a datetime
            if isinstance(value, datetime):
                value = value.strftime('%Y-%m-%d')
            # Handle season separately (always 2025/2026)
            if header == 'season':
                game[header] = value
            else:
                game[header] = value

    # Add missing 'season' field
    if 'season' not in game:
        game['season'] = '2025/2026'

    excel_games.append(game)

print(f"Games in Excel: {len(excel_games)}")
if excel_games:
    print(f"First game: {json.dumps(excel_games[0], indent=2)}")

# Load current JSON
print("\n2. Reading current JSON database...")
json_path = Path("data/all_games.json")

if json_path.exists():
    with open(json_path, 'r', encoding='utf-8') as f:
        current_games = json.load(f)
else:
    current_games = []

print(f"Games in JSON: {len(current_games)}")

# Find missing games
print("\n3. Identifying missing games...")

# Create set of game numbers from JSON
json_game_numbers = set()
for game in current_games:
    gn = str(game.get('gameNumber', ''))
    if gn:
        json_game_numbers.add(gn)

print(f"Game numbers in JSON: {sorted(json_game_numbers)[:10]}... ({len(json_game_numbers)} total)")

# Find games in Excel but not in JSON
missing_games = []
for game in excel_games:
    gn = str(game.get('gameNumber', ''))
    if gn not in json_game_numbers:
        missing_games.append(game)

print(f"Missing games: {len(missing_games)}")
if missing_games:
    print("\nMissing games to restore:")
    for game in missing_games:
        print(f"  - Game {game.get('gameNumber')}: {game.get('date')} - {game.get('location')}")

# Restore missing games
if missing_games:
    print("\n4. Restoring games to JSON...")

    # Add missing games
    for game in missing_games:
        current_games.append(game)

    # Sort by date
    current_games.sort(key=lambda g: (g.get('date', ''), g.get('gameNumber', '')))

    # Write back to JSON
    with open(json_path, 'w', encoding='utf-8') as f:
        json.dump(current_games, f, indent=2, ensure_ascii=False)

    print(f"Restored {len(missing_games)} games to JSON")
    print(f"Total games now: {len(current_games)}")

    # Now restore to database
    print("\n5. Restoring games to database...")

    try:
        from app.models.game_data import GameDataManager

        # Initialize manager
        manager = GameDataManager()

        # Check which games are missing from database
        try:
            existing_games = manager.get_all_games()
            existing_game_ids = set(g.get('id') or g.get('gameNumber') for g in existing_games)
        except Exception as e:
            print(f"Could not read from database: {e}")
            existing_game_ids = set()

        print(f"Games in database: {len(existing_game_ids)}")

        # Add missing games to database
        added_count = 0
        for game in missing_games:
            try:
                manager.add_game(
                    season=game.get('season', '2025/2026'),
                    gameNumber=str(game.get('gameNumber', '')),
                    date=game.get('date'),
                    location=game.get('location', ''),
                    transportation=game.get('transportation', 0),
                    food=game.get('food', 0),
                    gamePayment=game.get('gamePayment', 0),
                    paidStatus=game.get('paidStatus', ''),
                    paymentDate=game.get('paymentDate'),
                    observations=game.get('observations', '')
                )
                added_count += 1
            except Exception as e:
                print(f"Error adding game {game.get('gameNumber')}: {e}")

        print(f"Added {added_count} games to database")

    except Exception as e:
        print(f"Warning: Could not update database: {e}")
        print("Games have been restored to JSON file successfully")
else:
    print("No missing games found!")

print("\n" + "=" * 70)
print("RESTORATION COMPLETE")
print("=" * 70)
print(f"\nTotal games: {len(current_games)}")
print(f"Excel games: {len(excel_games)}")
print(f"Status: {'SYNCED' if len(current_games) == len(excel_games) else 'PARTIAL'}")
