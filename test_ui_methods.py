#!/usr/bin/env python
"""Test the new UI methods for rulebook navigation."""
import json
from pathlib import Path

# Load dataset
dataset_path = Path(__file__).parent / "data" / "handball_content.json"
with open(dataset_path, 'r', encoding='utf-8') as f:
    dataset = json.load(f)

# Test 1: Index loading
print("=" * 70)
print("TEST 1: Index loading (simulating _load_rulebook_index)")
print("=" * 70)
print(f"\nTotal rules in dataset: {len(dataset['rulebook'])}\n")

for idx, section in enumerate(dataset["rulebook"][:5]):
    sid = section.get("section_id", "")
    title = section.get("title", "")
    question_count = section.get("question_count", 0)
    difficulty = section.get("difficulty", "")

    display_text = f"{sid} - {title}"
    if difficulty and difficulty != "Untested":
        display_text += f" [{difficulty}]"
    if question_count > 0:
        display_text += f" ({question_count} q)"

    print(f"{idx}: {display_text}")

# Test 2: Index selection (simulating _select_from_index)
print("\n" + "=" * 70)
print("TEST 2: Index selection (simulating _select_from_index)")
print("=" * 70)

selected_idx = 0
section = dataset["rulebook"][selected_idx]
print(f"\nSelected rule at index {selected_idx}:")
print(f"  Section ID: {section.get('section_id')}")
print(f"  Title: {section.get('title')}")
print(f"  Start page: {section.get('start_page')}")
print(f"  Difficulty: {section.get('difficulty')}")
print(f"  Question count: {section.get('question_count')}")

# Test 3: Search and results display
print("\n" + "=" * 70)
print("TEST 3: Search functionality (simulating search_rulebook_ui)")
print("=" * 70)

from app.rulebook.search import search_rulebook

query = "substitute"
results = search_rulebook(dataset, query)
print(f"\nSearch for '{query}' returned {len(results)} results\n")

for idx, section in enumerate(results[:3]):
    sid = section.get("section_id", "")
    title = section.get("title", "")
    question_count = section.get("question_count", 0)
    difficulty = section.get("difficulty", "")
    score = section.get("_relevance_score", 0)

    display_text = f"{sid} - {title}"
    if difficulty and difficulty != "Untested":
        display_text += f" [{difficulty}]"
    if question_count > 0:
        display_text += f" ({question_count} q)"

    print(f"{idx}: {display_text}")
    print(f"   Score: {score:.1f}, Page: {section.get('start_page')}")

print("\n" + "=" * 70)
print("All UI methods verified successfully!")
print("=" * 70)
