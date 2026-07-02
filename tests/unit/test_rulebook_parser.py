from app.rulebook.parser import (
    parse_answers_text,
    parse_questions_text,
    parse_rulebook_text,
)
from app.rulebook.content import (
    audit_dataset,
    merge_questions_and_answers,
)
from app.rulebook.search import search_rulebook


def test_parse_questions_text_with_options():
    text = (
        "1) What should a referee do after a timeout?\n"
        "A) Restart with throw-off\n"
        "B) Restart with free throw\n"
        "2) Which signal means passive play?\n"
        "A) One arm up\n"
        "B) Two arms up\n"
    )

    questions = parse_questions_text(text)
    assert len(questions) == 2
    assert questions[0].question_id == "1"
    assert "timeout" in questions[0].question.lower()
    assert questions[0].options[0]["key"] == "A"
    assert "free throw" in questions[0].options[1]["text"].lower()


def test_parse_questions_supports_options_beyond_d():
    text = (
        "2.4) Which statements are correct?\n"
        "a) one\n"
        "b) two\n"
        "c) three\n"
        "d) four\n"
        "e) five\n"
        "f) six\n"
    )
    questions = parse_questions_text(text)
    assert len(questions) == 1
    assert [opt["key"] for opt in questions[0].options] == ["A", "B", "C", "D", "E", "F"]


def test_parse_questions_merges_page_break_artifacts():
    text = (
        "2.29) WHITE 7 passes the ball and is fouled.\n"
        "5) Continuation after page break. Correct decision?\n"
        "a) Option one\n"
        "b) Option two\n"
        "c) Option three\n"
    )
    questions = parse_questions_text(text)
    assert len(questions) == 1
    assert questions[0].question_id == "2.29"
    assert "continuation" in questions[0].question.lower()
    assert [opt["key"] for opt in questions[0].options] == ["A", "B", "C"]


def test_parse_questions_text_with_dotted_ids():
    text = (
        "1.1) What is the court size?\n"
        "a) 40x20\n"
        "b) 42x20\n"
        "1.2) How high is the goal?\n"
        "a) 2m\n"
        "b) 3m\n"
    )
    questions = parse_questions_text(text)
    assert len(questions) == 2
    assert questions[0].question_id == "1.1"
    assert questions[1].question_id == "1.2"


def test_parse_answers_text_with_reasoning():
    text = (
        "1) Correct answer: B\n"
        "Because play resumes with a free throw from the correct position.\n"
        "2) Answer: A\n"
        "Passive play warning is shown with one arm raised.\n"
    )

    answers = parse_answers_text(text)
    assert answers["1"].answer == "B"
    assert "free throw" in answers["1"].reasoning.lower()
    assert answers["2"].answer == "A"


def test_parse_answers_text_compact_table_style():
    text = (
        "1.1) a 1:1\n"
        "1.2) b, d 2:7, 12:1\n"
    )
    answers = parse_answers_text(text)
    assert answers["1.1"].answer == "A"
    assert answers["1.1"].reasoning == "1:1"
    assert answers["1.2"].answer == "B, D"
    assert "2:7" in answers["1.2"].reasoning


def test_parse_sar_style_question_and_answer_ids():
    q_text = (
        "SAR1) What is the distance between line and bench?\n"
        "a) 1 metre\n"
        "b) 2 metres\n"
        "c) 3 metres\n"
        "d) 3.5 metres\n"
    )
    a_text = "SAR1) d Substitution Area Regulations 1\n"

    questions = parse_questions_text(q_text)
    answers = parse_answers_text(a_text)
    merged = merge_questions_and_answers(questions, answers)

    assert questions[0].question_id == "SAR1"
    assert merged[0]["id"] == "SAR1"
    assert merged[0]["correct_options"] == ["D"]


def test_merge_questions_and_answers():
    question_text = "1) Is this a legal throw?\nA) Yes\nB) No\n"
    answer_text = "1) Answer: B\nFoot position is illegal.\n"

    questions = parse_questions_text(question_text)
    answers = parse_answers_text(answer_text)
    merged = merge_questions_and_answers(questions, answers)

    assert len(merged) == 1
    assert merged[0]["id"] == "1"
    assert merged[0]["answer"] == "B"
    assert merged[0]["correct_options"] == ["B"]
    assert "illegal" in merged[0]["reasoning"].lower()


def test_parse_rulebook_sections_and_search():
    text = (
        "Rule 7 Playing the ball\n"
        "It is permitted to use hands, arms, head, torso, thighs and knees.\n"
        "Rule 8 Fouls and unsportsmanlike conduct\n"
        "A foul is penalized with a free throw.\n"
    )

    sections = parse_rulebook_text(text)
    assert len(sections) == 2
    assert sections[0]["section_id"] == "7"
    assert "playing the ball" in sections[0]["title"].lower()

    dataset = {"rulebook": sections}
    matches = search_rulebook(dataset, "unsportsmanlike")
    assert len(matches) == 1
    assert matches[0]["section_id"] == "8"


def test_audit_dataset_flags_missing_answers():
    dataset = {
        "questions": [
            {
                "id": "1.1",
                "correct_options": ["A"],
                "invalid_answer_keys": [],
                "rule_references": ["1:1"],
            },
            {
                "id": "1.2",
                "correct_options": [],
                "invalid_answer_keys": [],
                "rule_references": ["9:1"],
            },
        ],
        "rulebook": [
            {"section_id": "1", "title": "Rule 1", "content": "..."},
        ],
    }

    audit = audit_dataset(dataset)
    assert audit["total_questions"] == 2
    assert audit["missing_answers"] == ["1.2"]
    assert "1.2:9:1" in audit["unresolved_rule_references"]
