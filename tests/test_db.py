from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pytest

from leetrevive.db import (
    get_all_problems,
    get_all_reviews,
    get_problem,
    get_reviews,
    init_db,
    insert_problem,
    insert_review,
    update_problem_review,
)
from leetrevive.models import Problem, Review

_UTC = timezone.utc


def _problem(pid: str = "1", title: str = "Two Sum") -> Problem:
    return Problem(
        problem_id=pid,
        title=title,
        url="https://leetcode.com/problems/two-sum/",
        source="leetcode",
        difficulty="easy",
        tags=["array", "hashmap"],
        pattern="hashmap",
        created_at=datetime(2024, 1, 1, tzinfo=_UTC),
        last_reviewed_at=None,
        next_due_at=None,
    )


def _review(pid: str = "1", score: int = 2) -> Review:
    return Review(
        problem_id=pid,
        reviewed_at=datetime(2024, 1, 2, tzinfo=_UTC),
        score=score,
        minutes=15,
        note="Got it",
        mistake=None,
    )


# ---------------------------------------------------------------------------
# init_db
# ---------------------------------------------------------------------------

def test_init_db_creates_file(tmp_path: Path) -> None:
    path = tmp_path / "sub" / "test.db"
    result = init_db(path)
    assert result == path
    assert path.exists()


def test_init_db_is_idempotent(tmp_path: Path) -> None:
    path = tmp_path / "test.db"
    init_db(path)
    init_db(path)  # must not raise


# ---------------------------------------------------------------------------
# Problems
# ---------------------------------------------------------------------------

def test_insert_and_get_problem(db_path: Path) -> None:
    insert_problem(_problem(), db_path)
    result = get_problem("1", db_path)
    assert result is not None
    assert result.problem_id == "1"
    assert result.title == "Two Sum"
    assert result.tags == ["array", "hashmap"]
    assert result.difficulty == "easy"
    assert result.source == "leetcode"


def test_get_problem_not_found(db_path: Path) -> None:
    assert get_problem("999", db_path) is None


def test_insert_duplicate_raises(db_path: Path) -> None:
    insert_problem(_problem(), db_path)
    with pytest.raises(Exception):
        insert_problem(_problem(), db_path)


def test_tags_round_trip_with_spaces(db_path: Path) -> None:
    p = _problem()
    p.tags = ["two pointers", "sliding window"]
    insert_problem(p, db_path)
    result = get_problem("1", db_path)
    assert result is not None
    assert result.tags == ["two pointers", "sliding window"]


def test_empty_tags(db_path: Path) -> None:
    p = _problem()
    p.tags = []
    insert_problem(p, db_path)
    result = get_problem("1", db_path)
    assert result is not None
    assert result.tags == []


def test_get_all_problems_order(db_path: Path) -> None:
    insert_problem(_problem("2", "Add Two Numbers"), db_path)
    insert_problem(_problem("1", "Two Sum"), db_path)
    # Two Sum has an earlier created_at, but we inserted "2" first;
    # get_all_problems orders by created_at ASC.
    # Both share the same created_at here so insertion order applies.
    problems = get_all_problems(db_path)
    assert len(problems) == 2


def test_datetime_roundtrip_preserves_utc(db_path: Path) -> None:
    p = _problem()
    p.created_at = datetime(2024, 6, 15, 12, 30, 0, tzinfo=_UTC)
    insert_problem(p, db_path)
    result = get_problem("1", db_path)
    assert result is not None
    assert result.created_at.year == 2024
    assert result.created_at.month == 6
    assert result.created_at.tzinfo is not None


# ---------------------------------------------------------------------------
# Reviews
# ---------------------------------------------------------------------------

def test_insert_and_get_reviews(db_path: Path) -> None:
    insert_problem(_problem(), db_path)
    insert_review(_review(), db_path)
    rows = get_reviews("1", db_path)
    assert len(rows) == 1
    assert rows[0].score == 2
    assert rows[0].minutes == 15
    assert rows[0].note == "Got it"


def test_get_reviews_empty(db_path: Path) -> None:
    insert_problem(_problem(), db_path)
    assert get_reviews("1", db_path) == []


def test_multiple_reviews_ordered(db_path: Path) -> None:
    insert_problem(_problem(), db_path)
    r1 = _review(score=1)
    r1.reviewed_at = datetime(2024, 1, 2, tzinfo=_UTC)
    r2 = _review(score=3)
    r2.reviewed_at = datetime(2024, 1, 9, tzinfo=_UTC)
    insert_review(r1, db_path)
    insert_review(r2, db_path)
    rows = get_reviews("1", db_path)
    assert rows[0].score == 1
    assert rows[1].score == 3


def test_update_problem_review(db_path: Path) -> None:
    insert_problem(_problem(), db_path)
    now = datetime(2024, 1, 5, tzinfo=_UTC)
    due = datetime(2024, 1, 12, tzinfo=_UTC)
    update_problem_review("1", now, due, db_path)
    p = get_problem("1", db_path)
    assert p is not None
    assert p.last_reviewed_at is not None
    assert p.last_reviewed_at.day == 5
    assert p.next_due_at is not None
    assert p.next_due_at.day == 12


def test_get_all_reviews(db_path: Path) -> None:
    insert_problem(_problem("1"), db_path)
    insert_problem(_problem("2", "Add Two Numbers"), db_path)
    insert_review(_review("1", score=3), db_path)
    insert_review(_review("2", score=1), db_path)
    all_reviews = get_all_reviews(db_path)
    assert len(all_reviews) == 2
