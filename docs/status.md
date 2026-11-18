# Status

_Last updated: 2026-11-16_

## Done
- **Python core** (`src/mtgcv/`, see CLAUDE.md)
  - Deck list parsing: plain, Moxfield, MTGA, Archidekt `[categories]`, `#hashtags`, sections, split names
  - Scryfall lookup: batched, rate-limited, fuzzy fallback, 7-day SQLite cache
  - Oracle tags from the bulk file, with hierarchy inheritance, aliases, and `strong_tags`
  - About 30 deck-role categories with a primary category per card
  - CLI: `analyze`, `card`, `refresh-tags`, `serve`
- **API** (`server.py`, FastAPI) with deck CRUD, custom grouping ("board") CRUD, and analyze. Stored in SQLite (`store.py`).
- **Web UI** (`web/`, React + Vite + TS)
  - Saved decks sidebar. The paste dialog creates or edits a deck.
  - Summary stats: counts, lands, average MV, color identity, median EDHREC rank, Game Changers, price
  - Board / Table / Images views. Group by any built-in mode or a custom grouping. Sort by EDHREC rank,
    name, MV, or price. Text filter across name, oracle text, tags, and categories.
  - Custom groupings: create (seeded or empty), drag cards between groups (dnd-kit), add, rename,
    reorder, and delete groups, auto-save
  - Card detail panel: image (with DFC flip), EDHREC rank tier, oracle text with symbols, categories,
    all Scryfall tags (★ for strong ones, click to filter), links to Scryfall, EDHREC, and Tagger
  - Hover image preview. Dark and light themes follow the OS.
- **Graph view** (D-014 to D-017): card-image nodes on a canvas, two weightings (Scryfall payoff ↔ enabler
  themes; EDHREC commander synergy with every legendary creature as a hub), layout saved per deck and
  mode (cards can't be moved since D-023; dragging anywhere pans), Reset recomputes the deterministic layout, unconnected cards in an outer ring, search highlights
  matches, hovering or selecting a card highlights its links, and the detail panel lists "Synergy links".
  Verified with a 2,000-card list: about 3 s to a ready graph, plus about 106 s once to download about 200 EDHREC pages.
- **ManaBox CSV import** (D-018): an "Import ManaBox CSV…" button and file drop in the deck dialog convert
  the export to a plain card list for review. Tokens and wishlist lists are left out by default, with
  checkboxes to include them. The CLI auto-detects ManaBox CSVs. Binder information is not used yet.
- **Pair comparison in the graph** (D-019): clicking a synergy link opens a second sidebar, and a box above
  both explains the pair: linking themes with payoff/enabler roles and matched tags, EDHREC commander numbers,
  and shared categories and tags. Right-clicking another card on the canvas (Control-click on Mac) opens the same comparison (D-025, D-026).
- Tests: 29 offline pytest tests (parser, client, tags, analysis, API, synergy, EDHREC, ManaBox import, pair explain)
- Verified manually: a live run against Scryfall, plus a headless-Edge CDP script that performs a real mouse
  drag between groups and confirms it persisted (the script lived in the session scratchpad and is not in the repo)

- **GraphMTG update** (D-020): UI renamed to GraphMTG/collections; Graph is the first and default view (tag
  synergy); filter bar (colors, type, category, MV, EDHREC rank, rarity, price) hides cards in all views; delete
  collections from the header or sidebar; Median rank stat removed.

- **Standalone Windows app** (D-021): `packaging/build_exe.ps1` → `dist\GraphMTG.exe`; launcher with single-instance,
  free-port and browser handling; version in sidebar; GitHub Actions release workflow (not yet run on GitHub).
- **macOS app** (D-022): `packaging/build_mac.sh` → `dist/GraphMTG.app` + `GraphMTG-mac.zip` (Apple Silicon, unsigned).
  Menu-bar front end in `src/mtgcv/macapp.py` (rumps); data in `~/Library/...`. Built and smoke-tested only in CI
  (`mac` job); never run on a real Mac yet.
- `make reset` / `make reset-cache` (`scripts/reset_data.py`) delete local data.
- Resizable left and right sidebars (D-024), with widths remembered per browser.
- New/Edit collection dialog: "Analyze & save" / "Save" is locked (shows "Analyzing…") while the save runs, and while
  a ManaBox CSV is being converted, so a list can't be imported twice. App.tsx also guards against overlapping saves.

## Next / ideas
- Run the release workflow once manually on GitHub (Actions → Build GraphMTG → Run workflow) before the first tag.
  The macOS job has never run; check its smoke test and try the zip on a real Mac (Gatekeeper "Open Anyway" flow).
- Optional: code signing (Windows SmartScreen) / Apple notarization ($99/yr Developer Program), Intel Mac build,
  native window (pywebview).
- Graph: the whole-library tag graph is one dense "hairball" (broad themes like Artifacts and Spellslinger
  connect everything). Options: lay out using only links at or above the current filter, or color nodes by theme or cluster.
  Ask the user before changing it.
- Graph: theme list tuning in `synergy.py` (e.g. Spellslinger links every instant to every spell payoff)
- Creating a deck from a large uncached list blocks for about 40 s on 2,000 cards (Scryfall lookups) with only a
  spinner. Consider a progress indicator.
- Add a frontend e2e test to the repo (e.g. Playwright) if UI regressions become a concern
- Reorder cards *within* a group (currently sorted by the Sort setting; only membership is custom)
- Let a card belong to multiple custom groups? (currently single placement, D-012)
- Category tuning against more real decks (e.g. Delver of Secrets is Uncategorized)
- Show Tagger `annotation` text; a tag-hierarchy tree or filter using `TagIndex.parents`
- Export a custom grouping back to text (e.g. Archidekt `[Category]` format)

- ManaBox binders/decks (Binder Name / Binder Type) could later become tags or separate decks. The user
  deferred this (D-018).

- Theme gap spotted: Tekuthal (proliferate doubler) and Flux Channeler (proliferates) have no tag theme linking
  them. Tekuthal's tags may not include a proliferate-payoff tag, so check this in `THEMES`.

## Open questions
- Nothing committed to git yet. Waiting on the user.
