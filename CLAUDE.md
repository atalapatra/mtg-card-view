# CLAUDE.md

Context for Claude Code sessions in this repo. Keep it short and current. Put details in `docs/`.

## Project

Analyze a Magic: The Gathering card list using Scryfall data: functional category tags, EDHREC rank,
and card details. The goal is to understand what each card does in a deck and how well it does it.
Group cards by category and sort by EDHREC rank. The end goal is a UI where cards can be
dragged and dropped into custom groupings.

- Backend/core: Python 3.13 package `mtgcv` in `src/mtgcv/` (done, see `docs/status.md`)
- Frontend: not built yet. It doesn't have to be Python. **The user wants to review options and make the UI design decisions
  themselves.** Present choices; don't pick a framework unilaterally.

## Docs: read and update these

- @docs/status.md: what's built, what's next, open questions. Update at the end of meaningful work.
- @docs/decisions.md: decision log. Append an entry whenever a design or technical decision is made
  (by the user or agreed with them). Never rewrite past entries. Supersede them with a new one.
- `docs/scryfall-notes.md`: verified findings about Scryfall's API and bulk data formats. Check here
  before probing the API again, and add any new findings.

## Commands (Windows / PowerShell)

```powershell
.\.venv\Scripts\python -m pytest -q                       # tests (offline, mocked HTTP)
.\.venv\Scripts\mtgcv analyze examples\sample_deck.txt    # live run against Scryfall
.\.venv\Scripts\mtgcv analyze deck.txt --json out.json    # JSON report (UI contract)
.\.venv\Scripts\mtgcv card "Sol Ring"                     # inspect one card's tags
.\.venv\Scripts\python -m pip install -e ".[dev]"         # (re)install
```

## Architecture

```
decklist.py    text list -> DeckEntry (qty, section, set, user_tags from [Archidekt] / #hashtags)
scryfall.py    ScryfallClient (rate-limited, cached) + TagIndex (oracle tags w/ hierarchy & aliases)
cache.py       SQLite card cache (7-day TTL) + tags bulk file (daily update check)
categories.py  CATEGORIES: ordered list mapping tag slugs -> ~30 deck roles; order = primary priority
analyze.py     CardInfo dataclass, build_report, group_cards, sort_cards, summarize
cli.py         argparse CLI (`mtgcv` entry point)
```

`Report.to_dict()` / `CardInfo` fields form the de facto data contract for any UI. Changing field
names means a breaking change for the frontend.

## Conventions and gotchas

- Scryfall etiquette is required: send a User-Agent and Accept header, keep ≥100 ms between requests, prefer
  `/cards/collection` and bulk data over per-card calls. The User-Agent is generic (`mtg-card-view/<ver>`).
  Never put personal info in it.
- Tests must stay offline. Use `httpx.MockTransport` (see `tests/test_scryfall_and_analyze.py`).
- Category tuning lives in `categories.py`. Refinement rules in `categorize()` use **canonical** tags,
  not alias-expanded ones (aliases like `tutor-hand` broke the Cultivate/Tutor rule).
- Windows: use `encoding="utf-8"` when reading/writing files and `python -X utf8` for ad-hoc scripts.
  Card names contain non-ASCII characters (Lim-Dûl, Æther).
- Bash heredocs containing apostrophes have failed in this environment. Use the Write tool for files.
- Commit only when the user asks.
