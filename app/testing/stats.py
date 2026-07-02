"""
Test statistics and analytics.

Provides aggregated statistics across test sessions and rule categories.
"""
from typing import Any, Dict, List

from app.testing.results import TestResults


def get_overall_stats() -> Dict[str, Any]:
    """Get overall test statistics across all sessions.

    Returns:
        Dictionary with overall performance metrics.
    """
    results = TestResults()
    stats = results.get_statistics()
    return stats


def get_stats_by_category(sessions: List[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    """Calculate statistics grouped by rule category.

    Args:
        sessions: List of test session records.

    Returns:
        Dictionary mapping category names to statistics.
    """
    stats_by_cat: Dict[str, Dict[str, Any]] = {}
    for session in sessions:
        category = session.get('rule_category', 'Uncategorized')
        if category not in stats_by_cat:
            stats_by_cat[category] = {
                'sessions': 0,
                'correct': 0,
                'total': 0,
                'avg_duration': 0.0
            }
        stats_by_cat[category]['sessions'] += 1
        correct = session.get('correct_count', 0)
        total = session.get('questions_answered', 0)
        stats_by_cat[category]['correct'] += correct
        stats_by_cat[category]['total'] += total

    for cat in stats_by_cat:
        if stats_by_cat[cat]['total'] > 0:
            stats_by_cat[cat]['success_rate'] = stats_by_cat[cat]['correct'] / stats_by_cat[cat]['total'] * 100
        else:
            stats_by_cat[cat]['success_rate'] = 0

    return stats_by_cat
