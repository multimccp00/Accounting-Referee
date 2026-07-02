#!/usr/bin/env python
"""Check exactly what's in row 31."""
import sys
from pathlib import Path

try:
    import openpyxl
except:
    import subprocess
    subprocess.check_call([sys.executable, "-m", "pip", "install", "openpyxl", "-q"])
    import openpyxl

excel_path = Path("games.xlsx")
wb = openpyxl.load_workbook(excel_path)
ws = wb.active

# Read row 31 cell by cell
print("ROW 31 CONTENTS:")
print("=" * 70)

row31 = ws[31]
for col_idx, cell in enumerate(row31, 1):
    col_letter = chr(64 + col_idx)  # A=65, B=66, etc
    print(f"  Column {col_letter} (#{col_idx}): {repr(cell.value)} (type: {type(cell.value).__name__})")

print("\n" + "=" * 70)
print("Extracted values:")
print(f"  Date (A31): {row31[0].value}")
print(f"  Game Number (B31): {row31[1].value}")
print(f"  Location (C31): {row31[2].value}")
print(f"  Transportation (D31): {row31[3].value}")
print(f"  Food (E31): {row31[4].value}")
print(f"  Payment (F31): {row31[5].value}")
print(f"  Paid Status (G31): {row31[6].value}")
print(f"  Payment Date (H31): {row31[7].value}")
print(f"  Observations (I31): {row31[8].value}")
