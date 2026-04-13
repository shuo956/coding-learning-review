from __future__ import annotations

"""
FastAPI server for the leetrevive web UI.

Endpoints:
  GET  /                       → serves index.html
  GET  /api/today              → today's 3 spaced-repetition picks
  POST /api/done               → record a review attempt
  GET  /api/bank               → all problems in the bank
  GET  /api/stats              → overview counts
  GET  /api/search/{id}        → metadata preview (not yet in bank)
  POST /api/add                → add a problem to the bank
  GET  /api/mock               → random sample for mock interview
"""

import random
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from .. import db
from ..meta import get_insight, lookup as meta_lookup
from ..models import Problem
from ..scheduler import pick_today

app = FastAPI(title="leetrevive", docs_url=None, redoc_url=None)

_STATIC = Path(__file__).parent / "static"
app.mount("/static", StaticFiles(directory=str(_STATIC)), name="static")


@app.get("/", include_in_schema=False)
def root() -> FileResponse:
    return FileResponse(str(_STATIC / "index.html"))


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _fmt_dt(dt: Optional[datetime]) -> Optional[str]:
    return dt.strftime("%Y-%m-%d") if dt is not None else None


def _scores_by_pid(reviews: list) -> dict[str, list[int]]:
    result: dict[str, list[int]] = defaultdict(list)
    for r in reviews:
        result[r.problem_id].append(r.score)
    return result


def _serialize_problem(p, scores: list[int]) -> dict:
    return {
        "problem_id":       p.problem_id,
        "title":            p.title,
        "difficulty":       p.difficulty,
        "tags":             p.tags,
        "pattern":          p.pattern,
        "url":              p.url,
        "insight":          get_insight(p.problem_id),
        "last_reviewed_at": _fmt_dt(p.last_reviewed_at),
        "next_due_at":      _fmt_dt(p.next_due_at),
        "review_count":     len(scores),
        "avg_score":        round(sum(scores) / len(scores), 1) if scores else None,
    }


# ---------------------------------------------------------------------------
# /api/today
# ---------------------------------------------------------------------------

@app.get("/api/today")
def api_today() -> dict:
    problems = db.get_all_problems()
    reviews  = db.get_all_reviews()
    picks    = pick_today(problems, reviews, datetime.now(tz=timezone.utc))
    sbp      = _scores_by_pid(reviews)
    return {
        "picks": [
            {
                **_serialize_problem(p.problem, sbp.get(p.problem.problem_id, [])),
                "reason": p.reason,
            }
            for p in picks
        ]
    }


# ---------------------------------------------------------------------------
# /api/done
# ---------------------------------------------------------------------------

class DoneRequest(BaseModel):
    problem_id: str
    score:      int
    minutes:    Optional[int] = None
    note:       Optional[str] = None
    mistake:    Optional[str] = None


@app.post("/api/done")
def api_done(body: DoneRequest) -> dict:
    if body.score not in (0, 1, 2, 3):
        raise HTTPException(status_code=422, detail="score must be 0-3")

    problem = db.get_problem(body.problem_id)
    if not problem:
        raise HTTPException(status_code=404, detail=f"Problem {body.problem_id!r} not found")

    from .. import scheduler as _sched
    from ..models import Review

    now     = datetime.now(tz=timezone.utc)
    history = db.get_reviews(body.problem_id)
    db.insert_review(Review(
        problem_id=body.problem_id,
        reviewed_at=now,
        score=body.score,
        minutes=body.minutes,
        note=body.note,
        mistake=body.mistake,
    ))
    next_due = _sched.compute_next_due(body.score, history, now)
    db.update_problem_review(body.problem_id, now, next_due)

    return {
        "ok":           True,
        "next_due_at":  next_due.strftime("%Y-%m-%d"),
        "review_count": len(history) + 1,
    }


# ---------------------------------------------------------------------------
# /api/bank
# ---------------------------------------------------------------------------

@app.get("/api/bank")
def api_bank() -> dict:
    problems = db.get_all_problems()
    sbp      = _scores_by_pid(db.get_all_reviews())
    return {
        "problems": [
            _serialize_problem(p, sbp.get(p.problem_id, []))
            for p in problems
        ]
    }


# ---------------------------------------------------------------------------
# /api/stats
# ---------------------------------------------------------------------------

@app.get("/api/stats")
def api_stats() -> dict:
    problems = db.get_all_problems()
    today    = datetime.now(tz=timezone.utc).date()
    return {
        "total_problems": len(problems),
        "total_reviews":  db.count_reviews(),
        "due_today":      sum(1 for p in problems if p.next_due_at and p.next_due_at.date() == today),
        "overdue":        sum(1 for p in problems if p.next_due_at and p.next_due_at.date() < today),
    }


# ---------------------------------------------------------------------------
# /api/search/{problem_id}  — metadata preview (does not add to bank)
# ---------------------------------------------------------------------------

@app.get("/api/search/{problem_id}")
def api_search(problem_id: str) -> dict:
    meta = meta_lookup(problem_id)
    if not meta:
        raise HTTPException(status_code=404, detail=f"Problem {problem_id} not in bundled metadata")
    return {
        "problem_id": meta.problem_id,
        "title":      meta.title,
        "difficulty": meta.difficulty,
        "tags":       meta.tags,
        "url":        meta.url,
        "insight":    get_insight(problem_id),
        "in_bank":    db.get_problem(problem_id) is not None,
    }


# ---------------------------------------------------------------------------
# /api/add
# ---------------------------------------------------------------------------

class AddRequest(BaseModel):
    problem_id: str
    title:      Optional[str] = None
    difficulty: Optional[str] = None
    url:        Optional[str] = None


@app.post("/api/add")
def api_add(body: AddRequest) -> dict:
    pid = body.problem_id.strip()
    if not pid:
        raise HTTPException(status_code=422, detail="problem_id required")
    if db.get_problem(pid):
        raise HTTPException(status_code=409, detail=f"Problem {pid} already in bank")

    meta       = meta_lookup(pid)
    title      = body.title      or (meta.title      if meta else None)
    difficulty = body.difficulty or (meta.difficulty if meta else None)
    url        = body.url        or (meta.url        if meta else f"https://leetcode.com/problems/{pid}/")

    if not title:
        raise HTTPException(status_code=404, detail=f"Problem {pid} not found in metadata — provide a title")

    db.insert_problem(Problem(
        problem_id=pid,
        title=title,
        difficulty=difficulty or "medium",
        tags=meta.tags if meta else [],
        pattern=None,
        source="web",
        url=url,
        created_at=datetime.now(tz=timezone.utc),
    ))
    return {
        "ok":         True,
        "problem_id": pid,
        "title":      title,
        "difficulty": difficulty or "medium",
        "url":        url,
        "insight":    get_insight(pid),
    }


# ---------------------------------------------------------------------------
# /api/mock  — random sample for mock interview mode
# ---------------------------------------------------------------------------

@app.get("/api/mock")
def api_mock(count: int = 3, difficulty: str = "all") -> dict:
    problems = db.get_all_problems()
    if difficulty != "all":
        problems = [p for p in problems if p.difficulty == difficulty]
    if not problems:
        raise HTTPException(status_code=404, detail="No problems match the selected difficulty")
    picked = random.sample(problems, min(count, len(problems)))
    # Insights intentionally omitted — this is a test environment
    return {
        "problems": [
            {
                "problem_id": p.problem_id,
                "title":      p.title,
                "difficulty": p.difficulty,
                "tags":       p.tags,
                "url":        p.url,
            }
            for p in picked
        ]
    }
