#!/usr/bin/env python
"""
Test script demonstrating rulebook improvements.

Run this to see:
1. Intelligent search ranking
2. Difficulty tagging
3. Keyword extraction
4. Relevance scoring
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from app.rulebook.search import search_rulebook, extract_keywords


def print_section(title):
    """Print a formatted section header."""
    print(f"\n{'=' * 70}")
    print(f"  {title}")
    print(f"{'=' * 70}\n")


def main():
    # Load dataset
    dataset_path = Path(__file__).parent / "data" / "handball_content.json"
    if not dataset_path.exists():
        print("Error: handball_content.json not found")
        return 1

    with open(dataset_path, 'r', encoding='utf-8') as f:
        dataset = json.load(f)

    print_section("RULEBOOK IMPROVEMENTS DEMONSTRATION")

    # 1. Show difficulty distribution
    print("1. RULE DIFFICULTY DISTRIBUTION")
    print("-" * 70)

    hard_rules = [r for r in dataset['rulebook'] if r.get('difficulty') == 'Hard']
    medium_rules = [r for r in dataset['rulebook'] if r.get('difficulty') == 'Medium']
    easy_rules = [r for r in dataset['rulebook'] if r.get('difficulty') == 'Easy']
    untested_rules = [r for r in dataset['rulebook'] if r.get('difficulty') == 'Untested']

    print(f"Hard rules (6+ questions):      {len(hard_rules):2d}  {hard_rules[0]['section_id'] if hard_rules else 'None'} - {hard_rules[0]['title'] if hard_rules else ''}")
    print(f"Medium rules (3-5 questions):   {len(medium_rules):2d}  {medium_rules[0]['section_id'] if medium_rules else 'None'} - {medium_rules[0]['title'] if medium_rules else ''}")
    print(f"Easy rules (1-2 questions):     {len(easy_rules):2d}")
    print(f"Untested rules (0 questions):   {len(untested_rules):2d}  {untested_rules[0]['section_id'] if untested_rules else 'None'} - {untested_rules[0]['title'] if untested_rules else ''}")

    # 2. Show intelligent search ranking
    print_section("2. INTELLIGENT SEARCH RANKING")
    print("Query: 'substitute' - Results ranked by relevance")
    print("-" * 70)

    results = search_rulebook(dataset, "substitute")
    for i, result in enumerate(results[:3], 1):
        score = result.get('_relevance_score', 0)
        difficulty = result.get('difficulty', 'Unknown')
        question_count = result.get('question_count', 0)
        print(f"\n{i}. [{difficulty}] {result['section_id']} - {result['title']}")
        print(f"   Questions: {question_count} | Relevance Score: {score:.1f}")
        keywords = result.get('_keywords', [])
        if keywords:
            print(f"   Keywords: {', '.join(keywords[:3])}")

    # 3. Show keyword extraction
    print_section("3. KEYWORD EXTRACTION")
    print("Keywords automatically extracted from each rule:")
    print("-" * 70)

    for rule in dataset['rulebook'][:5]:
        keywords = extract_keywords(rule.get('content', ''))
        if keywords:
            print(f"\n{rule['section_id']} - {rule['title'][:50]}...")
            print(f"   Keywords: {', '.join(keywords[:5])}")

    # 4. Show metadata on important rules
    print_section("4. RULE METADATA: TOP 3 TESTED RULES")
    print("Most heavily tested rules (highest question count)")
    print("-" * 70)

    sorted_rules = sorted(dataset['rulebook'], key=lambda r: r.get('question_count', 0), reverse=True)
    for rule in sorted_rules[:3]:
        difficulty = rule.get('difficulty')
        question_count = rule.get('question_count', 0)
        print(f"\n{rule['section_id']} - {rule['title']}")
        print(f"   Difficulty: {difficulty} | Test Questions: {question_count}")

        # Find percentage of all questions that reference this rule
        total_questions = len(dataset.get('questions', []))
        percentage = (question_count / total_questions * 100) if total_questions > 0 else 0
        print(f"   Coverage: {percentage:.1f}% of all test questions")

    # 5. Show search quality improvement
    print_section("5. SEARCH QUALITY: BEFORE vs AFTER")
    print("-" * 70)

    print("\nBEFORE (substring matching only):")
    print("  - 'goal' would return all rules containing the word 'goal'")
    print("  - No ranking: all results equally important")
    print("  - No difficulty info: hard to know which rules matter")
    print("  - No context: unclear what each rule covers")

    print("\nAFTER (intelligent ranking with metadata):")
    goal_results = search_rulebook(dataset, "goal")
    print(f"  - 'goal' returns {len(goal_results)} results, ranked by relevance")
    print(f"  - Top result: {goal_results[0]['section_id']} - {goal_results[0]['title']}")
    print(f"    Difficulty: {goal_results[0]['difficulty']} ({goal_results[0]['question_count']} questions)")
    print(f"    Keywords: {', '.join(goal_results[0].get('_keywords', [])[:3])}")

    print("\n" + "=" * 70)
    print("  All improvements are live in the app!")
    print("=" * 70 + "\n")

    return 0


if __name__ == "__main__":
    sys.exit(main())
