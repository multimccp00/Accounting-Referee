"""
Handball content dataset building and loading.

Combines parsed questions, answers, and rules into a unified dataset.
Handles dataset validation and persistence.
"""
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

from app.models.question import ParsedQuestion, ParsedAnswer
from app.rulebook.parser import (
    parse_questions_text, parse_answers_text, parse_rulebook_text,
    extract_rulebook_images
)
from app.utils.helpers import parse_answer_keys, extract_rule_reference_tokens
from app.utils.pdf import extract_pdf_text


def merge_questions_and_answers(
    questions: List[ParsedQuestion], answers: Dict[str, ParsedAnswer]
) -> List[Dict[str, Any]]:
    """Merge parsed questions with their answers.

    Args:
        questions: List of parsed questions.
        answers: Dictionary of answers keyed by question ID.

    Returns:
        List of merged question records with answer keys and validation flags.
    """
    merged: List[Dict[str, Any]] = []
    for q in questions:
        ans = answers.get(q.question_id)
        answer_text = ans.answer if ans else ""
        correct_options = parse_answer_keys(answer_text)
        option_keys = [opt.get("key", "") for opt in q.options]
        invalid_answer_keys = [k for k in correct_options if k not in option_keys]
        rule_refs = extract_rule_reference_tokens(ans.reasoning if ans else "")
        merged.append(
            {
                "id": q.question_id,
                "question": q.question,
                "options": q.options,
                "answer": answer_text,
                "correct_options": correct_options,
                "reasoning": ans.reasoning if ans else "",
                "rule_references": rule_refs,
                "invalid_answer_keys": invalid_answer_keys,
            }
        )
    return merged


def enrich_rules_with_metadata(rules: List[Dict[str, Any]], questions: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Enrich rule sections with metadata derived from test questions.

    Adds difficulty level and question count to each rule based on how
    frequently it appears in test questions.

    Args:
        rules: List of rule sections from the rulebook.
        questions: List of test questions with rule references.

    Returns:
        Enhanced rule sections with difficulty and question count metadata.
    """
    # Count questions referencing each rule
    rule_question_count: Dict[str, int] = {}
    for question in questions:
        for ref in question.get("rule_references", []):
            ref_str = str(ref).split(":")[0]  # Extract rule number (e.g., "1" from "1:2")
            rule_question_count[ref_str] = rule_question_count.get(ref_str, 0) + 1

    # Enrich rules with metadata
    enriched = []
    for rule in rules:
        rule_copy = rule.copy()
        section_id = str(rule_copy.get("section_id", "")).strip()
        question_count = rule_question_count.get(section_id, 0)

        # Calculate difficulty based on question frequency
        if question_count == 0:
            difficulty = "Untested"
        elif question_count <= 2:
            difficulty = "Easy"
        elif question_count <= 5:
            difficulty = "Medium"
        else:
            difficulty = "Hard"

        rule_copy["question_count"] = question_count
        rule_copy["difficulty"] = difficulty

        enriched.append(rule_copy)

    return enriched


def audit_dataset(dataset: Dict[str, Any]) -> Dict[str, Any]:
    """Validate dataset for common issues and inconsistencies.

    Checks for:
    - Duplicate question IDs
    - Questions without answers
    - Invalid answer key references
    - Rule references that don't exist

    Args:
        dataset: Complete dataset with questions and rulebook sections.

    Returns:
        Dictionary with audit results and identified issues.
    """
    questions = dataset.get("questions", [])
    rulebook = dataset.get("rulebook", [])

    ids_seen = set()
    duplicate_ids: List[str] = []
    missing_answers: List[str] = []
    invalid_key_questions: List[str] = []
    unresolved_rule_refs: List[str] = []

    available_rule_sections = {str(s.get("section_id", "")).strip() for s in rulebook}

    for q in questions:
        qid = str(q.get("id", "")).strip()
        if qid in ids_seen:
            duplicate_ids.append(qid)
        ids_seen.add(qid)

        if not q.get("correct_options"):
            missing_answers.append(qid)

        if q.get("invalid_answer_keys"):
            invalid_key_questions.append(qid)

        for ref in q.get("rule_references", []):
            token = str(ref)
            if ":" in token and token[0].isdigit():
                top_rule = token.split(":", 1)[0]
                if top_rule not in available_rule_sections:
                    unresolved_rule_refs.append(f"{qid}:{token}")

    return {
        "total_questions": len(questions),
        "duplicate_ids": sorted(list(set(duplicate_ids))),
        "missing_answers": sorted(list(set(missing_answers))),
        "questions_with_invalid_answer_keys": sorted(list(set(invalid_key_questions))),
        "unresolved_rule_references": sorted(list(set(unresolved_rule_refs))),
    }


def build_handball_dataset(
    questions_pdf: str,
    answers_pdf: str,
    rulebook_pdf: str,
    output_json: str,
    source_language: str = "pt",
) -> Dict[str, Any]:
    """Build complete handball dataset from source PDF files.

    Extracts questions, answers, and rules from PDFs, merges them,
    extracts images, and performs validation.

    Args:
        questions_pdf: Path to questions PDF.
        answers_pdf: Path to answers PDF.
        rulebook_pdf: Path to rulebook PDF.
        output_json: Path where the combined dataset will be saved.
        source_language: Language code for metadata (default: 'pt' for Portuguese).

    Returns:
        Complete dataset dictionary with metadata, questions, and rulebook.
    """
    question_text = extract_pdf_text(questions_pdf)
    answer_text = extract_pdf_text(answers_pdf)
    rulebook_text = extract_pdf_text(rulebook_pdf)

    parsed_questions = parse_questions_text(question_text)
    parsed_answers = parse_answers_text(answer_text)
    rules = parse_rulebook_text(rulebook_text)
    merged_questions = merge_questions_and_answers(parsed_questions, parsed_answers)

    # Enrich rules with metadata (difficulty, question count)
    rules = enrich_rules_with_metadata(rules, merged_questions)

    output_path = Path(output_json)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    images_output_dir = output_path.parent / "rulebook_images"
    section_images = extract_rulebook_images(
        rulebook_pdf=rulebook_pdf,
        rules=rules,
        output_dir=images_output_dir,
        relative_to=output_path.parent,
    )
    for section in rules:
        sid = str(section.get("section_id", "")).strip()
        section["images"] = section_images.get(sid, [])

    dataset = {
        "metadata": {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "source_language": source_language,
            "sources": {
                "questions_pdf": str(Path(questions_pdf).name),
                "answers_pdf": str(Path(answers_pdf).name),
                "rulebook_pdf": str(Path(rulebook_pdf).name),
            },
            "counts": {
                "questions": len(merged_questions),
                "answered_questions": sum(1 for q in merged_questions if q.get("answer")),
                "rule_sections": len(rules),
                "rulebook_images": sum(len(s.get("images", [])) for s in rules),
            },
        },
        "questions": merged_questions,
        "rulebook": rules,
    }

    dataset["integrity"] = audit_dataset(dataset)

    with output_path.open("w", encoding="utf-8") as handle:
        json.dump(dataset, handle, indent=2, ensure_ascii=False)

    return dataset


def load_handball_dataset(json_path: str) -> Dict[str, Any]:
    """Load pre-built handball dataset from JSON file.

    Args:
        json_path: Path to the dataset JSON file.

    Returns:
        Complete dataset dictionary.

    Raises:
        FileNotFoundError: If the JSON file does not exist.
        json.JSONDecodeError: If the file is not valid JSON.
    """
    with Path(json_path).open("r", encoding="utf-8") as handle:
        return json.load(handle)
