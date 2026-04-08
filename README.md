# leetrevive

A terminal-first, local-first LeetCode review assistant.

`leetrevive` helps you build and maintain a personal problem bank, schedules daily review sessions using spaced repetition, and opens the original LeetCode problem in your browser — no problem statements scraped, no accounts, no server.

```
$ leetrevive today

  Today's Review — 2024-06-15
 ┏━━━┳━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━┳━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━━┓
 ┃ # ┃ ID    ┃ Title                   ┃ Diff     ┃ Due          ┃ Reason                 ┃
 ┡━━━╇━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━╇━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━━━┩
 │ 1 │ 23    │ Merge K Sorted Lists    │ Hard     │ overdue 3d   │ overdue 3d             │
 │ 2 │ 1     │ Two Sum                 │ Easy     │ today        │ due today              │
 │ 3 │ 300   │ Longest Increasing Sub  │ Medium   │ in 5d        │ reinforcement: dp      │
 └───┴───────┴─────────────────────────┴──────────┴──────────────┴────────────────────────┘

Tip: leetrevive open <id> to open in browser  •  leetrevive done <id> to record a review
```

---

## Why leetrevive?

Most people grind LeetCode problems once and move on. A week later, they can't solve the same problem from scratch.

`leetrevive` treats your solved problems as a review bank. It schedules which problems to revisit each day, prioritises the ones you're weakest on, and surfaces problems you haven't seen in a while — so your knowledge actually sticks.

It does **not** scrape or bundle LeetCode problem statements. When you want to re-attempt a problem, it opens the original URL in your browser. This keeps the tool lightweight, legally clean, and always up to date.

---

## Features

- **Daily picks** — exactly 3 problems every day, chosen by priority: overdue first, then long-unreviewed, then reinforcement from recent activity
- **Spaced repetition** — interval grows as you score cleanly; a blank resets the clock
- **Review history** — per-problem notes, mistake log, score trend
- **Weak-spot tracking** — `stats` surfaces your weakest patterns and tags by average score
- **Bank with filters** — filter by tag, pattern, due date, or weakness
- **Browser jump** — `open` launches the original LeetCode URL; no mirrored content
- **Fully local** — SQLite database in your system data directory; nothing leaves your machine
- **Fast** — all commands respond in milliseconds

---

## Installation

Requires Python 3.10+.

**From PyPI** *(once published)*:
```bash
pip install leetrevive
```

**From source**:
```bash
git clone https://github.com/yourname/leetrevive
cd leetrevive
pip install .
```

**For development**:
```bash
pip install -e ".[dev]"
pytest   # 58 tests, all green
```

---

## Quickstart

```bash
# 1. Initialise the local database (run once)
leetrevive init

# 2. Add problems you have already solved
leetrevive add 1   "Two Sum"                        --difficulty easy   --tags "array,hashmap"      --pattern "hashmap"
leetrevive add 146 "LRU Cache"                      --difficulty medium --tags "hashmap,linked-list" --pattern "design"
leetrevive add 23  "Merge K Sorted Lists"           --difficulty hard   --tags "heap,linked-list"   --pattern "heap"
leetrevive add 300 "Longest Increasing Subsequence" --difficulty medium --tags "dp"                 --pattern "dp"

# 3. See today's recommended problems
leetrevive today

# 4. Open a problem in your browser and re-attempt it
leetrevive open 1

# 5. Record how it went
leetrevive done 1 --score 3 --minutes 12 --note "clean two-pass solution"

# 6. Check your progress
leetrevive stats
```

---

## Commands

### `init`
Initialise the local data directory and SQLite database. Safe to run multiple times.

```bash
leetrevive init
```

---

### `add <id> <title>`
Add a solved problem to your bank.

```bash
leetrevive add 56 "Merge Intervals" \
  --difficulty medium \
  --tags "array,sorting" \
  --pattern "intervals"
```

| Flag | Default | Description |
|---|---|---|
| `--difficulty` | — | `easy` / `medium` / `hard` |
| `--tags` | — | Comma-separated, e.g. `"array,hashmap"` |
| `--pattern` | — | Algorithm pattern, e.g. `"sliding-window"` |
| `--url` | Auto-generated | Defaults to `https://leetcode.com/problems/<slug>/` |
| `--source` | `leetcode` | Problem source label |

---

### `done <id>`
Record a review attempt. Updates the next due date automatically.

```bash
leetrevive done 56 --score 2 --minutes 20 --mistake "forgot to sort first"
```

