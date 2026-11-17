# CLAUDE.md

Context for Claude Code sessions in this repo. Keep it short and current. Put details in `docs/`.

## Project

**GraphMTG** (user-facing name; repo, package, `mtgcv` CLI, API routes and data dirs keep the old names, D-020).
In the UI a saved card list is a **collection** (code/API/DB still say "deck").

Analyze a Magic: The Gathering card list using Scryfall data: functional category tags, EDHREC rank,
and card details. The goal is to understand what each card does in a deck and how well it does it.
Group cards by category and sort by EDHREC rank. The end goal is a UI where cards can be
dragged and dropped into custom groupings.

- Backend/core: Python 3.13 package `mtgcv` in `src/mtgcv/`, plus a FastAPI server
- Frontend: React + Vite + TypeScript in `web/` (D-010 to D-013 in the decisions log)
- **The user wants to make UI and design decisions themselves.** For new UX choices, present options with a
  recommendation and ask. Don't pick unilaterally.

## Docs: read and update these

- @docs/status.md: what's built, what's next, open questions. Update at the end of meaningful work.
- @docs/decisions.md: decision log. Append an entry whenever a design or technical decision is made
  (by the user or agreed with them). Never rewrite past entries. Supersede them with a new one.
- `docs/scryfall-notes.md` / `docs/edhrec-notes.md`: verified findings about Scryfall's API and bulk data,
  and EDHREC's unofficial JSON. Check here before probing the APIs again, and add any new findings.

## Commands (Windows / PowerShell)

```powershell
.\.venv\Scripts\python -m pytest -q                       # tests (offline, mocked HTTP)
.\.venv\Scripts\mtgcv analyze examples\sample_deck.txt    # live run against Scryfall
.\.venv\Scripts\mtgcv analyze deck.txt --json out.json    # JSON report (UI contract)
.\.venv\Scripts\mtgcv card "Sol Ring"                     # inspect one card's tags
.\.venv\Scripts\python -m pip install -e ".[dev]"         # (re)install
.\.venv\Scripts\mtgcv serve --open                        # app at :8000 (serves web/dist if built)

cd web; npm install; npm run build                        # build UI (tsc typecheck + vite)
cd web; npm run dev                                       # UI dev server :5173, proxies /api -> :8000

.\packaging\build_exe.ps1                                # dist\GraphMTG.exe (PyInstaller, bundles web/dist)
.\.venv\Scripts\graphmtg                                  # the exe's launcher, unbuilt (port 8737, opens browser)
```

Releases: bump `__version__` in `src/mtgcv/__init__.py` (single source), tag `vX.Y.Z`, push the tag, and
`.github/workflows/release.yml` builds and publishes GraphMTG.exe. When testing the exe/launcher, set
`MTGCV_DATA_DIR`/`MTGCV_CACHE_DIR` to scratch folders and `GRAPHMTG_NO_BROWSER=1`.

When testing the server manually, set `$env:MTGCV_DATA_DIR` to a scratch folder so you don't write
into the user's real saved decks.

## Architecture

```
decklist.py    text list -> DeckEntry (qty, section, set, user_tags from [Archidekt] / #hashtags)
importers.py   ManaBox CSV -> plain card-list text (binders ignored, tokens/lists excluded by default)
scryfall.py    ScryfallClient (rate-limited, cached) + TagIndex (oracle tags w/ hierarchy & aliases)
cache.py       SQLite card cache (7-day TTL) + tags bulk file (daily update check)
categories.py  CATEGORIES: ordered list mapping tag slugs -> ~30 deck roles; order = primary priority
analyze.py     CardInfo dataclass, build_report, group_cards, sort_cards, summarize
cli.py         argparse CLI (`mtgcv` entry point)
store.py       DeckStore: SQLite decks + boards (custom groupings) + graph_layouts in the data dir
server.py      FastAPI app (create_app) — /api/decks, /api/boards, /api/analyze, /api/decks/{id}/graph, /api/health;
               serves the built UI (find_web_dist: env override, exe bundle, package, repo web/dist)
launcher.py    GraphMTG.exe / `graphmtg`: single instance via <data dir>/server.json, free port, opens browser
edhrec.py      EdhrecClient (unofficial JSON, cached, 0.5 s/request) + EdhrecFetcher (background jobs)
synergy.py     THEMES (payoff <-> enabler), build_tag_graph, build_edhrec_graph, commander_hubs, explain_pair

web/src/
  types.ts       TS mirror of CardInfo / Report.to_api_dict / deck + board shapes
  api.ts         fetch wrappers
  util.ts        client-side sort/search/filters (matchesFilters), symbol URLs, pure board ops (moveCard, addGroup…)
  App.tsx        state: decks, current deck, view, grouping ("auto:<mode>" | "board:<id>"), sort, search,
                 selectedKey + pairKey (second sidebar, graph view)
  components/    BoardView (dnd-kit), TableView, GridView, CardDetail, SynergyBox, FilterBar, Dialogs, HoverPreview, Symbols
  graph/         GraphView (fetch/poll, layout, save, reset), GraphCanvas (canvas renderer), layoutWorker (d3-force)
```

Scale target: a whole collection (thousands of cards) must stay usable in every view. Avoid O(n²) work per
render, keep heavy computation server-side or in workers, and cap graph edges per card.

Data contract: `CardInfo` fields and `Report.to_api_dict()` are mirrored in `web/src/types.ts`. **Change
both together.** Grouping logic lives only in Python (the API returns membership for every mode).
Sorting and filtering are client-side.

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
