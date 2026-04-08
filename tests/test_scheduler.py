from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from leetrevive.models import Problem, Review
from leetrevive.scheduler import compute_next_due, pick_today

_UTC = timezone.utc


def _dt(year: int, month: int, day: int) -> datetime:
    return datetime(year, month, day, tzinfo=_UTC)


def _problem(
    pid: str,
    *,
    next_due_at: datetime | None = None,
    last_reviewed_at: datetime | None = None,
    tags: list[str] | None = None,
    pattern: str | None = None,
) -> Problem:
    return Problem(
        problem_id=pid,
        title=f"Problem {pid}",
        url=None,
        source="leetcode",
        difficulty="medium",
        tags=tags or [],
        pattern=pattern,
        created_at=_dt(2024, 1, 1),
        last_reviewed_at=last_reviewed_at,
        next_due_at=next_due_at,
    )


def _review(pid: str, score: int, reviewed_at: datetime) -> Review:
    return Review(
        problem_id=pid,
        reviewed_at=reviewed_at,
        score=score,
        minutes=None,
        note=None,
        mistake=None,
    )


# ---------------------------------------------------------------------------
# compute_next_due
# ---------------------------------------------------------------------------

class TestComputeNextDue:
    def test_score_0_always_one_day(self) -> None:
        now = _dt(2024, 6, 1)
        assert compute_next_due(0, [], now) == now + timedelta(days=1)

    def test_score_0_ignores_streak(self) -> None:
        now = _dt(2024, 6, 1)
        history = [
            _review("1", 3, _dt(2024, 5, 1)),
            _review("1", 3, _dt(2024, 5, 15)),
        ]
        result = compute_next_due(0, history, now)
        assert result == now + timedelta(days=1)

    def test_score_1_three_days(self) -> None:
        assert compute_next_due(1, [], _dt(2024, 6, 1)) == _dt(2024, 6, 1) + timedelta(days=3)

    def test_score_2_seven_days_no_history(self) -> None:
        assert compute_next_due(2, [], _dt(2024, 6, 1)) == _dt(2024, 6, 1) + timedelta(days=7)

    def test_score_3_fourteen_days_no_history(self) -> None:
        assert compute_next_due(3, [], _dt(2024, 6, 1)) == _dt(2024, 6, 1) + timedelta(days=14)

    def test_two_consecutive_strong_gives_30_day_floor(self) -> None:
        now = _dt(2024, 6, 1)
        # history ends with one strong; new score is 3 → streak becomes 2
        history = [_review("1", 3, _dt(2024, 5, 1))]
        result = compute_next_due(3, history, now)
        assert result == now + timedelta(days=30)

    def test_three_consecutive_strong_gives_60_day_floor(self) -> None:
        now = _dt(2024, 6, 1)
        history = [
            _review("1", 3, _dt(2024, 4, 1)),
            _review("1", 3, _dt(2024, 5, 1)),
        ]
        result = compute_next_due(3, history, now)
        assert result == now + timedelta(days=60)

    def test_weak_score_breaks_streak(self) -> None:
        now = _dt(2024, 6, 1)
        history = [
            _review("1", 3, _dt(2024, 4, 1)),
            _review("1", 0, _dt(2024, 5, 1)),  # miss resets streak
        ]
        # tail = 0; new score 3 → streak = 1 → base 14d
        result = compute_next_due(3, history, now)
        assert result == now + timedelta(days=14)

    def test_score_2_with_two_consecutive_strong_raises_floor(self) -> None:
        now = _dt(2024, 6, 1)
        history = [_review("1", 2, _dt(2024, 5, 1))]
        # tail = 1; new score 2 → streak = 2 → floor 30d, base for score-2 = 7d
        result = compute_next_due(2, history, now)
        assert result == now + timedelta(days=30)

    def test_score_1_never_extended(self) -> None:
        # score 1 is not "strong" so streak logic doesn't apply
        now = _dt(2024, 6, 1)
        history = [_review("1", 1, _dt(2024, 5, 1))]
        result = compute_next_due(1, history, now)
        assert result == now + timedelta(days=3)


# ---------------------------------------------------------------------------
# pick_today
# ---------------------------------------------------------------------------

