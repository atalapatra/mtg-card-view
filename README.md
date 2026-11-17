# mtg-card-view

Analyze a Magic: The Gathering card list with data from [Scryfall](https://scryfall.com/docs/api):
functional category tags, EDHREC rank, and card details. Group cards by what they do
and sort by popularity.

## Setup

```powershell
python -m venv .venv
.\.venv\Scripts\activate
pip install -e ".[dev]"
```

## Web UI

```powershell
cd web; npm install; npm run build; cd ..   # one-time: build the frontend
mtgcv serve --open                          # http://127.0.0.1:8000
```

- Paste a deck list with **+ New deck**. To load a **ManaBox** collection export, click **Import ManaBox CSV…** or drop
  the `.csv` file on the card list. It becomes a normal card list you can review before saving. Tokens and wishlist
  lists are left out unless you tick their checkboxes. Decks are saved in `%APPDATA%\mtg-card-view\decks.sqlite3`.
- Switch between **Board**, **Table**, and **Images** views. Group by category, type, mana value, color, and more. Sort by EDHREC rank, name, MV, or price.
  Filter by name, rules text, or tag.
- Choose **Group by → + New custom grouping…** to make your own groups, then drag cards between them in the Board view.
  Changes save automatically.
- Click a card to see its details: EDHREC rank, categories, and every Scryfall tag (★ marks cards Tagger considers defining examples of a tag).
- **Graph** view: cards as images in a synergy network. Two weightings are available:
  - **Scryfall tag synergy** links payoffs to enablers (e.g. "lifegain matters" ↔ lifegain cards; see `THEMES` in
    `src/mtgcv/synergy.py`).
  - **EDHREC commander synergy** links every legendary creature in the list to the cards EDHREC says over-perform
    with it. The first use downloads each commander's EDHREC page, about 0.5 s each, then caches it for a week.

  Drag cards to arrange them; the layout is saved per deck. **Reset layout** returns to the original arrangement.
  Scroll to zoom and double-click empty space to fit. Hover or click a card to highlight its links. The search box
  highlights matching cards. It works with whole collections (tested with 2,000 cards).

For frontend development, run `mtgcv serve` and `cd web; npm run dev` (http://localhost:5173, hot reload).

## CLI

```powershell
mtgcv analyze examples\sample_deck.txt                  # grouped by category, sorted by EDHREC rank
mtgcv analyze deck.txt --group-by type --sort cmc       # other groupings / sorts
mtgcv analyze deck.txt --tags                           # also show raw Scryfall tags per card
mtgcv analyze deck.txt --json report.json               # full JSON report (for the UI)
mtgcv card "Rhystic Study"                              # one card: details, categories, every tag
mtgcv refresh-tags                                      # force re-download of tag data
```

Group modes: `category` (a card appears in every category it fits), `primary` (one category
per card), `type`, `cmc`, `color`, `section`, `user_tag`, `none`.
Sort modes: `edhrec` (most-played first), `name`, `cmc`, `price`.

`mtgcv analyze ManaBox_Collection.csv` also works. ManaBox CSVs are detected automatically, and
`--include-tokens` / `--include-lists` keep the entries that are left out by default.

### Deck list formats

Plain (`1 Sol Ring`, `1x Sol Ring`, `Sol Ring`), Moxfield/MTGA (`1 Sol Ring (C21) 263 *F*`),
Archidekt (`1x Sol Ring (c21) 263 [Ramp]`), and `#hashtags`. Section headers such as
`Commander`, `Deck`, `Sideboard`, and `Maybeboard` are recognized. Archidekt `[categories]`
and `#hashtags` are kept as `user_tags` (use `--group-by user_tag`).

## How it works

| Data | Source |
|---|---|
| Card details, EDHREC rank, prices, images | `POST /cards/collection` (75 cards per request), with a `/cards/named?fuzzy=` fallback for typos |
| Category tags | Scryfall's **Oracle Tags** bulk file (`/bulk-data/oracle-tags`), from the community [Tagger](https://tagger.scryfall.com) project |

* About 5,000 raw Tagger tags are collapsed into about 30 deckbuilding **categories** in
  [`src/mtgcv/categories.py`](src/mtgcv/categories.py) (Ramp, Removal, Board Wipe, Card Advantage,
  Tutor, Protection, and others). Edit that file to tune the categories. The raw tags are still kept on every card.
* Requests follow Scryfall's guidelines: a User-Agent header and at least 100 ms between requests.
* Results are cached in `%LOCALAPPDATA%\mtg-card-view` (or `~/.cache/mtg-card-view`; override
  with `MTGCV_CACHE_DIR`). Cards are re-fetched after 7 days. Tag data is checked for updates daily.

## Layout

```
src/mtgcv/
  decklist.py    parse text card lists
  scryfall.py    API client, rate limiting, oracle-tag index
  cache.py       SQLite + file cache
  categories.py  tag -> category mapping
  analyze.py     CardInfo model, grouping, sorting, summary
  cli.py         command-line interface
  store.py       saved decks + custom groupings (SQLite)
  server.py      FastAPI app
web/             React + Vite + TypeScript UI
docs/            decisions log, status, Scryfall API notes
```

## Tests

```powershell
pytest
```
