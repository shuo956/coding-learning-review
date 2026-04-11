from __future__ import annotations

"""
FastAPI server for the leetrevive web UI.

Exposes:
  GET  /                      → serves index.html
  GET  /api/today             → today's 3 picks
  POST /api/done              → record a review attempt
  GET  /api/graph             → knowledge graph (nodes + edges)
  PUT  /api/notes/{key}       → upsert a knowledge-node insight
  GET  /api/bank              → all problems (for sidebar)
  GET  /api/stats             → overview counts
"""

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

# ---------------------------------------------------------------------------
# App setup
# ---------------------------------------------------------------------------

app = FastAPI(title="leetrevive", docs_url=None, redoc_url=None)

_STATIC = Path(__file__).parent / "static"
app.mount("/static", StaticFiles(directory=str(_STATIC)), name="static")


@app.get("/", include_in_schema=False)
def root() -> FileResponse:
    return FileResponse(str(_STATIC / "index.html"))


# ---------------------------------------------------------------------------
# /api/today
# ---------------------------------------------------------------------------

@app.get("/api/today")
def api_today() -> dict:
    problems = db.get_all_problems()
    reviews  = db.get_all_reviews()
    picks    = pick_today(problems, reviews, datetime.now(tz=timezone.utc))
    return {
        "picks": [
            {
                "problem_id":       p.problem.problem_id,
                "title":            p.problem.title,
                "difficulty":       p.problem.difficulty,
                "tags":             p.problem.tags,
                "pattern":          p.problem.pattern,
                "url":              p.problem.url,
                "insight":          get_insight(p.problem.problem_id),
                "reason":           p.reason,
                "last_reviewed_at": _fmt_dt(p.problem.last_reviewed_at),
                "next_due_at":      _fmt_dt(p.problem.next_due_at),
            }
            for p in picks
        ]
    }


# ---------------------------------------------------------------------------
# /api/done
# ---------------------------------------------------------------------------

class DoneRequest(BaseModel):
    problem_id: str
    score: int                    # 0-3
    minutes: Optional[int] = None
    note: Optional[str]    = None
    mistake: Optional[str] = None


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
    review  = Review(
        problem_id=body.problem_id,
        reviewed_at=now,
        score=body.score,
        minutes=body.minutes,
        note=body.note,
        mistake=body.mistake,
    )
    db.insert_review(review)
    next_due = _sched.compute_next_due(body.score, history, now)
    db.update_problem_review(body.problem_id, now, next_due)

    return {
        "ok":            True,
        "next_due_at":   next_due.strftime("%Y-%m-%d"),
        "review_count":  len(history) + 1,
    }


# ---------------------------------------------------------------------------
# /api/graph  —  DS&A curriculum skeleton + user mastery overlay
# ---------------------------------------------------------------------------

_MASTERY_THRESHOLDS = {"strong": 2.0, "developing": 1.0}

def _mastery(avg: Optional[float]) -> str:
    if avg is None:
        return "unreviewed"
    if avg >= _MASTERY_THRESHOLDS["strong"]:
        return "strong"
    if avg >= _MASTERY_THRESHOLDS["developing"]:
        return "developing"
    return "weak"


# ---------------------------------------------------------------------------
# Interview-focused curriculum map
#
# Two design axes:
#   tier  = learning prerequisite order (1 = first, 3 = advanced)
#   freq  = interview frequency weight (1-5, 5 = asked at every company)
#
# Tier 1 — Foundation (Blind 75 / NeetCode 150 core)
# Tier 2 — Strong signal (FAANG standard rounds)
# Tier 3 — Differentiators (senior / hard rounds)
# ---------------------------------------------------------------------------