| Score | Meaning |
|---|---|
| `0` | Blank — couldn't start |
| `1` | Partial — got the idea, couldn't finish |
| `2` | Struggled — solved it but slowly or with hints |
| `3` | Clean — solved from memory without issues |

`--score` is prompted interactively if omitted.

---

### `today`
Print the 3 recommended problems for today with a reason for each pick.

```bash
leetrevive today
```

---

### `bank`
Browse your review bank with optional filters.

```bash
leetrevive bank                       # all problems
leetrevive bank --due                 # due or overdue only
leetrevive bank --weak                # avg score < 1.5 or never reviewed
leetrevive bank --tag "dp"
leetrevive bank --pattern "sliding-window"
leetrevive bank --limit 50
```

---

### `review <id>`
Show full metadata and complete review history for one problem.

```bash
leetrevive review 146
```

---

### `open <id>`
Open the original problem URL in your default browser.

```bash
leetrevive open 23
```

---

### `stats`
Show overall progress and weak spots.

```bash
leetrevive stats
```

Includes: total problems and reviews, due today, overdue count, review streak, top 5 weakest patterns, top 5 weakest tags.

---

## Scheduling Philosophy

`leetrevive` uses a simple, transparent interval policy — not a black-box algorithm.

**Base intervals by score:**

| Score | Next due |
|---|---|
| 0 — Blank | 1 day |
| 1 — Partial | 3 days |
| 2 — Struggled | 7 days |
| 3 — Clean | 14 days |

**Progressive extension:**
Two consecutive strong reviews (score ≥ 2) raises the minimum interval to 30 days. Three or more raises it to 60 days. A score of 0 always resets to 1 day regardless of history — a miss clears all momentum.

**Today's picks use a four-bucket waterfall:**

1. **Overdue** — most overdue problems first
2. **Due today** — least recently reviewed first
3. **Long unreviewed** — problems unseen for 30+ days, or never reviewed
4. **Reinforcement** — problems sharing tags or patterns with your recent activity

Every pick shows a `Reason` column so the daily selection is never opaque.

The goal is a scheduling policy you can reason about, not one you have to optimise against.

---

## Data storage

Your database lives at:

| Platform | Path |
|---|---|
| macOS | `~/Library/Application Support/leetrevive/leetrevive.db` |
| Linux | `~/.local/share/leetrevive/leetrevive.db` |
| Windows | `%APPDATA%\Local\leetrevive\leetrevive\leetrevive.db` |

It is a standard SQLite file. You can inspect, query, or back it up with any SQLite client. No external services, no telemetry, no sync.

---

## Roadmap

**Near-term**
- [ ] `leetrevive remove <id>` — remove a problem from the bank
- [ ] `leetrevive edit <id>` — update tags, pattern, difficulty, URL
- [ ] `leetrevive import` — bulk import from CSV or JSON
- [ ] Shell completions (bash / zsh / fish)
- [ ] `--json` output flag on `bank` and `stats` for scripting

**Medium-term**
- [ ] FSRS scheduler as an opt-in alternative (`--algo fsrs`)
- [ ] Textual-based TUI (`leetrevive tui`) reusing the existing service layer
- [ ] Export to Anki deck (`.apkg`)
- [ ] Weekly digest summary command

**Long-term**
- [ ] Optional sync via a self-hosted backend
- [ ] Editor plugin (`done` without leaving Neovim / VS Code)
- [ ] LeetCode session integration for automatic submission detection

---

## Project structure

```
src/leetrevive/
  cli.py          # typer app and command registration
  db.py           # sqlite3 layer — no ORM, no global state
  models.py       # Problem, Review, DailyPick dataclasses
  scheduler.py    # pure scheduling functions — zero DB imports
  utils.py        # rich console, formatters, URL helpers
  commands/       # one file per CLI command
tests/
  conftest.py     # db_path + isolated_db fixtures
  test_db.py
  test_scheduler.py
  test_commands.py
```

`scheduler.py` contains no database calls. Commands fetch data, pass it in, and receive decisions back. This keeps scheduling logic independently testable and reusable by a future TUI or API layer without modification.

---

## Contributing

Contributions are welcome.

- Business logic belongs in `scheduler.py` or a future `services/` layer — not in command handlers
- `scheduler.py` must stay free of database imports
- All new commands need at least one integration test in `test_commands.py`
- Run `pytest` before opening a PR — 100% pass rate required
- Prefer clarity over cleverness

```bash
pip install -e ".[dev]"
pytest
```

---

## License

MIT
