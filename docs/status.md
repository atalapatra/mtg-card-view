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
- Tests: 13 offline pytest tests (parser, client, tags, analysis, API)
- Verified manually: a live run against Scryfall, plus a headless-Edge CDP script that performs a real mouse
  drag between groups and confirms it persisted (the script lived in the session scratchpad and is not in the repo)

## Next / ideas
- Add a frontend e2e test to the repo (e.g. Playwright) if UI regressions become a concern
- Reorder cards *within* a group (currently sorted by the Sort setting; only membership is custom)
- Let a card belong to multiple custom groups? (currently single placement, D-012)
- Category tuning against more real decks (e.g. Delver of Secrets is Uncategorized)
- Show Tagger `annotation` text; a tag-hierarchy tree or filter using `TagIndex.parents`
- Export a custom grouping back to text (e.g. Archidekt `[Category]` format)

## Open questions
- Nothing committed to git yet. Waiting on the user.
