"""Tests for DrillAI Question Solver and Response Validation."""

from unittest.mock import MagicMock
import pytest

from solver import QuestionSolver, SolverResult, validate_response


def test_validate_response_valid_multiple_choice():
    """Verify validation of a well-formed multiple choice response."""
    data = {
        "question_detected": True,
        "question_text": "Berapakah hasil dari 15 x 12?",
        "question_type": "mathematics",
        "options": {
            "A": "160",
            "B": "180",
            "C": "200",
            "D": "220",
        },
        "proposed_answer": "B",
        "answer_text": "180",
        "explanation": "15 dikali 12 sama dengan 180.",
        "confidence": 0.95,
        "needs_review": False,
        "warnings": [],
    }
    is_valid, errors, cleaned = validate_response(data)
    assert is_valid is True
    assert len(errors) == 0
    assert cleaned["proposed_answer"] == "B"
    assert cleaned["confidence"] == 0.95


def test_validate_response_no_question():
    """Verify validation when no question is detected."""
    data = {
        "question_detected": False,
        "question_text": "",
        "question_type": "unknown",
        "options": {},
        "proposed_answer": "",
        "answer_text": "",
        "explanation": "Desktop only shows browser homepage.",
        "confidence": 0.0,
        "needs_review": False,
        "warnings": ["No question found"],
    }
    is_valid, errors, cleaned = validate_response(data)
    assert is_valid is True
    assert cleaned["question_detected"] is False


def test_validate_response_invalid_options_and_answer():
    """Verify detection of answer not in options and invalid option labels."""
    data = {
        "question_detected": True,
        "question_text": "Sample question?",
        "question_type": "science",
        "options": {
            "1": "Option One",    # Invalid label (needs A-J)
            "A": "Option Alpha",
        },
        "proposed_answer": "Z",   # Not in options
        "explanation": "Testing validation.",
        "confidence": 0.8,
    }
    is_valid, errors, cleaned = validate_response(data)
    assert is_valid is False
    assert any("Invalid option label" in e for e in errors)
    assert any("not in available options" in e for e in errors)


def test_solver_solve_success(synthetic_rgb_image):
    """Verify solver execution with mocked GeminiClient."""
    mock_gemini = MagicMock()
    mock_gemini.model_name = "gemini-2.0-flash"
    mock_gemini.analyze_image.return_value = {
        "question_detected": True,
        "question_text": "What is 2 + 2?",
        "question_type": "mathematics",
        "options": {"A": "3", "B": "4"},
        "proposed_answer": "B",
        "answer_text": "4",
        "explanation": "2 + 2 = 4",
        "confidence": 0.99,
        "needs_review": False,
        "warnings": [],
    }

    solver = QuestionSolver(gemini_client=mock_gemini)
    res = solver.solve(synthetic_rgb_image)

    assert isinstance(res, SolverResult)
    assert res.question_detected is True
    assert res.proposed_answer == "B"
    assert res.confidence == 0.99
    assert "What is 2 + 2?" in res.format_display()
    assert solver.solve_count == 1


def test_solver_solve_handles_parse_error(synthetic_rgb_image):
    """Verify solver handles raw unparsed text gracefully."""
    mock_gemini = MagicMock()
    mock_gemini.model_name = "gemini-2.0-flash"
    mock_gemini.analyze_image.return_value = {
        "parse_error": True,
        "raw_text": "Raw non-json output",
    }

    solver = QuestionSolver(gemini_client=mock_gemini)
    res = solver.solve(synthetic_rgb_image)

    assert res.needs_review is True
    assert any("not valid JSON" in w for w in res.warnings)