_CURRICULUM_NODES: list[dict] = [
    # ── Tier 1: Foundation ─────────────────────────────────────────────────
    {
        "id": "arrays-hashing", "label": "Arrays & Hashing",
        "group": "tier1", "tier": 1, "freq": 5,
        "note": "Master frequency maps and index tricks — the base of ~30% of all interview problems.",
    },
    {
        "id": "pattern:two-pointers", "label": "⚡ Two Pointers",
        "group": "tier1", "tier": 1, "freq": 5,
        "note": "Move left/right pointers toward each other on a sorted array to avoid O(n²) brute force.",
    },
    {
        "id": "pattern:sliding-window", "label": "⚡ Sliding Window",
        "group": "tier1", "tier": 1, "freq": 5,
        "note": "Expand right to grow the window; shrink left when the constraint breaks.",
    },
    {
        "id": "stack", "label": "Stack",
        "group": "tier1", "tier": 1, "freq": 4,
        "note": "LIFO for bracket matching, monotonic sequences, and iterative DFS.",
    },
    {
        "id": "pattern:binary-search", "label": "⚡ Binary Search",
        "group": "tier1", "tier": 1, "freq": 5,
        "note": "Apply to any monotonic search space — not just sorted arrays.",
    },
    {
        "id": "linked-list", "label": "Linked List",
        "group": "tier1", "tier": 1, "freq": 4,
        "note": "Dummy head + slow/fast pointers solve most linked-list problems cleanly.",
    },
    {
        "id": "binary-tree", "label": "Trees (Binary)",
        "group": "tier1", "tier": 1, "freq": 5,
        "note": "Most tree problems are recursive DFS; inorder traversal gives sorted order on BSTs.",
    },
    {
        "id": "heap-priority-queue", "label": "Heap / Priority Queue",
        "group": "tier1", "tier": 1, "freq": 4,
        "note": "Min/max in O(log n) — essential for top-k, merge-k-lists, and scheduling problems.",
    },

    # ── Tier 2: FAANG Standard ─────────────────────────────────────────────
    {
        "id": "pattern:backtracking", "label": "⚡ Backtracking",
        "group": "tier2", "tier": 2, "freq": 4,
        "note": "Build candidates incrementally; prune branches that cannot yield a valid solution.",
    },
    {
        "id": "tries", "label": "Tries",
        "group": "tier2", "tier": 2, "freq": 3,
        "note": "Prefix tree for word search and autocomplete; each node stores a char and children map.",
    },
    {
        "id": "graphs", "label": "Graphs (BFS/DFS)",
        "group": "tier2", "tier": 2, "freq": 5,
        "note": "BFS for shortest path, DFS for connectivity; always track visited to avoid cycles.",
    },
    {
        "id": "pattern:dp-1d", "label": "⚡ 1-D Dynamic Prog.",
        "group": "tier2", "tier": 2, "freq": 5,
        "note": "Define a dp[i] state, write the recurrence, and handle base cases first.",
    },
    {
        "id": "pattern:dp-2d", "label": "⚡ 2-D Dynamic Prog.",
        "group": "tier2", "tier": 2, "freq": 4,
        "note": "dp[i][j] typically means 'best answer using first i of X and first j of Y'.",
    },
    {
        "id": "pattern:intervals", "label": "⚡ Intervals",
        "group": "tier2", "tier": 2, "freq": 4,
        "note": "Sort by start time; merge overlapping intervals when next.start ≤ prev.end.",
    },
    {
        "id": "pattern:greedy", "label": "⚡ Greedy",
        "group": "tier2", "tier": 2, "freq": 3,
        "note": "Make the locally optimal choice at each step; prove it leads to a global optimum.",
    },

    # ── Tier 3: Differentiators ────────────────────────────────────────────
    {
        "id": "advanced-graphs", "label": "Advanced Graphs",
        "group": "tier3", "tier": 3, "freq": 3,
        "note": "Dijkstra for weighted shortest path, Topological sort for DAG ordering, Union-Find for components.",
    },
    {
        "id": "pattern:dp-intervals", "label": "⚡ DP on Intervals",
        "group": "tier3", "tier": 3, "freq": 2,
        "note": "dp[i][j] = optimal answer on subarray [i..j]; fill by increasing interval length.",
    },
    {
        "id": "pattern:bit-manip", "label": "⚡ Bit Manipulation",
        "group": "tier3", "tier": 3, "freq": 2,
        "note": "XOR cancels duplicates; use masks and shifts for compact state in bitmask DP.",
    },
    {
        "id": "pattern:math-geometry", "label": "⚡ Math & Geometry",
        "group": "tier3", "tier": 3, "freq": 2,
        "note": "Recognize modular arithmetic, GCD patterns, and coordinate rotation tricks.",
    },
    {
        "id": "pattern:monotonic-stack", "label": "⚡ Monotonic Stack",
        "group": "tier3", "tier": 3, "freq": 3,
        "note": "Maintain a stack in sorted order to find next-greater or previous-smaller in O(n).",
    },
]

