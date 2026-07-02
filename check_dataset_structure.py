#!/usr/bin/env python
"""Check the structure of the handball content dataset."""
import json
from pathlib import Path

with open('data/handball_content.json', 'r', encoding='utf-8') as f:
    data = json.load(f)

# Check first rule structure
rule = data['rulebook'][0]
print("Rule structure:")
for key in rule.keys():
    if key != 'content':
        value = rule[key]
        if isinstance(value, str) and len(value) > 50:
            print(f"  {key}: {value[:50]}...")
        else:
            print(f"  {key}: {value}")
    else:
        content = rule[key]
        print(f"  content: {len(content)} chars - {content[:60]}...")

print(f"\nContent length: {len(rule.get('content', ''))} chars")

# Check if images exist
images = rule.get('images', [])
print(f"\nImages in first rule: {len(images)}")
if images:
    img = images[0]
    if isinstance(img, str):
        print(f"  First image is string, length: {len(img)}")
        print(f"  Preview: {img[:100]}...")
    else:
        print(f"  First image type: {type(img)}")

# Check a rule with more content
rule4 = data['rulebook'][4]
print(f"\n\nRule 4: {rule4['section_id']} - {rule4['title']}")
print(f"  Content length: {len(rule4.get('content', ''))} chars")
print(f"  Images: {len(rule4.get('images', []))}")
print(f"  Start page: {rule4.get('start_page')}")
print(f"  End page: {rule4.get('end_page')}")
