#!/usr/bin/env python
"""Add game 1416 to JSON."""
import json
from pathlib import Path

json_path = Path("data/all_games.json")

# Load
with open(json_path, 'r', encoding='utf-8') as f:
    games = json.load(f)

# Check if 1416 exists
has_1416 = any(str(g.get('gameNumber')) == '1416' for g in games)

if has_1416:
    print("Game 1416 already exists in JSON")
else:
    print("Game 1416 not found, adding it...")

    # Create game 1416
    game_1416 = {
        "season": "2025/2026",
        "gameNumber": "1416",
        "date": "2026-01-24",
        "location": "MUN. PAMPILHOSA",
        "transportation": 80.0,
        "food": 20.0,
        "gamePayment": 35.0,
        "paidStatus": "No",
        "paymentDate": None,
        "observations": None
    }

    # Add it
    games.append(game_1416)

    # Sort by gameNumber (as integers where possible)
    def sort_key(game):
        try:
            return int(game.get('gameNumber', '0'))
        except ValueError:
            return 0

    games.sort(key=sort_key)

    # Save
    with open(json_path, 'w', encoding='utf-8') as f:
        json.dump(games, f, indent=2, ensure_ascii=False)

    print(f"Added game 1416")
    print(f"Total games now: {len(games)}")

    # Verify
    has_1416 = any(str(g.get('gameNumber')) == '1416' for g in games)
    print(f"Verification: {'OK' if has_1416 else 'FAILED'}")