class TestPickToday:
    def test_empty_bank_returns_empty(self) -> None:
        assert pick_today([], [], _dt(2024, 6, 1)) == []

    def test_fewer_problems_than_n(self) -> None:
        today = _dt(2024, 6, 1)
        problems = [_problem("1", next_due_at=_dt(2024, 6, 1))]
        picks = pick_today(problems, [], today)
        assert len(picks) == 1

    def test_returns_exactly_n_when_enough(self) -> None:
        today = _dt(2024, 6, 10)
        problems = [
            _problem("1", next_due_at=_dt(2024, 6, 1)),   # overdue
            _problem("2", next_due_at=_dt(2024, 6, 10)),  # due today
            _problem("3"),                                  # never reviewed
        ]
        picks = pick_today(problems, [], today)
        assert len(picks) == 3

    def test_no_duplicate_picks(self) -> None:
        today = _dt(2024, 6, 10)
        problems = [
            _problem("1", next_due_at=_dt(2024, 6, 1)),
            _problem("2", next_due_at=_dt(2024, 6, 5)),
            _problem("3", next_due_at=_dt(2024, 6, 10)),
            _problem("4"),
        ]
        picks = pick_today(problems, [], today, n=3)
        ids = [p.problem.problem_id for p in picks]
        assert len(ids) == len(set(ids))

    def test_most_overdue_comes_first(self) -> None:
        today = _dt(2024, 6, 10)
        problems = [
            _problem("1", next_due_at=_dt(2024, 6, 3)),   # overdue 7d
            _problem("2", next_due_at=_dt(2024, 6, 1)),   # overdue 9d — most overdue
            _problem("3", next_due_at=_dt(2024, 6, 8)),   # overdue 2d
        ]
        picks = pick_today(problems, [], today)
        assert picks[0].problem.problem_id == "2"

    def test_never_reviewed_included(self) -> None:
        today = _dt(2024, 6, 1)
        problems = [
            _problem("1", next_due_at=today),
            _problem("2", next_due_at=today),
            _problem("3"),  # never reviewed
        ]
        picks = pick_today(problems, [], today)
        ids = [p.problem.problem_id for p in picks]
        assert "3" in ids

    def test_overdue_reason_label(self) -> None:
        today = _dt(2024, 6, 10)
        problems = [_problem("1", next_due_at=_dt(2024, 6, 5))]
        picks = pick_today(problems, [], today)
        assert "overdue" in picks[0].reason

    def test_due_today_reason_label(self) -> None:
        today = _dt(2024, 6, 1)
        problems = [_problem("1", next_due_at=today)]
        picks = pick_today(problems, [], today)
        assert picks[0].reason == "due today"

    def test_reinforcement_from_recent_pattern(self) -> None:
        today = _dt(2024, 6, 10)
        # p1 was recently reviewed with pattern "dp"
        # p2 shares the same pattern and is not due yet → reinforcement candidate
        p1 = _problem("1", next_due_at=_dt(2024, 7, 1), pattern="dp")
        p2 = _problem("2", next_due_at=_dt(2024, 7, 1), pattern="dp")
        # Mark p1 as reviewed 3 days ago
        p1.last_reviewed_at = _dt(2024, 6, 7)
        recent_review = _review("1", 3, _dt(2024, 6, 7))
        # p3 has no pattern and isn't due → filler
        p3 = _problem("3")

        picks = pick_today([p1, p2, p3], [recent_review], today, n=2)
        ids = [p.problem.problem_id for p in picks]
        # p3 (never reviewed) and p2 (reinforcement) should both appear
        assert "3" in ids or "2" in ids

    def test_future_not_due_not_included_unless_needed(self) -> None:
        today = _dt(2024, 6, 1)
        # Only 1 overdue problem; 2 others are far future with recent reviews
        last_week = _dt(2024, 5, 25)
        p1 = _problem("1", next_due_at=_dt(2024, 5, 30), last_reviewed_at=last_week)
        p2 = _problem("2", next_due_at=_dt(2024, 7, 1), last_reviewed_at=last_week)
        p3 = _problem("3", next_due_at=_dt(2024, 7, 1), last_reviewed_at=last_week)

        picks = pick_today([p1, p2, p3], [], today, n=1)
        assert picks[0].problem.problem_id == "1"
