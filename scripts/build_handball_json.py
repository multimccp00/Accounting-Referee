import argparse
import sys
from pathlib import Path


def _ensure_repo_on_path() -> None:
    root = Path(__file__).resolve().parent.parent
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Build app-ready handball quiz/rulebook JSON from source PDFs"
    )
    parser.add_argument("--questions", required=True, help="Path to questions PDF")
    parser.add_argument("--answers", required=True, help="Path to answers PDF")
    parser.add_argument("--rulebook", required=True, help="Path to rulebook PDF")
    parser.add_argument(
        "--output",
        default="data/handball_content.json",
        help="Output JSON file path (default: data/handball_content.json)",
    )
    parser.add_argument(
        "--language",
        default="pt",
        help="Source language code used in metadata (default: pt)",
    )

    args = parser.parse_args()
    _ensure_repo_on_path()

    from app.rulebook.content import build_handball_dataset

    dataset = build_handball_dataset(
        questions_pdf=args.questions,
        answers_pdf=args.answers,
        rulebook_pdf=args.rulebook,
        output_json=args.output,
        source_language=args.language,
    )

    counts = dataset.get("metadata", {}).get("counts", {})
    integrity = dataset.get("integrity", {})
    print("Built handball dataset successfully")
    print(f"- Output: {args.output}")
    print(f"- Questions: {counts.get('questions', 0)}")
    print(f"- Answered questions: {counts.get('answered_questions', 0)}")
    print(f"- Rule sections: {counts.get('rule_sections', 0)}")
    print(f"- Missing answers: {len(integrity.get('missing_answers', []))}")
    print(
        f"- Questions with invalid answer keys: "
        f"{len(integrity.get('questions_with_invalid_answer_keys', []))}"
    )
    print(
        f"- Unresolved rule references: "
        f"{len(integrity.get('unresolved_rule_references', []))}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
