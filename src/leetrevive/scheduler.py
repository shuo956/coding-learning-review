from __future__ import annotations

"""
Scheduling logic for leetrevive.

All functions are pure (no DB calls). Commands fetch data, pass it in,
and receive decisions back — keeping this module trivially testable.
"""

from collections import Counter, defaultdict
from datetime import date, datetime, timedelta, timezone
from typing import Optional

from .models import DailyPick, Problem, Review

# Base review intervals keyed by score (0-3)
_BASE_DAYS: dict[int, int] = {0: 1, 1: 3, 2: 7, 3: 14}

# Extended interval caps applied after consecutive strong reviews
_EXT_2_CONSECUTIVE = 30   # 2+ strong in a row → minimum 30d
_EXT_3_CONSECUTIVE = 60   # 3+ strong in a row → minimum 60d

# A problem unseen for this many days qualifies as "long unreviewed"
_LONG_UNREVIEWED_DAYS = 30

# Look back this many days when scoring reinforcement candidates
_REINFORCEMENT_WINDOW_DAYS = 7


def _consecutive_strong_tail(history: list[Review]) -> int:
    """Count consecutive score >= 2 reviews at the *end* of history."""
    count = 0
    for r in reversed(history):
        if r.score >= 2:
            count += 1
        else:
            break
    return count


def compute_next_due(
    score: int,
    history: list[Review],
    now: Optional[datetime] = None,
) -> datetime:
    """
    Return the next due datetime after a review with the given score.

    Rules:
    - score 0 always resets to 1 day (miss clears all momentum)
    - score 1-3 uses base intervals from _BASE_DAYS
    - 2 consecutive strong (>=2) reviews → floor raised to 30 days
    - 3+ consecutive strong reviews     → floor raised to 60 days
    """
    if now is None:
        now = datetime.now(tz=timezone.utc)

    if score == 0:
        return now + timedelta(days=1)

    base = _BASE_DAYS[score]

    # Include the current (new) score when counting the streak
    tail = _consecutive_strong_tail(history)
    if score >= 2:
        tail += 1

    if tail >= 3:
        days = max(base, _EXT_3_CONSECUTIVE)
    elif tail == 2:
        days = max(base, _EXT_2_CONSECUTIVE)
    else:
        days = base

    return now + timedelta(days=days)


# ---------------------------------------------------------------------------
# Today's picks
# ---------------------------------------------------------------------------

def _as_date(dt: datetime) -> date:
    """Return the UTC date of a datetime regardless of tzinfo."""
    if dt.tzinfo is not None:
        return dt.astimezone(timezone.utc).date()
    return dt.date()


