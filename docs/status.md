# Status

_Last updated: 2026-11-16_

## Done
- Python core package `mtgcv` (see CLAUDE.md for the module map)
  - Deck list parsing: plain, Moxfield, MTGA, Archidekt `[categories]`, `#hashtags`, section headers,
    split names, duplicate merging
  - Scryfall lookup: batched, rate-limited, fuzzy fallback, 7-day SQLite cache
  - Oracle tags from the bulk file, with hierarchy inheritance, aliases, and `strong_tags`
  - About 30 deck-role categories with a primary category per card
  - Grouping: category, primary, type, cmc, color, section, user_tag, none.
    Sorting: edhrec, name, cmc, price
  - Summary: counts, lands, average MV, color identity, median EDHREC rank, Game Changers, price, category counts
  - CLI: `analyze` (table or `--json`), `card`, `refresh-tags`
- 10 offline tests passing
- Verified live against `examples/sample_deck.txt`

## Next
1. **UI decision** (D-009 in `decisions.md`, waiting on the user): stack, layout, how custom groupings are saved, deck input
2. Build the UI, likely with an HTTP API layer (e.g. FastAPI) over `build_report`
3. Drag-and-drop custom groupings, seeded from `primary_category` or `user_tags`

## Open questions / ideas
- Should Tagger `annotation` text be shown? (~3.4k taggings have one)
- Tag hierarchy (`TagIndex.parents`) could power a tag tree or filter in the UI
- Category list tuning: check against more real decks. Some cards are Uncategorized
  (e.g. Delver of Secrets).
- Nothing committed to git yet.
