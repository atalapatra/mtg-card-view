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

- Paste a deck list with **+ New deck**. Decks are saved in `%APPDATA%\mtg-card-view\decks.sqlite3`.
- Switch between **Board**, **Table**, and **Images** views. Group by category, type, mana value, color, and more. Sort by EDHREC rank, name, MV, or price.
  Filter by name, rules text, or tag.
- Choose **Group by → + New custom grouping…** to make your own groups, then drag cards between them in the Board view.
  Changes save automatically.
- Click a card to see its details: EDHREC rank, categories, and every Scryfall tag (★ marks cards Tagger considers defining examples of a tag).

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