def pick_today(
    problems: list[Problem],
    reviews: list[Review],
    today: Optional[datetime] = None,
    n: int = 3,
) -> list[DailyPick]:
    """
    Select up to n problems for today using a priority waterfall:

      Bucket A — overdue   (next_due < today)      → most overdue first
      Bucket B — due today (next_due == today)      → least recently reviewed first
      Bucket C — long unreviewed (>30d or never)   → oldest first
      Bucket D — reinforcement (recent tag/pattern)→ highest overlap score first

    Fill strategy: drain A → drain B → 1 from C → 1 from D → backfill C → B → D
    """
    if today is None:
        today = datetime.now(tz=timezone.utc)

    today_date = _as_date(today)

    # ------------------------------------------------------------------
    # Build per-problem review index and identify recently active topics
    # ------------------------------------------------------------------
    reviews_by_pid: dict[str, list[Review]] = defaultdict(list)
    for r in reviews:
        reviews_by_pid[r.problem_id].append(r)

    cutoff = today - timedelta(days=_REINFORCEMENT_WINDOW_DAYS)
    recent_tags: Counter[str] = Counter()
    recent_patterns: Counter[str] = Counter()

    for r in reviews:
        reviewed_date = _as_date(r.reviewed_at)
        if reviewed_date >= _as_date(cutoff):
            prob = next((p for p in problems if p.problem_id == r.problem_id), None)
            if prob:
                for tag in prob.tags:
                    recent_tags[tag] += 1
                if prob.pattern:
                    recent_patterns[prob.pattern] += 1

    # ------------------------------------------------------------------
    # Assign each problem to one bucket
    # ------------------------------------------------------------------
    bucket_a: list[tuple[Problem, int]] = []           # (problem, days_overdue)
    bucket_b: list[tuple[Problem, datetime]] = []      # (problem, last_reviewed or created)
    bucket_c: list[tuple[Problem, Optional[date]]] = []  # (problem, last_reviewed date or None)
    bucket_d: list[tuple[Problem, int]] = []           # (problem, reinforcement_score)

    for p in problems:
        if p.next_due_at is None:
            # Never reviewed → long unreviewed
            bucket_c.append((p, None))
            continue

        due_date = _as_date(p.next_due_at)

        if due_date < today_date:
            days_overdue = (today_date - due_date).days
            bucket_a.append((p, days_overdue))

        elif due_date == today_date:
            anchor = p.last_reviewed_at or p.created_at
            bucket_b.append((p, anchor))

        else:
            # Future due — check for long unreviewed or reinforcement
            if p.last_reviewed_at is None:
                bucket_c.append((p, None))
            else:
                days_since = (today_date - _as_date(p.last_reviewed_at)).days
                if days_since >= _LONG_UNREVIEWED_DAYS:
                    bucket_c.append((p, _as_date(p.last_reviewed_at)))
                else:
                    rscore = sum(recent_tags[t] for t in p.tags)
                    if p.pattern:
                        rscore += recent_patterns[p.pattern] * 2
                    if rscore > 0:
                        bucket_d.append((p, rscore))

    # Sort each bucket
    bucket_a.sort(key=lambda x: x[1], reverse=True)       # most overdue first
    bucket_b.sort(key=lambda x: x[1])                      # oldest anchor first
    bucket_c.sort(key=lambda x: (x[1] is not None, x[1])) # None (never) before dated
    bucket_d.sort(key=lambda x: x[1], reverse=True)        # highest overlap first

    # ------------------------------------------------------------------
    # Fill picks
    # ------------------------------------------------------------------
    picks: list[DailyPick] = []
    seen: set[str] = set()

    def _add(problem: Problem, reason: str) -> bool:
        if problem.problem_id not in seen and len(picks) < n:
            picks.append(DailyPick(problem=problem, reason=reason))
            seen.add(problem.problem_id)
            return True
        return False

    def _overdue_label(days: int) -> str:
        return f"overdue {days}d" if days > 1 else "overdue 1d"

    # A: drain overdue
    for p, days in bucket_a:
        if len(picks) >= n:
            break
        _add(p, _overdue_label(days))

    # B: drain due-today
    for p, _ in bucket_b:
        if len(picks) >= n:
            break
        _add(p, "due today")

    # C: include at least one long-unreviewed
    if len(picks) < n:
        for p, _ in bucket_c:
            if _add(p, "long unreviewed"):
                break

    # D: include at least one reinforcement pick
    if len(picks) < n:
        for p, _ in bucket_d:
            label = _reinforcement_label(p)
            if _add(p, label):
                break

    # Backfill: C → D → B (in that priority order)
    for p, _ in bucket_c:
        if len(picks) >= n:
            break
        _add(p, "long unreviewed")

    for p, _ in bucket_d:
        if len(picks) >= n:
            break
        _add(p, _reinforcement_label(p))

    for p, _ in bucket_b:
        if len(picks) >= n:
            break
        _add(p, "due today")

    return picks


def _reinforcement_label(p: Problem) -> str:
    if p.pattern:
        return f"reinforcement: {p.pattern}"
    if p.tags:
        return f"reinforcement: {', '.join(p.tags[:2])}"
    return "reinforcement"
