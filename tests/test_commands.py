from __future__ import annotations

"""
Command-level integration tests using typer's CliRunner.

All tests use the `isolated_db` fixture which sets LEETREVIVE_DB_PATH
to a temp file, routing all db.get_db_path() calls away from the real
user data directory.
"""

from datetime import datetime, timezone
from pathlib import Path

import pytest
from typer.testing import CliRunner

from leetrevive.cli import app
from leetrevive.db import insert_problem, insert_review, update_problem_review
from leetrevive.models import Problem, Review

runner = CliRunner()

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


# ---------------------------------------------------------------------------
# init
# ---------------------------------------------------------------------------

def test_init_creates_db(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    db = tmp_path / "test.db"
    monkeypatch.setenv("LEETREVIVE_DB_PATH", str(db))
    result = runner.invoke(app, ["init"])
    assert result.exit_code == 0
    assert db.exists()
    assert "Initialized" in result.output


def test_init_is_idempotent(isolated_db: Path) -> None:
    result = runner.invoke(app, ["init"])
    assert result.exit_code == 0


# ---------------------------------------------------------------------------
# add
# ---------------------------------------------------------------------------

def test_add_basic(isolated_db: Path) -> None:
    result = runner.invoke(app, ["add", "1", "Two Sum"])
    assert result.exit_code == 0
    assert "Added" in result.output
    assert "#1" in result.output


def test_add_with_flags(isolated_db: Path) -> None:
    result = runner.invoke(
        app,
        [
            "add", "146", "LRU Cache",
            "--difficulty", "medium",
            "--tags", "hashmap,linked-list",
            "--pattern", "design",
        ],
    )
    assert result.exit_code == 0
    assert "146" in result.output


def test_add_auto_generates_url(isolated_db: Path) -> None:
    result = runner.invoke(app, ["add", "1", "Two Sum"])
    assert "leetcode.com/problems/two-sum" in result.output


def test_add_duplicate_fails(isolated_db: Path) -> None:
    runner.invoke(app, ["add", "1", "Two Sum"])
    result = runner.invoke(app, ["add", "1", "Two Sum Again"])
    assert result.exit_code != 0


def test_add_invalid_difficulty_fails(isolated_db: Path) -> None:
    result = runner.invoke(
        app, ["add", "1", "Two Sum", "--difficulty", "extreme"]
    )
    assert result.exit_code != 0


def test_add_without_init_fails(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LEETREVIVE_DB_PATH", str(tmp_path / "missing.db"))
    result = runner.invoke(app, ["add", "1", "Two Sum"])
    assert result.exit_code != 0


# ---------------------------------------------------------------------------
# done
# ---------------------------------------------------------------------------

def test_done_records_review(isolated_db: Path) -> None:
    insert_problem(_problem(), isolated_db)
    result = runner.invoke(app, ["done", "1", "--score", "3"])
    assert result.exit_code == 0
    assert "Recorded" in result.output
    assert "Next due" in result.output


def test_done_with_all_flags(isolated_db: Path) -> None:
    insert_problem(_problem(), isolated_db)
    result = runner.invoke(
        app,
        ["done", "1", "--score", "2", "--minutes", "25", "--note", "clean", "--mistake", "edge case"],
    )
    assert result.exit_code == 0


def test_done_invalid_problem_fails(isolated_db: Path) -> None:
    result = runner.invoke(app, ["done", "999", "--score", "2"])
    assert result.exit_code != 0


# ---------------------------------------------------------------------------
# today
# ---------------------------------------------------------------------------

def test_today_empty_bank(isolated_db: Path) -> None:
    result = runner.invoke(app, ["today"])
    assert result.exit_code == 0
    assert "No problems" in result.output


def test_today_shows_due_problems(isolated_db: Path) -> None:
    p = _problem()
    p.next_due_at = datetime(2020, 1, 1, tzinfo=_UTC)  # long overdue
    p.last_reviewed_at = datetime(2020, 1, 1, tzinfo=_UTC)
    insert_problem(p, isolated_db)
    result = runner.invoke(app, ["today"])
    assert result.exit_code == 0
    assert "Two Sum" in result.output


# ---------------------------------------------------------------------------
# bank
# ---------------------------------------------------------------------------

def test_bank_shows_all_problems(isolated_db: Path) -> None:
    insert_problem(_problem("1", "Two Sum"), isolated_db)
    insert_problem(_problem("2", "Add Two Numbers"), isolated_db)
    result = runner.invoke(app, ["bank"])
    assert result.exit_code == 0
    assert "Two Sum" in result.output
    assert "Add Two Numbers" in result.output


def test_bank_filter_by_tag(isolated_db: Path) -> None:
    insert_problem(_problem("1", "Two Sum"), isolated_db)        # tags: array, hashmap
    p2 = _problem("2", "Climbing Stairs")
    p2.tags = ["dp"]
    insert_problem(p2, isolated_db)
    result = runner.invoke(app, ["bank", "--tag", "dp"])
    assert result.exit_code == 0
    assert "Climbing Stairs" in result.output
    assert "Two Sum" not in result.output


def test_bank_filter_due(isolated_db: Path) -> None:
    p = _problem()
    p.next_due_at = datetime(2020, 1, 1, tzinfo=_UTC)
    insert_problem(p, isolated_db)
    p2 = _problem("2", "Future Problem")
    p2.next_due_at = datetime(2099, 1, 1, tzinfo=_UTC)
    insert_problem(p2, isolated_db)
    result = runner.invoke(app, ["bank", "--due"])
    assert "Two Sum" in result.output
    assert "Future Problem" not in result.output


# ---------------------------------------------------------------------------
# review
# ---------------------------------------------------------------------------

def test_review_shows_detail(isolated_db: Path) -> None:
    insert_problem(_problem(), isolated_db)
    result = runner.invoke(app, ["review", "1"])
    assert result.exit_code == 0
    assert "Two Sum" in result.output
    assert "hashmap" in result.output


def test_review_shows_history(isolated_db: Path) -> None:
    insert_problem(_problem(), isolated_db)
    r = Review(
        problem_id="1",
        reviewed_at=datetime(2024, 6, 1, tzinfo=_UTC),
        score=3,
        minutes=12,
        note="clean solve",
        mistake=None,
    )
    insert_review(r, isolated_db)
    result = runner.invoke(app, ["review", "1"])
    assert result.exit_code == 0
    assert "clean solve" in result.output


def test_review_not_found(isolated_db: Path) -> None:
    result = runner.invoke(app, ["review", "999"])
    assert result.exit_code != 0


# ---------------------------------------------------------------------------
# open
# ---------------------------------------------------------------------------

def test_open_no_url_fails(isolated_db: Path) -> None:
    p = _problem()
    p.url = None
    insert_problem(p, isolated_db)
    result = runner.invoke(app, ["open", "1"])
    assert result.exit_code != 0


def test_open_not_found_fails(isolated_db: Path) -> None:
    result = runner.invoke(app, ["open", "999"])
    assert result.exit_code != 0


# ---------------------------------------------------------------------------
# stats
# ---------------------------------------------------------------------------

def test_stats_empty(isolated_db: Path) -> None:
    result = runner.invoke(app, ["stats"])
    assert result.exit_code == 0
    assert "Total problems" in result.output


def test_stats_counts(isolated_db: Path) -> None:
    insert_problem(_problem("1"), isolated_db)
    insert_problem(_problem("2", "Add Two Numbers"), isolated_db)
    r = Review(
        problem_id="1",
        reviewed_at=datetime(2024, 6, 1, tzinfo=_UTC),
        score=2,
        minutes=10,
        note=None,
        mistake=None,
    )
    insert_review(r, isolated_db)
    result = runner.invoke(app, ["stats"])
    assert result.exit_code == 0
    assert "2" in result.output  # 2 total problems


# ---------------------------------------------------------------------------
# version flag
# ---------------------------------------------------------------------------

def test_version_flag() -> None:
    result = runner.invoke(app, ["--version"])
    assert result.exit_code == 0
    assert "leetrevive" in result.output
    assert "0.1.0" in result.output
