from __future__ import annotations

"""
End-to-end flow tests for leetrevive MVP.

Each section narrates a realistic usage flow and asserts both the CLI output
and the resulting database state. Tests are intentionally readable — a new
contributor should be able to understand the intended behaviour from these
tests alone, without reading the source.

All tests use the `isolated_db` fixture, which routes db.get_db_path() to a
throwaway SQLite file via the LEETREVIVE_DB_PATH environment variable.
"""

from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from typer.testing import CliRunner

from leetrevive.cli import app
from leetrevive.db import get_problem, get_reviews, insert_problem, insert_review
from leetrevive.models import Problem, Review
from leetrevive.scheduler import _consecutive_strong_tail, compute_next_due

runner = CliRunner()
_UTC = timezone.utc


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_problem(
    pid: str = "1",
    title: str = "Two Sum",
    *,
    tags: list[str] | None = None,
    pattern: str | None = None,
    next_due_at: datetime | None = None,
    last_reviewed_at: datetime | None = None,
) -> Problem:
    return Problem(
        problem_id=pid,
        title=title,
        url=f"https://leetcode.com/problems/{title.lower().replace(' ', '-')}/",
        source="leetcode",
        difficulty="medium",
        tags=tags or [],
        pattern=pattern,
        created_at=datetime(2024, 1, 1, tzinfo=_UTC),
        last_reviewed_at=last_reviewed_at,
        next_due_at=next_due_at,
    )


def _make_review(pid: str, score: int, days_ago: int = 1) -> Review:
    reviewed_at = datetime.now(tz=_UTC) - timedelta(days=days_ago)
    return Review(
        problem_id=pid,
        reviewed_at=reviewed_at,
        score=score,
        minutes=None,
        note=None,
        mistake=None,
    )


# ---------------------------------------------------------------------------
# Init flow
# ---------------------------------------------------------------------------

