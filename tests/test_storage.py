"""Tests for DrillAI SQLite Storage."""

from pathlib import Path
import pytest

from storage import AnalysisStorage


def test_storage_init_creates_table(tmp_path):
    """Verify database and table are initialized automatically."""
    db_file = tmp_path / "test.db"
    storage = AnalysisStorage(db_path=db_file)
    assert db_file.exists()
    assert storage.get_count() == 0


def test_save_and_retrieve_result(tmp_path):
    """Verify saving analysis result and retrieving recent records."""
    db_file = tmp_path / "test.db"
    storage = AnalysisStorage(db_path=db_file)

    sample_result = {
        "question_text": "Hitung 5 x 5?",
        "question_type": "mathematics",
        "options": {"A": "20", "B": "25"},
        "proposed_answer": "B",
        "answer_text": "25",
        "explanation": "5 x 5 = 25",
        "confidence": 0.99,
        "needs_review": False,
        "warnings": [],
        "model": "gemini-2.0-flash",
        "processing_time": 0.45,
    }

    row_id = storage.save_result(sample_result, screenshot_hash="hash_abc123")
    assert row_id > 0
    assert storage.get_count() == 1

    recent = storage.get_recent(limit=10)
    assert len(recent) == 1
    assert recent[0]["question_text"] == "Hitung 5 x 5?"
    assert recent[0]["proposed_answer"] == "B"
    assert recent[0]["screenshot_hash"] == "hash_abc123"


def test_save_duplicate_hash_skips_insert(tmp_path):
    """Verify saving duplicate screenshot_hash returns existing row id."""
    db_file = tmp_path / "test.db"
    storage = AnalysisStorage(db_path=db_file)

    sample_result = {
        "question_text": "Pertanyaan duplikat",
        "proposed_answer": "A",
    }

    id1 = storage.save_result(sample_result, screenshot_hash="unique_hash_1")
    id2 = storage.save_result(sample_result, screenshot_hash="unique_hash_1")

    assert id1 == id2
    assert storage.get_count() == 1


def test_format_results(tmp_path):
    """Verify format_results produces human-readable string."""
    db_file = tmp_path / "test.db"
    storage = AnalysisStorage(db_path=db_file)

    res = storage.get_recent(limit=5)
    assert storage.format_results(res) == "No results found."

    storage.save_result({"question_text": "Q1", "proposed_answer": "C", "confidence": 0.9})
    recent = storage.get_recent(limit=5)
    formatted = storage.format_results(recent)
    assert "Found 1 result(s):" in formatted
    assert "Q: Q1" in formatted
    assert "A: C (90%)" in formatted
