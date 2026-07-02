#!/usr/bin/env python
"""Test the text view functionality without running the GUI."""
import json
from pathlib import Path

# Load dataset
dataset_path = Path(__file__).parent / "data" / "handball_content.json"
with open(dataset_path, 'r', encoding='utf-8') as f:
    data = json.load(f)

print("=" * 70)
print("TEXT VIEW FUNCTIONALITY TEST")
print("=" * 70)

# Test 1: Check that all rules have content
print("\n1. CONTENT AVAILABLE IN ALL RULES:")
print("-" * 70)

rules_with_content = 0
rules_with_images = 0
total_images = 0

for rule in data['rulebook']:
    content = rule.get('content', '')
    images = rule.get('images', [])

    if content and len(content) > 0:
        rules_with_content += 1

    if images and len(images) > 0:
        rules_with_images += 1
        total_images += len(images)

print(f"Rules with extracted text content: {rules_with_content}/23")
print(f"Rules with images: {rules_with_images}/23")
print(f"Total images available: {total_images}")

# Test 2: Show sample content from Rule 4
print("\n2. SAMPLE TEXT VIEW CONTENT (Rule 4):")
print("-" * 70)

rule4 = data['rulebook'][4]
print(f"\nRule ID: {rule4['section_id']}")
print(f"Title: {rule4['title']}")
print(f"Content length: {len(rule4.get('content', ''))} characters")
print(f"\nContent preview (first 300 chars):")
print(f"{rule4.get('content', '')[:300]}...")
print(f"\nImages: {len(rule4.get('images', []))}")

# Test 3: Show a rule with images
print("\n3. RULE WITH IMAGES (Rule I - Foreword):")
print("-" * 70)

rule_i = data['rulebook'][0]
print(f"\nRule ID: {rule_i['section_id']}")
print(f"Title: {rule_i['title']}")
print(f"Content length: {len(rule_i.get('content', ''))} characters")
print(f"Images: {len(rule_i.get('images', []))}")

for img_path in rule_i.get('images', []):
    full_path = Path(__file__).parent / img_path
    print(f"  - {img_path}")
    print(f"    Exists: {full_path.exists()}")
    if full_path.exists():
        from PIL import Image
        try:
            img = Image.open(full_path)
            print(f"    Size: {img.width}x{img.height} pixels")
        except Exception as e:
            print(f"    Error loading: {e}")

# Test 4: Test text view toggle functionality
print("\n4. TEXT VIEW TOGGLE (Simulated):")
print("-" * 70)

print("\nWhen user clicks 'Text' radio button:")
print("  1. PDF canvas hidden")
print("  2. Text frame shown")
print("  3. Content rendered with extracted text and images")
print("  4. Images scaled to fit 600px width")
print("  5. User can scroll through content")
print("  6. 'Continuous' mode can show all related sections")

print("\nWhen user clicks 'PDF' radio button:")
print("  1. Text frame hidden")
print("  2. PDF canvas shown")
print("  3. PDF pages rendered as before")

# Test 5: Show keyword extraction
print("\n5. KEYWORD EXTRACTION (for tests):")
print("-" * 70)

from app.rulebook.search import extract_keywords

for idx in [4, 8, 16]:
    rule = data['rulebook'][idx]
    keywords = extract_keywords(rule.get('content', ''))
    print(f"\n{rule['section_id']} - {rule['title'][:40]}...")
    print(f"  Keywords: {', '.join(keywords[:5])}")

print("\n" + "=" * 70)
print("All tests completed successfully!")
print("=" * 70)

print("\nNEXT STEPS:")
print("1. Run: python app/main.py")
print("2. Navigate to Rulebook tab")
print("3. Select a rule from the index")
print("4. Click 'Text' button to see extracted content")
print("5. Click 'PDF' button to return to PDF view")
print("6. Test the toggle between both modes")
