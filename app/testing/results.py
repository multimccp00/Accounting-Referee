"""
Test results and progress tracking.

Manages persistent storage of test progress, including answered questions,
correct answers, and performance statistics.
"""
import json
import os
from typing import Any, Dict, List

from config.settings import TEST_DATA_DIR


class TestResults:
    """Manages test progress and historical results.

    Persists test progress (answered questions, correct answers, wrong answers)
    to a local JSON file for retrieval across sessions.

    Attributes:
        progress_file: Path to the persistent progress JSON file.
    """
    """Manage test session results and progress."""

    def __init__(self):
        """Initialize test results tracker."""
        os.makedirs(TEST_DATA_DIR, exist_ok=True)
        self.progress_file = os.path.join(TEST_DATA_DIR, 'test_progress.json')

    def load_progress(self) -> Dict[str, Any]:
        """Load test progress from persistent storage.

        Returns:
            Dictionary with 'answered', 'correct', 'wrong_answers' lists.
        """
        try:
            if os.path.exists(self.progress_file):
                with open(self.progress_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
        except Exception:
            pass
        return {
            'answered': [],
            'correct': [],
            'wrong_answers': [],
            'question_history': []
        }

    def save_progress(self, progress: Dict[str, Any]):
        """Save test progress to persistent storage.

        Args:
            progress: Progress dictionary with question IDs and status.
        """
        try:
            with open(self.progress_file, 'w', encoding='utf-8') as f:
                json.dump(progress, f, indent=2)
        except Exception as e:
            print(f"Warning: could not save progress: {e}")

    def record_answer(self, question_id: str, is_correct: bool, answer: str = ""):
        """Record that a question was answered.

        Args:
            question_id: ID of the question.
            is_correct: Whether the answer was correct.
            answer: Optional user's answer text.
        """
        progress = self.load_progress()
        if question_id not in progress['answered']:
            progress['answered'].append(question_id)
        if is_correct and question_id not in progress['correct']:
            progress['correct'].append(question_id)
        elif not is_correct and question_id not in progress['wrong_answers']:
            progress['wrong_answers'].append(question_id)
        self.save_progress(progress)

    def get_statistics(self) -> Dict[str, Any]:
        """Get overall test statistics from progress.

        Returns:
            Dictionary with 'total_answered', 'correct', 'wrong', 'success_rate'.
        """
        progress = self.load_progress()
        total_answered = len(progress['answered'])
        correct = len(progress['correct'])
        return {
            'total_answered': total_answered,
            'correct': correct,
            'wrong': total_answered - correct,
            'success_rate': (correct / total_answered * 100) if total_answered > 0 else 0
        }