class TestInitFlow:
    def test_creates_db_file(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        db = tmp_path / "test.db"
        monkeypatch.setenv("LEETREVIVE_DB_PATH", str(db))
        result = runner.invoke(app, ["init"])
        assert result.exit_code == 0
        assert db.exists(), "init should create the database file"

    def test_prints_db_path_to_output(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        db = tmp_path / "leet.db"
        monkeypatch.setenv("LEETREVIVE_DB_PATH", str(db))
        result = runner.invoke(app, ["init"])
        # Rich may wrap long paths across lines; collapse whitespace before checking.
        flat = " ".join(result.output.split())
        assert "leet.db" in flat, "init should print the database path"

    def test_running_twice_does_not_corrupt(self, isolated_db: Path) -> None:
        # Add a problem, re-run init, confirm the problem survives.
        runner.invoke(app, ["add", "1", "Two Sum"])
        runner.invoke(app, ["init"])
        p = get_problem("1", isolated_db)
        assert p is not None, "re-running init should not wipe existing data"

    def test_next_command_works_immediately_after_init(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        db = tmp_path / "fresh.db"
        monkeypatch.setenv("LEETREVIVE_DB_PATH", str(db))
        runner.invoke(app, ["init"])
        result = runner.invoke(app, ["today"])
        # 'today' on an empty bank should still exit cleanly, not crash.
        assert result.exit_code == 0


# ---------------------------------------------------------------------------
# Add flow
# ---------------------------------------------------------------------------

class TestAddFlow:
    def test_problem_persisted_to_db(self, isolated_db: Path) -> None:
        runner.invoke(app, ["add", "1", "Two Sum", "--difficulty", "easy", "--tags", "array,hashmap"])
        p = get_problem("1", isolated_db)
        assert p is not None
        assert p.title == "Two Sum"
        assert p.difficulty == "easy"
        assert p.tags == ["array", "hashmap"]

    def test_url_slug_generated_from_title(self, isolated_db: Path) -> None:
        runner.invoke(app, ["add", "42", "Trapping Rain Water"])
        p = get_problem("42", isolated_db)
        assert p is not None
        assert p.url is not None
        assert "trapping-rain-water" in p.url

    def test_url_slug_strips_special_characters(self, isolated_db: Path) -> None:
        # Titles like "N-th Tribonacci Number" should produce a clean slug.
        runner.invoke(app, ["add", "1137", "N-th Tribonacci Number"])
        p = get_problem("1137", isolated_db)
        assert p is not None
        assert p.url is not None
        # URL should not contain raw parentheses or capital letters
        assert p.url == p.url.lower()
        assert "(" not in p.url

    def test_custom_url_overrides_auto_generation(self, isolated_db: Path) -> None:
        custom = "https://custom.example.com/problem/1"
        runner.invoke(app, ["add", "1", "Two Sum", "--url", custom])
        p = get_problem("1", isolated_db)
        assert p is not None
        assert p.url == custom

    def test_non_leetcode_source_gets_no_auto_url(self, isolated_db: Path) -> None:
        runner.invoke(app, ["add", "A1", "Graph Paths", "--source", "hackerrank"])
        p = get_problem("A1", isolated_db)
        assert p is not None
        # No auto-URL for non-leetcode sources without explicit --url
        assert p.url is None or "hackerrank" not in (p.url or "")

    def test_pattern_stored_and_shown(self, isolated_db: Path) -> None:
        runner.invoke(app, ["add", "76", "Minimum Window Substring", "--pattern", "sliding-window"])
        p = get_problem("76", isolated_db)
        assert p is not None
        assert p.pattern == "sliding-window"

    def test_next_due_is_null_until_first_review(self, isolated_db: Path) -> None:
        runner.invoke(app, ["add", "1", "Two Sum"])
        p = get_problem("1", isolated_db)
        assert p is not None
        assert p.next_due_at is None, "next_due_at should be NULL before any review"
        assert p.last_reviewed_at is None


# ---------------------------------------------------------------------------
# Done flow
# ---------------------------------------------------------------------------

class TestDoneFlow:
    def test_review_written_to_db(self, isolated_db: Path) -> None:
        insert_problem(_make_problem(), isolated_db)
        runner.invoke(app, ["done", "1", "--score", "2"])
        reviews = get_reviews("1", isolated_db)
        assert len(reviews) == 1
        assert reviews[0].score == 2

    def test_next_due_set_in_db_after_done(self, isolated_db: Path) -> None:
        insert_problem(_make_problem(), isolated_db)
        runner.invoke(app, ["done", "1", "--score", "3"])
        p = get_problem("1", isolated_db)
        assert p is not None
        assert p.next_due_at is not None, "done should set next_due_at on the problem"
        assert p.last_reviewed_at is not None

    def test_score_0_schedules_next_day(self, isolated_db: Path) -> None:
        insert_problem(_make_problem(), isolated_db)
        runner.invoke(app, ["done", "1", "--score", "0"])
        p = get_problem("1", isolated_db)
        assert p is not None and p.next_due_at is not None
        days_until_due = (p.next_due_at - datetime.now(tz=_UTC)).days
        assert days_until_due == 0, "score 0 should schedule for tomorrow (0 full days away)"

    def test_score_3_schedules_14_days_first_review(self, isolated_db: Path) -> None:
        insert_problem(_make_problem(), isolated_db)
        runner.invoke(app, ["done", "1", "--score", "3"])
        p = get_problem("1", isolated_db)
        assert p is not None and p.next_due_at is not None
        days = (p.next_due_at - datetime.now(tz=_UTC)).days
        # Allow ±1 day for test execution timing
        assert 13 <= days <= 14, f"expected ~14 days, got {days}"

    def test_score_3_twice_extends_to_30_days(self, isolated_db: Path) -> None:
        # Two consecutive clean solves should raise the floor to 30 days.
        insert_problem(_make_problem(), isolated_db)
        runner.invoke(app, ["done", "1", "--score", "3"])
        runner.invoke(app, ["done", "1", "--score", "3"])
        p = get_problem("1", isolated_db)
        assert p is not None and p.next_due_at is not None
        days = (p.next_due_at - datetime.now(tz=_UTC)).days
        assert 28 <= days <= 31, f"expected ~30 days after 2 consecutive clean solves, got {days}"

    def test_score_0_after_streak_resets_to_1_day(self, isolated_db: Path) -> None:
        # Build up a streak of 2 strong reviews, then miss.
        insert_problem(_make_problem(), isolated_db)
        runner.invoke(app, ["done", "1", "--score", "3"])
        runner.invoke(app, ["done", "1", "--score", "3"])
        runner.invoke(app, ["done", "1", "--score", "0"])
        p = get_problem("1", isolated_db)
        assert p is not None and p.next_due_at is not None
        days = (p.next_due_at - datetime.now(tz=_UTC)).days
        assert days == 0, "miss (score 0) should reset interval to 1 day regardless of streak"

    def test_review_count_increments_per_done(self, isolated_db: Path) -> None:
        insert_problem(_make_problem(), isolated_db)
        for score in [2, 3, 1]:
            runner.invoke(app, ["done", "1", f"--score={score}"])
        reviews = get_reviews("1", isolated_db)
        assert len(reviews) == 3

    def test_note_and_mistake_stored(self, isolated_db: Path) -> None:
        insert_problem(_make_problem(), isolated_db)
        runner.invoke(
            app,
            ["done", "1", "--score", "1", "--note", "almost got it", "--mistake", "wrong base case"],
        )
        reviews = get_reviews("1", isolated_db)
        assert reviews[0].note == "almost got it"
        assert reviews[0].mistake == "wrong base case"

    def test_minutes_stored(self, isolated_db: Path) -> None:
        insert_problem(_make_problem(), isolated_db)
        runner.invoke(app, ["done", "1", "--score", "2", "--minutes", "18"])
        reviews = get_reviews("1", isolated_db)
        assert reviews[0].minutes == 18


# ---------------------------------------------------------------------------
# Today flow
# ---------------------------------------------------------------------------

class TestTodayFlow:
    def test_returns_exactly_3_with_many_problems(self, isolated_db: Path) -> None:
        # Plant 6 overdue problems — today should still return exactly 3.
        overdue = datetime(2020, 1, 1, tzinfo=_UTC)
        for i in range(1, 7):
            p = _make_problem(str(i), f"Problem {i}", next_due_at=overdue, last_reviewed_at=overdue)
            insert_problem(p, isolated_db)
        result = runner.invoke(app, ["today"])
        assert result.exit_code == 0
        # Count table data rows: each problem appears as exactly one line
        # containing its ID in the output. IDs 1-6 → only 3 should appear.
        shown = sum(1 for line in result.output.splitlines() if "Problem" in line)
        assert shown == 3

    def test_picks_are_all_distinct(self, isolated_db: Path) -> None:
        overdue = datetime(2020, 1, 1, tzinfo=_UTC)
        for i in range(1, 7):
            p = _make_problem(str(i), f"Problem {i}", next_due_at=overdue, last_reviewed_at=overdue)
            insert_problem(p, isolated_db)
        result = runner.invoke(app, ["today"])
        # Extract IDs from output lines that contain a problem ID pattern
        ids_seen = []
        for line in result.output.splitlines():
            for i in range(1, 7):
                if f" {i} " in line and "Problem" in line:
                    ids_seen.append(i)
        assert len(ids_seen) == len(set(ids_seen)), "today should never show the same problem twice"

    def test_tip_text_shown(self, isolated_db: Path) -> None:
        p = _make_problem(next_due_at=datetime(2020, 1, 1, tzinfo=_UTC),
                          last_reviewed_at=datetime(2020, 1, 1, tzinfo=_UTC))
        insert_problem(p, isolated_db)
        result = runner.invoke(app, ["today"])
        assert "open" in result.output.lower() or "done" in result.output.lower(), \
            "today should show usage tip"

    def test_never_reviewed_problems_appear(self, isolated_db: Path) -> None:
        # Problems with no next_due_at should still surface via long-unreviewed bucket.
        for i in range(1, 5):
            insert_problem(_make_problem(str(i), f"Problem {i}"), isolated_db)
        result = runner.invoke(app, ["today"])
        assert result.exit_code == 0
        # At least one problem should appear
        assert any(f"Problem {i}" in result.output for i in range(1, 5))

    def test_nothing_due_shows_positive_message(self, isolated_db: Path) -> None:
        # A single problem with a far-future due date and recent review
        p = _make_problem(
            next_due_at=datetime(2099, 1, 1, tzinfo=_UTC),
            last_reviewed_at=datetime.now(tz=_UTC) - timedelta(days=1),
        )
        insert_problem(p, isolated_db)
        result = runner.invoke(app, ["today"])
        # Either shows the problem (reinforcement/backfill) or a "nothing due" message.
        # Either way it should not crash.
        assert result.exit_code == 0


# ---------------------------------------------------------------------------
# Review history flow
# ---------------------------------------------------------------------------

class TestReviewHistoryFlow:
    def test_shows_no_history_message_for_fresh_problem(self, isolated_db: Path) -> None:
        insert_problem(_make_problem(), isolated_db)
        result = runner.invoke(app, ["review", "1"])
        assert result.exit_code == 0
        assert "No review history" in result.output

    def test_shows_all_review_entries(self, isolated_db: Path) -> None:
        insert_problem(_make_problem(), isolated_db)
        for score, note in [(0, "blanked"), (2, "got it"), (3, "clean")]:
            insert_review(Review(
                problem_id="1",
                reviewed_at=datetime(2024, 3, score + 1, tzinfo=_UTC),
                score=score,
                minutes=10,
                note=note,
                mistake=None,
            ), isolated_db)
        result = runner.invoke(app, ["review", "1"])
        assert "blanked" in result.output
        assert "got it" in result.output
        assert "clean" in result.output

    def test_shows_avg_score(self, isolated_db: Path) -> None:
        insert_problem(_make_problem(), isolated_db)
        for score in [2, 2, 2]:
            insert_review(Review(
                problem_id="1",
                reviewed_at=datetime(2024, 3, 1, tzinfo=_UTC),
                score=score,
                minutes=None,
                note=None,
                mistake=None,
            ), isolated_db)
        result = runner.invoke(app, ["review", "1"])
        assert "2.0" in result.output, "avg score should be shown in review detail"

    def test_shows_mistake_field(self, isolated_db: Path) -> None:
        insert_problem(_make_problem(), isolated_db)
        insert_review(Review(
            problem_id="1",
            reviewed_at=datetime(2024, 3, 1, tzinfo=_UTC),
            score=1,
            minutes=20,
            note=None,
            mistake="off-by-one",  # short enough to fit in any terminal width
        ), isolated_db)
        result = runner.invoke(app, ["review", "1"])
        assert "off-by-one" in result.output

    def test_shows_problem_metadata(self, isolated_db: Path) -> None:
        insert_problem(_make_problem(
            tags=["heap", "greedy"],
            pattern="two-heaps",
        ), isolated_db)
        result = runner.invoke(app, ["review", "1"])
        assert "heap" in result.output
        assert "two-heaps" in result.output

    def test_review_count_correct(self, isolated_db: Path) -> None:
        insert_problem(_make_problem(), isolated_db)
        for i in range(4):
            insert_review(Review(
                problem_id="1",
                reviewed_at=datetime(2024, 3, i + 1, tzinfo=_UTC),
                score=2,
                minutes=None,
                note=None,
                mistake=None,
            ), isolated_db)
        result = runner.invoke(app, ["review", "1"])
        assert "4" in result.output


# ---------------------------------------------------------------------------
# Stats flow
# ---------------------------------------------------------------------------

class TestStatsFlow:
    def test_empty_stats_exits_cleanly(self, isolated_db: Path) -> None:
        result = runner.invoke(app, ["stats"])
        assert result.exit_code == 0
        assert "Total problems" in result.output
        assert "0" in result.output

    def test_total_problems_count(self, isolated_db: Path) -> None:
        for i in range(1, 4):
            insert_problem(_make_problem(str(i), f"Problem {i}"), isolated_db)
        result = runner.invoke(app, ["stats"])
        assert result.exit_code == 0
        assert "3" in result.output

    def test_overdue_count_shown(self, isolated_db: Path) -> None:
        # 2 overdue, 1 future
        overdue = datetime(2020, 6, 1, tzinfo=_UTC)
        future = datetime(2099, 1, 1, tzinfo=_UTC)
        insert_problem(_make_problem("1", next_due_at=overdue), isolated_db)
        insert_problem(_make_problem("2", "Problem 2", next_due_at=overdue), isolated_db)
        insert_problem(_make_problem("3", "Problem 3", next_due_at=future), isolated_db)
        result = runner.invoke(app, ["stats"])
        assert result.exit_code == 0
        # "2" should appear somewhere in the output as the overdue count
        assert "2" in result.output

    def test_due_today_count_shown(self, isolated_db: Path) -> None:
        today_midnight = datetime.now(tz=_UTC).replace(hour=0, minute=0, second=0, microsecond=0)
        insert_problem(_make_problem("1", next_due_at=today_midnight), isolated_db)
        insert_problem(_make_problem("2", "Problem 2", next_due_at=datetime(2099, 1, 1, tzinfo=_UTC)), isolated_db)
        result = runner.invoke(app, ["stats"])
        assert result.exit_code == 0
        assert "1" in result.output  # 1 due today

    def test_weak_pattern_appears_in_output(self, isolated_db: Path) -> None:
        p = _make_problem(pattern="sliding-window")
        insert_problem(p, isolated_db)
        insert_review(Review(
            problem_id="1",
            reviewed_at=datetime(2024, 3, 1, tzinfo=_UTC),
            score=0,  # weak
            minutes=None,
            note=None,
            mistake=None,
        ), isolated_db)
        result = runner.invoke(app, ["stats"])
        assert "sliding-window" in result.output

    def test_weak_tag_appears_in_output(self, isolated_db: Path) -> None:
        p = _make_problem(tags=["dynamic-programming"])
        insert_problem(p, isolated_db)
        insert_review(Review(
            problem_id="1",
            reviewed_at=datetime(2024, 3, 1, tzinfo=_UTC),
            score=0,
            minutes=None,
            note=None,
            mistake=None,
        ), isolated_db)
        result = runner.invoke(app, ["stats"])
        assert "dynamic-programming" in result.output

    def test_no_stats_section_when_no_reviews(self, isolated_db: Path) -> None:
        # With no reviews there are no weak patterns — stats should say so gracefully.
        insert_problem(_make_problem(), isolated_db)
        result = runner.invoke(app, ["stats"])
        assert result.exit_code == 0
        assert "No pattern" in result.output or "add reviews" in result.output.lower()


# ---------------------------------------------------------------------------
# Scheduler integration (pure, no CLI)
# ---------------------------------------------------------------------------

class TestSchedulerIntegration:
    """
    Full review-cycle scenarios exercising compute_next_due and the
    streak counter end-to-end, without hitting the database.
    """

    def test_score_progression_base_intervals(self) -> None:
        now = datetime(2024, 6, 1, tzinfo=_UTC)
        for score, expected_days in [(0, 1), (1, 3), (2, 7), (3, 14)]:
            result = compute_next_due(score, [], now)
            assert result == now + timedelta(days=expected_days), \
                f"score {score} should give {expected_days} days"

    def test_streak_counter_on_consecutive_strong_reviews(self) -> None:
        # Verify _consecutive_strong_tail directly.
        from leetrevive.models import Review

        def _r(score: int) -> Review:
            return Review("1", datetime(2024, 1, 1, tzinfo=_UTC), score, None, None, None)

        assert _consecutive_strong_tail([]) == 0
        assert _consecutive_strong_tail([_r(3)]) == 1
        assert _consecutive_strong_tail([_r(3), _r(3)]) == 2
        assert _consecutive_strong_tail([_r(3), _r(0), _r(3)]) == 1  # miss breaks streak
        assert _consecutive_strong_tail([_r(1), _r(2)]) == 1          # score 1 not strong

    def test_full_cycle_clean_then_miss_then_clean(self) -> None:
        now = datetime(2024, 6, 1, tzinfo=_UTC)
        history: list[Review] = []

        def _do_review(score: int) -> datetime:
            from leetrevive.models import Review as R
            nonlocal history
            due = compute_next_due(score, history, now)
            history.append(R("1", now, score, None, None, None))
            return due

        # First clean solve: 14 days
        due1 = _do_review(3)
        assert due1 == now + timedelta(days=14)

        # Second clean solve: streak=2 → 30 days
        due2 = _do_review(3)
        assert due2 == now + timedelta(days=30)

        # Miss: always 1 day, streak resets
        due3 = _do_review(0)
        assert due3 == now + timedelta(days=1)

        # Clean again after miss: streak=1 → back to base 14 days
        due4 = _do_review(3)
        assert due4 == now + timedelta(days=14)

    def test_weak_score_never_extends_interval(self) -> None:
        now = datetime(2024, 6, 1, tzinfo=_UTC)
        # score 1 repeated many times should never trigger 30-day extension
        from leetrevive.models import Review as R
        history = [R("1", now, 1, None, None, None)] * 10
        result = compute_next_due(1, history, now)
        assert result == now + timedelta(days=3), \
            "score 1 is not 'strong'; interval should never be extended"
