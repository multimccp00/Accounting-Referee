"""
Quiz engine and test session management.

Manages quiz sessions, records question attempts, and persists test history
to local JSON storage.
"""
import json
import os
import uuid
from datetime import datetime
from typing import Any, Dict, List

from config.settings import TEST_DATA_DIR
from app.models.question import QuestionAttempt


class QuizEngine:
    """Manages quiz sessions and test attempt recording.

    Persists all test sessions and attempts to local JSON files in TEST_DATA_DIR.
    Allows retrieval of session history for analysis and reporting.

    Attributes:
        current_session: Active session data, or None if no session in progress.
        session_history_file: Path to the persistent session history JSON file.
    """
    def __init__(self):
        """Initialize the quiz engine."""
        os.makedirs(TEST_DATA_DIR, exist_ok=True)
        self.current_session = None
        self.session_history_file = os.path.join(TEST_DATA_DIR, 'session_history.json')

    def start_session(self, mode: str, rule_category: str = "", total_questions: int = 30) -> str:
        """Start a new test session.

        Args:
            mode: Quiz mode (e.g., 'random', 'by_rule', 'unanswered', 'wrong_answers').
            rule_category: Optional rule category to focus on.
            total_questions: Number of questions in the session.

        Returns:
            Unique session ID.
        """
        session_id = str(uuid.uuid4())
        self.current_session = {
            'session_id': session_id,
            'timestamp': datetime.now().isoformat(),
            'mode': mode,
            'rule_category': rule_category,
            'total_questions': total_questions,
            'questions_answered': 0,
            'correct_count': 0,
            'duration_seconds': 0.0,
            'attempts': []
        }
        return session_id

    def record_attempt(self, question_id: str, user_answer: str, correct_answer: str,
                      is_correct: bool, reasoning: str = "", notes: str = ""):
        """Record a single question attempt in the current session.

        Args:
            question_id: ID of the question answered.
            user_answer: What the user answered.
            correct_answer: The correct answer.
            is_correct: Whether the answer was correct.
            reasoning: Optional explanation of the answer.
            notes: Optional user notes.
        """
        if not self.current_session:
            return

        attempt = {
            'question_id': question_id,
            'user_answer': user_answer,
            'correct_answer': correct_answer,
            'is_correct': is_correct,
            'timestamp': datetime.now().isoformat(),
            'attempt_number': len(self.current_session['attempts']) + 1,
            'reasoning': reasoning,
            'notes': notes
        }
        self.current_session['attempts'].append(attempt)
        self.current_session['questions_answered'] += 1
        if is_correct:
            self.current_session['correct_count'] += 1

    def end_session(self) -> Dict[str, Any]:
        """End the current session and persist it to history.

        Returns:
            The session data that was saved.
        """
        if not self.current_session:
            return {}

        session_data = self.current_session.copy()
        self._save_session(session_data)
        self.current_session = None
        return session_data

    def _save_session(self, session: Dict[str, Any]):
        """Persist session to local storage."""
        try:
            history = self._load_history()
            history.append(session)
            with open(self.session_history_file, 'w', encoding='utf-8') as f:
                json.dump(history, f, indent=2)
        except Exception as e:
            print(f"Warning: could not save session: {e}")

    def _load_history(self) -> List[Dict[str, Any]]:
        """Load all previous sessions."""
        try:
            if os.path.exists(self.session_history_file):
                with open(self.session_history_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    return data if isinstance(data, list) else []
        except Exception:
            pass
        return []

    def get_session_history(self) -> List[Dict[str, Any]]:
        """Retrieve all recorded test sessions.

        Returns:
            List of all session records.
        """
        return self._load_history()

    def get_session_by_id(self, session_id: str) -> Dict[str, Any]:
        """Retrieve a specific test session by ID.

        Args:
            session_id: ID of the session to retrieve.

        Returns:
            Session data if found, otherwise empty dictionary.
        """
        for session in self.get_session_history():
            if session.get('session_id') == session_id:
                return session
        return {}
