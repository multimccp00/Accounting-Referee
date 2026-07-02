"""
Question filtering and retrieval utilities.

Provides functions to filter and retrieve questions based on categories
and test progress history.
"""
from typing import Any, Dict, List


def filter_questions_by_category(questions: List[Dict[str, Any]], category: str) -> List[Dict[str, Any]]:
    """Filter questions by rule category.

    Args:
        questions: List of question records.
        category: Rule category to filter by (e.g., '1', '2:7').
                  'all' or empty string returns all questions.

    Returns:
        Questions matching the specified category.
    """
    if not category or category.lower() == 'all':
        return questions

    filtered = []
    for q in questions:
        rule_refs = q.get('rule_references', [])
        if any(category in str(ref) for ref in rule_refs):
            filtered.append(q)
    return filtered


def get_unanswered_questions(progress: Dict[str, Any], questions: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Get questions that haven't been answered in any session.

    Args:
        progress: Test progress dictionary with 'answered' key.
        questions: List of all available questions.

    Returns:
        Questions not yet answered.
    """
    answered_ids = set(progress.get('answered', []))
    return [q for q in questions if q.get('id') not in answered_ids]


def get_wrong_answer_questions(progress: Dict[str, Any], questions: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Get questions that were answered incorrectly.

    Args:
        progress: Test progress dictionary with 'wrong_answers' key.
        questions: List of all available questions.

    Returns:
        Questions answered incorrectly in past sessions.
    """
    wrong_ids = set(progress.get('wrong_answers', []))
    return [q for q in questions if q.get('id') in wrong_ids]
