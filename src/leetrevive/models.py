from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional


@dataclass
class Problem:
    problem_id: str               # user-visible ID: "1", "146"
    title: str
    url: Optional[str]
    source: str                   # "leetcode" or custom
    difficulty: Optional[str]     # "easy" | "medium" | "hard"
    tags: list[str]               # e.g. ["array", "hashmap"]
    pattern: Optional[str]        # e.g. "sliding-window"
    created_at: datetime
    last_reviewed_at: Optional[datetime]
    next_due_at: Optional[datetime]
    id: Optional[int] = field(default=None, repr=False)  # sqlite rowid


@dataclass
class Review:
    problem_id: str
    reviewed_at: datetime
    score: int        # 0 = blank, 1 = partial, 2 = struggled, 3 = clean
    minutes: Optional[int]
    note: Optional[str]
    mistake: Optional[str]
    id: Optional[int] = field(default=None, repr=False)


@dataclass
class DailyPick:
    problem: Problem
    reason: str       # human-readable: "overdue 5d", "long unreviewed", "reinforcement: dp"