# Prerequisite / learning-order edges (from prerequisite → unlocks)
_CURRICULUM_EDGES: list[dict] = [
    # Tier 1 internal order
    {"from": "arrays-hashing",          "to": "pattern:two-pointers"},
    {"from": "arrays-hashing",          "to": "pattern:sliding-window"},
    {"from": "arrays-hashing",          "to": "pattern:binary-search"},
    {"from": "pattern:two-pointers",    "to": "linked-list"},
    {"from": "pattern:sliding-window",  "to": "stack"},
    {"from": "stack",                   "to": "binary-tree"},
    {"from": "binary-tree",             "to": "heap-priority-queue"},

    # Tier 1 → Tier 2 unlocks
    {"from": "binary-tree",             "to": "pattern:backtracking"},
    {"from": "binary-tree",             "to": "tries"},
    {"from": "binary-tree",             "to": "graphs"},
    {"from": "heap-priority-queue",     "to": "pattern:greedy"},
    {"from": "pattern:binary-search",   "to": "pattern:dp-1d"},
    {"from": "pattern:dp-1d",           "to": "pattern:dp-2d"},
    {"from": "pattern:dp-1d",           "to": "pattern:intervals"},

    # Tier 2 → Tier 3 unlocks
    {"from": "graphs",                  "to": "advanced-graphs"},
    {"from": "pattern:dp-2d",           "to": "pattern:dp-intervals"},
    {"from": "pattern:backtracking",    "to": "pattern:bit-manip"},
    {"from": "stack",                   "to": "pattern:monotonic-stack"},
    {"from": "pattern:greedy",          "to": "pattern:math-geometry"},
]

# Build a set of curriculum node ids for fast lookup
_CURRICULUM_IDS = {n["id"] for n in _CURRICULUM_NODES}


@app.get("/api/graph")
def api_graph() -> dict:
    problems = db.get_all_problems()
    reviews  = db.get_all_reviews()
    notes    = db.get_all_notes()

    # avg score per problem
    scores_by_pid: dict[str, list[int]] = defaultdict(list)
    for r in reviews:
        scores_by_pid[r.problem_id].append(r.score)

    # Build user mastery per key (tag / pattern:xxx)
    key_pids: dict[str, list[str]] = defaultdict(list)
    for p in problems:
        for tag in p.tags:
            key_pids[tag].append(p.problem_id)
        if p.pattern:
            key_pids[f"pattern:{p.pattern}"].append(p.problem_id)

    def _node_mastery_and_count(key: str) -> tuple:
        pids = key_pids.get(key, [])
        all_scores = [s for pid in pids for s in scores_by_pid.get(pid, [])]
        avg = sum(all_scores) / len(all_scores) if all_scores else None
        return _mastery(avg), (round(avg, 2) if avg is not None else None), pids

    # Start from curriculum skeleton — always shown
    nodes = []
    seen_ids: set[str] = set()

    for cn in _CURRICULUM_NODES:
        key = cn["id"]
        mastery, avg, pids = _node_mastery_and_count(key)
        is_pattern = key.startswith("pattern:")
        nodes.append({
            "id":            key,
            "label":         cn["label"],
            "is_pattern":    is_pattern,
            "group":         cn["group"],
            "tier":          cn.get("tier"),
            "freq":          cn.get("freq"),
            "mastery":       mastery,
            "avg_score":     avg,
            "problem_count": len(pids),
            "problem_ids":   pids,
            # Saved note wins; fall back to curriculum default insight
            "note":          notes.get(key, cn.get("note", "")),
        })
        seen_ids.add(key)

    # Add any user tags/patterns NOT already in the curriculum
    for key, pids in key_pids.items():
        if key in seen_ids:
            continue
        all_scores = [s for pid in pids for s in scores_by_pid.get(pid, [])]
        avg = sum(all_scores) / len(all_scores) if all_scores else None
        is_pattern = key.startswith("pattern:")
        label = ("⚡ " + key[len("pattern:"):]) if is_pattern else key
        nodes.append({
            "id":            key,
            "label":         label,
            "is_pattern":    is_pattern,
            "group":         "user",
            "mastery":       _mastery(avg),
            "avg_score":     round(avg, 2) if avg is not None else None,
            "problem_count": len(pids),
            "problem_ids":   pids,
            "note":          notes.get(key, ""),
        })
        seen_ids.add(key)

    # Edges: curriculum skeleton + user co-occurrence edges
    edge_set: set[tuple[str, str]] = set()
    edges = list(_CURRICULUM_EDGES)
    for e in _CURRICULUM_EDGES:
        edge_set.add((min(e["from"], e["to"]), max(e["from"], e["to"])))

    for p in problems:
        keys = list(p.tags) + ([f"pattern:{p.pattern}"] if p.pattern else [])
        for i, a in enumerate(keys):
            for b in keys[i + 1:]:
                ek = (min(a, b), max(a, b))
                if ek not in edge_set:
                    edge_set.add(ek)
                    edges.append({"from": a, "to": b})

    return {"nodes": nodes, "edges": edges}


