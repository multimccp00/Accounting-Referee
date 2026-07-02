#!/usr/bin/env python
"""List all games from Excel with row numbers."""
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

print("=" * 100)
print("ALL GAMES FROM EXCEL")
print("=" * 100)

headers = None
row_num = 0

for row_idx, row in enumerate(ws.iter_rows(min_row=3, values_only=True), start=3):
    if row_idx == 3:
        headers = [h for h in row if h]
        print(f"\nHeaders: {headers}\n")
        print("Row | GameNum | Date       | Location")
        print("-" * 100)
        continue

    if not row[0]:
        break

    row_num += 1
    game_num = row[1] if len(row) > 1 else ''
    date = row[0] if len(row) > 0 else ''
    location = row[2] if len(row) > 2 else ''

    # Convert date to string if needed
    if isinstance(date, datetime):
        date = date.strftime('%Y-%m-%d')

    print(f"{row_idx:3d} | {str(game_num):7s} | {str(date):10s} | {str(location)[:40]}")

print("-" * 100)
print(f"Total games: {row_num}")
