#!/usr/bin/env python
"""Show every single row in Excel to see all games."""
import sys
from pathlib import Path
from datetime import datetime

try:
    import openpyxl
except:
    import subprocess
    subprocess.check_call([sys.executable, "-m", "pip", "install", "openpyxl", "-q"])
    import openpyxl

excel_path = Path("games.xlsx")
wb = openpyxl.load_workbook(excel_path)
ws = wb.active

print("ALL ROWS IN EXCEL:")
print("=" * 100)

for row_idx, row in enumerate(ws.iter_rows(max_row=70, values_only=True)):
    # Show all non-empty rows
    if any(v for v in row):
        row_num = row_idx + 1
        game_num = row[1] if len(row) > 1 else ''
        date_val = row[0] if len(row) > 0 else ''
        location = row[2] if len(row) > 2 else ''

        if isinstance(date_val, datetime):
            date_val = date_val.strftime('%Y-%m-%d')

        print(f"Row {row_num:2d}: {str(game_num):10s} | {str(date_val):15s} | {str(location)[:40]}")

print("\n" + "=" * 100)