# ---------------------------------------------------------------------------
# /api/notes
# ---------------------------------------------------------------------------

class NoteRequest(BaseModel):
    note: str


@app.put("/api/notes/{key:path}")
def api_upsert_note(key: str, body: NoteRequest) -> dict:
    db.upsert_note(key, body.note)
    return {"ok": True, "key": key, "note": body.note}


# ---------------------------------------------------------------------------
# /api/bank
# ---------------------------------------------------------------------------

@app.get("/api/bank")
def api_bank() -> dict:
    problems = db.get_all_problems()
    reviews  = db.get_all_reviews()

    scores_by_pid: dict[str, list[int]] = defaultdict(list)
    for r in reviews:
        scores_by_pid[r.problem_id].append(r.score)

    return {
        "problems": [
            {
                "problem_id":       p.problem_id,
                "title":            p.title,
                "difficulty":       p.difficulty,
                "tags":             p.tags,
                "pattern":          p.pattern,
                "url":              p.url,
                "insight":          get_insight(p.problem_id),
                "last_reviewed_at": _fmt_dt(p.last_reviewed_at),
                "next_due_at":      _fmt_dt(p.next_due_at),
                "review_count":     len(scores_by_pid.get(p.problem_id, [])),
                "avg_score":        (
                    round(sum(scores_by_pid[p.problem_id]) / len(scores_by_pid[p.problem_id]), 1)
                    if scores_by_pid.get(p.problem_id) else None
                ),
            }
            for p in problems
        ]
    }


# ---------------------------------------------------------------------------
# /api/stats
# ---------------------------------------------------------------------------

@app.get("/api/stats")
def api_stats() -> dict:
    problems = db.get_all_problems()
    reviews  = db.get_all_reviews()
    now      = datetime.now(tz=timezone.utc)
    today    = now.date()

    due_today = sum(
        1 for p in problems
        if p.next_due_at and p.next_due_at.date() == today
    )
    overdue = sum(
        1 for p in problems
        if p.next_due_at and p.next_due_at.date() < today
    )

    return {
        "total_problems": len(problems),
        "total_reviews":  len(reviews),
        "due_today":      due_today,
        "overdue":        overdue,
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

    # Already in bank?
    if db.get_problem(pid):
        raise HTTPException(status_code=409, detail=f"Problem {pid} already in bank")

    # Fill from bundled meta if not provided
    meta = meta_lookup(pid)
    title      = body.title      or (meta.title      if meta else None)
    difficulty = body.difficulty or (meta.difficulty if meta else None)
    url        = body.url        or (meta.url        if meta else f"https://leetcode.com/problems/{pid}/")

    if not title:
        raise HTTPException(status_code=404, detail=f"Problem {pid} not found in metadata — provide a title")

    from datetime import timezone
    now = datetime.now(tz=timezone.utc)
    problem = Problem(
        problem_id=pid,
        title=title,
        difficulty=difficulty or "medium",
        tags=meta.tags if meta else [],
        pattern=None,
        source="web",
        url=url,
        created_at=now,
    )
    db.insert_problem(problem)
    return {
        "ok":         True,
        "problem_id": pid,
        "title":      title,
        "difficulty": difficulty or "medium",
        "url":        url,
        "insight":    get_insight(pid),
    }


# ---------------------------------------------------------------------------
# /api/search  — meta lookup without adding to bank
# ---------------------------------------------------------------------------

@app.get("/api/search/{problem_id}")
def api_search(problem_id: str) -> dict:
    meta = meta_lookup(problem_id)
    if not meta:
        raise HTTPException(status_code=404, detail=f"Problem {problem_id} not in bundled metadata")
    in_bank = db.get_problem(problem_id) is not None
    return {
        "problem_id": meta.problem_id,
        "title":      meta.title,
        "difficulty": meta.difficulty,
        "tags":       meta.tags,
        "url":        meta.url,
        "insight":    get_insight(problem_id),
        "in_bank":    in_bank,
    }


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _fmt_dt(dt: Optional[datetime]) -> Optional[str]:
    if dt is None:
        return None
    return dt.strftime("%Y-%m-%d")
