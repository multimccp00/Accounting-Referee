"""
Question and test session data models.

Defines data structures for parsed questions, answers, test attempts,
and test session metadata.
"""
from dataclasses import dataclass
from typing import Any, Dict, List


@dataclass
class ParsedQuestion:
    """A question parsed from PDF source material.

    Attributes:
        question_id: Unique identifier for the question.
        question: The question text.
        options: List of answer options, each with 'key' and 'text'.
    """
    question_id: str
    question: str
    options: List[Dict[str, str]]


@dataclass
class ParsedAnswer:
    """An answer parsed from PDF source material.

    Attributes:
        question_id: Matches the corresponding question ID.
        answer: Correct answer (e.g., 'A', 'A, B', etc.).
        reasoning: Explanation or rule references.
    """
    question_id: str
    answer: str
    reasoning: str


@dataclass
class QuestionAttempt:
    """A persisted record of one question attempt in a test session.

    Attributes:
        question_id: ID of the question answered.
        user_answer: What the user answered.
        correct_answer: The correct answer.
        is_correct: Whether the user's answer was correct.
        timestamp: When the attempt was recorded (ISO format).
        attempt_number: Sequential attempt number in the session.
        reasoning: Optional explanation of the answer.
        notes: Optional user notes for later reference.
    """
    question_id: str
    user_answer: str
    correct_answer: str
    is_correct: bool
    timestamp: str
    attempt_number: int
    reasoning: str = ""
    notes: str = ""


@dataclass
class TestSession:
    """A persisted record of a complete test session.

    Attributes:
        session_id: Unique session identifier.
        timestamp: When the session started (ISO format).
        mode: Quiz mode (e.g., 'random', 'by_rule', 'unanswered').
        rule_category: Rule category focused on, if applicable.
        total_questions: Number of questions in the session.
        questions_answered: How many questions were answered.
        correct_count: Number of correct answers.
        duration_seconds: Total session duration in seconds.
        attempts: List of attempt records from this session.
    """
    session_id: str
    timestamp: str
    mode: str
    rule_category: str
    total_questions: int
    questions_answered: int
    correct_count: int
    duration_seconds: float
    attempts: List[Dict[str, Any]]
