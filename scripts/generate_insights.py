#!/usr/bin/env python3
"""
Generate one-sentence insights for every LeetCode problem using Claude.

Reads  : src/leetrevive/data/problems_meta.json
Writes : src/leetrevive/data/insights.json   { "1": "Use a hash map ...", ... }

Usage:
    python scripts/generate_insights.py                  # all problems
    python scripts/generate_insights.py --limit 200      # first 200 by ID
    python scripts/generate_insights.py --resume         # skip already-done

Requires:  ANTHROPIC_API_KEY env var
           pip install anthropic
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path

try:
    import anthropic
except ImportError:
    sys.exit("Run:  pip install anthropic")

ROOT      = Path(__file__).parent.parent
META_FILE = ROOT / "src" / "leetrevive" / "data" / "problems_meta.json"
OUT_FILE  = ROOT / "src" / "leetrevive" / "data" / "insights.json"

BATCH_SIZE  = 50     # problems per API call
MODEL       = "claude-haiku-4-5"   # fast + cheap for bulk generation
RETRY_WAIT  = 5      # seconds between retries on rate-limit


SYSTEM_PROMPT = """\
You are a concise algorithm tutor. For each LeetCode problem given, write exactly
ONE sentence (≤ 20 words) capturing the single most important algorithmic insight
a student needs to solve it from memory.

Rules:
- Focus on the KEY TRICK or DATA STRUCTURE, not the problem statement.
- Be concrete: name the pattern (e.g. "sliding window", "two pointers", "min-heap").
- Do NOT start with "Use" every time — vary the opening.
- Return ONLY a JSON object mapping problem_id (string) → insight (string).
- No markdown, no explanation, no trailing text.

Example output:
{"1":"Store each number's complement in a hash map for an O(n) single-pass solution.",
 "2":"Simulate digit addition with a carry variable, iterating both lists simultaneously."}
"""


def build_user_prompt(batch: list[dict]) -> str:
    lines = []
    for p in batch:
        tags = ", ".join(p["tags"][:4]) if p["tags"] else "none"
        lines.append(f'{p["id"]}. [{p["difficulty"].upper()}] {p["title"]}  tags: {tags}')
    return "Generate insights for these problems:\n" + "\n".join(lines)


def call_api(client: anthropic.Anthropic, batch: list[dict]) -> dict[str, str]:
    for attempt in range(3):
        try:
            msg = client.messages.create(
                model=MODEL,
                max_tokens=2048,
                system=SYSTEM_PROMPT,
                messages=[{"role": "user", "content": build_user_prompt(batch)}],
            )
            text = msg.content[0].text.strip()
            # Strip any accidental markdown fencing
            if text.startswith("```"):
                text = text.split("```")[1]
                if text.startswith("json"):
                    text = text[4:]
            return json.loads(text)
        except json.JSONDecodeError as e:
            print(f"  [warn] JSON parse error (attempt {attempt+1}): {e}", flush=True)
            time.sleep(2)
        except anthropic.RateLimitError:
            print(f"  [rate-limit] waiting {RETRY_WAIT}s…", flush=True)
            time.sleep(RETRY_WAIT)
        except anthropic.APIError as e:
            print(f"  [api-error] {e} (attempt {attempt+1})", flush=True)
            time.sleep(2)
    return {}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit",  type=int, default=0,     help="Only process first N problems (0=all)")
    parser.add_argument("--resume", action="store_true",      help="Skip problem IDs already in insights.json")
    parser.add_argument("--batch",  type=int, default=BATCH_SIZE, help=f"API batch size (default {BATCH_SIZE})")
    args = parser.parse_args()

    api_key   = os.environ.get("ANTHROPIC_API_KEY")
    oauth_tok = os.environ.get("CLAUDE_CODE_OAUTH_TOKEN")

    if not api_key and not oauth_tok:
        sys.exit("Set ANTHROPIC_API_KEY (or CLAUDE_CODE_OAUTH_TOKEN) first.")

    if api_key:
        client = anthropic.Anthropic(api_key=api_key)
    else:
        # Claude Code OAuth token — passed as Bearer in Authorization header
        client = anthropic.Anthropic(
            api_key="dummy",
            default_headers={"Authorization": f"Bearer {oauth_tok}"},
        )

    meta: dict[str, dict] = json.loads(META_FILE.read_text())

    # Load existing insights if resuming
    existing: dict[str, str] = {}
    if args.resume and OUT_FILE.exists():
        existing = json.loads(OUT_FILE.read_text())
        print(f"Resuming — {len(existing)} insights already generated.", flush=True)

    # Sort by numeric problem ID
    problems = sorted(
        [{"id": k, **v} for k, v in meta.items()],
        key=lambda p: int(p["id"]) if p["id"].isdigit() else 9999,
    )
    if args.limit:
        problems = problems[:args.limit]

    # Skip already-done when resuming
    if args.resume:
        problems = [p for p in problems if p["id"] not in existing]

    total   = len(problems)
    results = dict(existing)
    batches = [problems[i:i + args.batch] for i in range(0, total, args.batch)]

    print(f"Generating insights for {total} problems in {len(batches)} batches (model={MODEL})…", flush=True)

    for i, batch in enumerate(batches):
        ids = [p["id"] for p in batch]
        print(f"  Batch {i+1}/{len(batches)}: problems {ids[0]}–{ids[-1]}…", end=" ", flush=True)
        t0 = time.time()
        chunk = call_api(client, batch)
        elapsed = time.time() - t0
        results.update(chunk)
        print(f"got {len(chunk)} insights  ({elapsed:.1f}s)", flush=True)

        # Write incrementally so a crash doesn't lose work
        OUT_FILE.write_text(json.dumps(results, indent=2, ensure_ascii=False))

        # Polite delay between batches
        if i < len(batches) - 1:
            time.sleep(0.5)

    print(f"\nDone. {len(results)} total insights written to {OUT_FILE}")
    missing = [p["id"] for p in problems if p["id"] not in results]
    if missing:
        print(f"Missing {len(missing)} problems: {missing[:10]}{'…' if len(missing)>10 else ''}")


if __name__ == "__main__":
    main()
