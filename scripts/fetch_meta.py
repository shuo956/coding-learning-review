#!/usr/bin/env python3
"""
Fetch all LeetCode problem metadata from LeetCode's GraphQL API
and write it to src/leetrevive/data/problems_meta.json.

Run once at release time:
    python scripts/fetch_meta.py

Requires: requests  (pip install requests)
No authentication needed — uses LeetCode's public API.
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

try:
    import requests
except ImportError:
    sys.exit("Install requests first:  pip install requests")

OUTPUT = Path(__file__).parent.parent / "src" / "leetrevive" / "data" / "problems_meta.json"

GRAPHQL_URL = "https://leetcode.com/graphql"
PAGE_SIZE = 100

QUERY = """
query problemList($skip: Int, $limit: Int) {
  problemsetQuestionList: questionList(
    categorySlug: ""
    limit: $limit
    skip: $skip
    filters: {}
  ) {
    total: totalNum
    questions: data {
      questionFrontendId
      title
      titleSlug
      difficulty
      topicTags {
        slug
      }
      isPaidOnly
    }
  }
}
"""

HEADERS = {
    "Content-Type": "application/json",
    "Referer": "https://leetcode.com/problemset/",
    "User-Agent": "Mozilla/5.0",
}


def fetch_page(skip: int) -> dict:
    payload = {"query": QUERY, "variables": {"skip": skip, "limit": PAGE_SIZE}}
    resp = requests.post(GRAPHQL_URL, json=payload, headers=HEADERS, timeout=15)
    resp.raise_for_status()
    return resp.json()


def main() -> None:
    print("Fetching problem list from LeetCode GraphQL...", flush=True)

    # Fetch first page to get total count
    data = fetch_page(0)
    pset = data["data"]["problemsetQuestionList"]
    total = pset["total"]
    print(f"Total problems: {total}", flush=True)

    all_questions = list(pset["questions"])

    # Paginate through the rest
    skip = PAGE_SIZE
    while skip < total:
        print(f"  fetching {skip}/{total}...", end="\r", flush=True)
        page = fetch_page(skip)
        all_questions.extend(page["data"]["problemsetQuestionList"]["questions"])
        skip += PAGE_SIZE
        time.sleep(0.3)  # be polite to LeetCode's servers

    print(f"\nFetched {len(all_questions)} problems.", flush=True)

    # Build the lookup dict keyed by frontend problem ID (string)
    meta: dict[str, dict] = {}
    for q in all_questions:
        pid = q["questionFrontendId"]
        # Skip problems with non-numeric IDs (rare edge cases)
        if not pid.isdigit():
            continue
        meta[pid] = {
            "title": q["title"],
            "slug": q["titleSlug"],
            "difficulty": q["difficulty"].lower(),
            "tags": [t["slug"] for t in q["topicTags"]],
            "url": f"https://leetcode.com/problems/{q['titleSlug']}/",
            "paid": q["isPaidOnly"],
        }

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(meta, indent=2, ensure_ascii=False))
    print(f"Written to {OUTPUT}  ({OUTPUT.stat().st_size // 1024} KB)")


if __name__ == "__main__":
    main()
