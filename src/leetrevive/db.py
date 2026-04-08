from __future__ import annotations

import os
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Generator, Optional

import platformdirs

from .models import Problem, Review

APP_NAME = "leetrevive"

_DDL = """
CREATE TABLE IF NOT EXISTS problems (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    problem_id       TEXT    NOT NULL UNIQUE,
    title            TEXT    NOT NULL,
    url              TEXT,
    source           TEXT    NOT NULL DEFAULT 'leetcode',
    difficulty       TEXT,
    tags             TEXT,
    pattern          TEXT,
    created_at       TEXT    NOT NULL,
    last_reviewed_at TEXT,
    next_due_at      TEXT
);

CREATE TABLE IF NOT EXISTS reviews (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    problem_id  TEXT    NOT NULL,
    reviewed_at TEXT    NOT NULL,
    score       INTEGER NOT NULL,
    minutes     INTEGER,
    note        TEXT,
    mistake     TEXT,
    FOREIGN KEY (problem_id) REFERENCES problems(problem_id)
);

CREATE INDEX IF NOT EXISTS idx_reviews_problem_id ON reviews(problem_id);
CREATE INDEX IF NOT EXISTS idx_problems_next_due  ON problems(next_due_at);

CREATE TABLE IF NOT EXISTS knowledge_notes (
    key        TEXT PRIMARY KEY,   -- tag slug or "pattern:sliding-window"
    note       TEXT NOT NULL,      -- one-sentence insight shown in learning map
    updated_at TEXT NOT NULL
);
"""


def get_data_dir() -> Path:
    return Path(platformdirs.user_data_dir(APP_NAME))


def get_db_path() -> Path:
    """Return the active DB path. Overridable via LEETREVIVE_DB_PATH (used in tests)."""
    override = os.environ.get("LEETREVIVE_DB_PATH")
    if override:
        return Path(override)
    return get_data_dir() / "leetrevive.db"


@contextmanager
def _connect(db_path: Path) -> Generator[sqlite3.Connection, None, None]:
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db(db_path: Optional[Path] = None) -> Path:
    """Create data directory and initialize schema. Idempotent."""
    path = db_path or get_db_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    with _connect(path) as conn:
        conn.executescript(_DDL)
    return path


# ---------------------------------------------------------------------------
# Datetime serialisation helpers
# ---------------------------------------------------------------------------

def _fmt(dt: Optional[datetime]) -> Optional[str]:
    if dt is None:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.isoformat()


def _parse(value: Optional[str]) -> Optional[datetime]:
    if value is None:
        return None
    dt = datetime.fromisoformat(value)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


# ---------------------------------------------------------------------------
# Row mappers
# ---------------------------------------------------------------------------

def _to_problem(row: sqlite3.Row) -> Problem:
    raw_tags = row["tags"]
    tags = [t.strip() for t in raw_tags.split(",") if t.strip()] if raw_tags else []
    return Problem(
        id=row["id"],
        problem_id=row["problem_id"],
        title=row["title"],
        url=row["url"],
        source=row["source"],
        difficulty=row["difficulty"],
        tags=tags,
        pattern=row["pattern"],
        created_at=_parse(row["created_at"]),  # type: ignore[arg-type]
        last_reviewed_at=_parse(row["last_reviewed_at"]),
        next_due_at=_parse(row["next_due_at"]),
    )


def _to_review(row: sqlite3.Row) -> Review:
    return Review(
        id=row["id"],
        problem_id=row["problem_id"],
        reviewed_at=_parse(row["reviewed_at"]),  # type: ignore[arg-type]
        score=row["score"],
        minutes=row["minutes"],
        note=row["note"],
        mistake=row["mistake"],
    )


# ---------------------------------------------------------------------------
# Problem queries
# ---------------------------------------------------------------------------

