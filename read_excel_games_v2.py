#!/usr/bin/env python
"""Read games from Excel file and compare with database/JSON."""
import json
import sys
from pathlib import Path

try:
    import openpyxl
except ImportError:
    print("Installing openpyxl...")
    import subprocess
    subprocess.check_call([sys.executable, "-m", "pip", "install", "openpyxl", "-q"])
    import openpyxl

# Load Excel
excel_path = Path("games.xlsx")
if not excel_path.exists():
    print("Excel file not found")
    sys.exit(1)

print("Reading Excel file...")
wb = openpyxl.load_workbook(excel_path)
ws = wb.active

print(f"Sheet name: {ws.title}")
print(f"Dimensions: {ws.dimensions}")

# Get all values
print("\nFirst 10 rows:")
for idx, row in enumerate(ws.iter_rows(min_row=1, max_row=10, values_only=True)):
    print(f"  Row {idx+1}: {row}")

# Find where headers actually are
print("\nLooking for game data...")
for row_idx, row in enumerate(ws.iter_rows(min_row=1, values_only=True), 1):
    # Check if row has multiple non-empty values that look like headers
    non_empty = [v for v in row if v]
    if len(non_empty) > 3 and row_idx < 10:
        print(f"Potential header row {row_idx}: {row}")

# Current games count
print("\n" + "=" * 70)
print("Checking current database...")

json_path = Path("data/all_games.json")
if json_path.exists():
    with open(json_path, 'r', encoding='utf-8') as f:
        current_data = json.load(f)

    # Handle both list and dict structures
    if isinstance(current_data, list):
        current_games = current_data
    else:
        current_games = current_data.get('games', [])

    print(f"Games in JSON: {len(current_games)}")
    if current_games:
        print(f"First game structure: {json.dumps(current_games[0], indent=2)}")
else:
    print("JSON file not found")
    current_games = []

print(f"\nTotal games needed: Check manually based on Excel content")
