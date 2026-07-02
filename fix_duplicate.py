#!/usr/bin/env python
"""Identify and fix the duplicate game number."""
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

# Load JSON for comparison
json_path = Path("data/all_games.json")
with open(json_path, 'r', encoding='utf-8') as f:
    json_games = json.load(f)

print("=" * 70)
print("DUPLICATE GAME FIX")
print("=" * 70)

# Find the duplicate games in Excel
print("\nDuplicate game 1417 occurrences in Excel:")
print("\n1. 2026-03-01 - GIC GUEDA (row 10 estimated)")
print("2. 2026-01-24 - MUN. PAMPILHOSA (row 9 estimated)")

# Check which one is in JSON
json_1417_games = [g for g in json_games if str(g.get('gameNumber')) == '1417']
print(f"\nGame 1417 in JSON: {len(json_1417_games)} occurrences")
for game in json_1417_games:
    print(f"  - {game.get('date')} - {game.get('location')}")

# Look for the correct game number for the second occurrence
# Check what game numbers are missing or what could be the right number
print("\nAnalyzing game numbers...")

# Find all game numbers in JSON
json_nums = set(str(g.get('gameNumber')) for g in json_games if g.get('gameNumber'))

# Look at what game number the second occurrence should be
# Check if there's a missing number near 1417
import itertools
all_nums = list(range(1410, 1425))
missing = [str(n) for n in all_nums if str(n) not in json_nums]
print(f"Missing game numbers in range 1410-1425: {missing}")

# The second 1417 entry (2026-01-24) might be 1416 or 1418
print("\nPossible corrections:")
print("- Game 1417 (2026-03-01 - GIC GUEDA) - keep as is")
print("- Game 1417 (2026-01-24 - MUN. PAMPILHOSA) - should be:")

# Look at the other numbers to see what makes sense
for potential in [1416, 1418, 1419, 1421]:
    if str(potential) not in json_nums:
        print(f"  - {potential} (available)")

print("\nManual inspection needed:")
print("Please check the Excel file to determine the correct game number for:")
print("  2026-01-24 - MUN. PAMPILHOSA")
print("\nLikely candidates based on adjacent numbers:")
print("  - 1416 (before 1417)")
print("  - 1418 (after 1417)")
print("  - Check the sequence in the spreadsheet to determine which is correct")