def insert_problem(problem: Problem, db_path: Optional[Path] = None) -> None:
    tags_str = ",".join(problem.tags) if problem.tags else None
    path = db_path or get_db_path()
    with _connect(path) as conn:
        conn.execute(
            """
            INSERT INTO problems
                (problem_id, title, url, source, difficulty, tags, pattern,
                 created_at, last_reviewed_at, next_due_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                problem.problem_id,
                problem.title,
                problem.url,
                problem.source,
                problem.difficulty,
                tags_str,
                problem.pattern,
                _fmt(problem.created_at),
                _fmt(problem.last_reviewed_at),
                _fmt(problem.next_due_at),
            ),
        )


def get_problem(problem_id: str, db_path: Optional[Path] = None) -> Optional[Problem]:
    path = db_path or get_db_path()
    with _connect(path) as conn:
        row = conn.execute(
            "SELECT * FROM problems WHERE problem_id = ?", (problem_id,)
        ).fetchone()
    return _to_problem(row) if row else None


def update_problem_review(
    problem_id: str,
    last_reviewed_at: datetime,
    next_due_at: datetime,
    db_path: Optional[Path] = None,
) -> None:
    path = db_path or get_db_path()
    with _connect(path) as conn:
        conn.execute(
            """
            UPDATE problems
               SET last_reviewed_at = ?, next_due_at = ?
             WHERE problem_id = ?
            """,
            (_fmt(last_reviewed_at), _fmt(next_due_at), problem_id),
        )


def get_all_problems(db_path: Optional[Path] = None) -> list[Problem]:
    path = db_path or get_db_path()
    with _connect(path) as conn:
        rows = conn.execute(
            "SELECT * FROM problems ORDER BY created_at ASC"
        ).fetchall()
    return [_to_problem(r) for r in rows]


# ---------------------------------------------------------------------------
# Review queries
# ---------------------------------------------------------------------------

def insert_review(review: Review, db_path: Optional[Path] = None) -> None:
    path = db_path or get_db_path()
    with _connect(path) as conn:
        conn.execute(
            """
            INSERT INTO reviews (problem_id, reviewed_at, score, minutes, note, mistake)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                review.problem_id,
                _fmt(review.reviewed_at),
                review.score,
                review.minutes,
                review.note,
                review.mistake,
            ),
        )


def get_reviews(problem_id: str, db_path: Optional[Path] = None) -> list[Review]:
    path = db_path or get_db_path()
    with _connect(path) as conn:
        rows = conn.execute(
            "SELECT * FROM reviews WHERE problem_id = ? ORDER BY reviewed_at ASC",
            (problem_id,),
        ).fetchall()
    return [_to_review(r) for r in rows]


def get_all_reviews(db_path: Optional[Path] = None) -> list[Review]:
    path = db_path or get_db_path()
    with _connect(path) as conn:
        rows = conn.execute(
            "SELECT * FROM reviews ORDER BY reviewed_at ASC"
        ).fetchall()
    return [_to_review(r) for r in rows]


# ---------------------------------------------------------------------------
# Knowledge notes (learning map insights)
# ---------------------------------------------------------------------------

def get_all_notes(db_path: Optional[Path] = None) -> dict[str, str]:
    """Return all knowledge notes as {key: note}."""
    path = db_path or get_db_path()
    with _connect(path) as conn:
        rows = conn.execute("SELECT key, note FROM knowledge_notes").fetchall()
    return {r["key"]: r["note"] for r in rows}


def upsert_note(key: str, note: str, db_path: Optional[Path] = None) -> None:
    """Insert or update a knowledge note for a tag/pattern key."""
    path = db_path or get_db_path()
    now = _fmt(datetime.now(tz=timezone.utc))
    with _connect(path) as conn:
        conn.execute(
            """
            INSERT INTO knowledge_notes (key, note, updated_at)
            VALUES (?, ?, ?)
            ON CONFLICT(key) DO UPDATE SET note = excluded.note, updated_at = excluded.updated_at
            """,
            (key, note, now),
        )
