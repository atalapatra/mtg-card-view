# GraphMTG

See how the cards in a Magic: The Gathering collection work together. GraphMTG pulls data from
[Scryfall](https://scryfall.com/docs/api) (functional tags, card details) and EDHREC (commander synergy), then
draws your cards as a synergy graph. Group them by what they do, sort by popularity, filter, and organize.

The code, the `mtgcv` command and the data folders keep their original `mtg-card-view` / `mtgcv` names (D-020).

## Download and run

Get the app from the repo's **Releases** page. Collections are stored on your own computer (see "How it works"
below). Nothing is uploaded anywhere.

- **Windows:** download **GraphMTG.exe** and double-click it. It opens in your browser, and a small console window
  stays open while it runs; close that window to quit. Windows may warn that the app is unrecognized (it isn't
  code-signed). Click **More info → Run anyway**.
- **Mac (Apple Silicon, macOS 11+):** download **GraphMTG-mac.zip**, unzip it, and drag **GraphMTG** into
  Applications. The first time, macOS blocks it because it isn't notarized: open **System Settings → Privacy &
  Security**, scroll down and click **Open Anyway**. GraphMTG opens in your browser and adds an icon to the menu
  bar (top right) with **Open GraphMTG** and **Quit GraphMTG**.

## Releasing a new version

1. Bump `__version__` in `src/mtgcv/__init__.py` (the only place the version lives).
2. Commit, then tag and push: `git tag v0.2.0; git push origin v0.2.0`.
3. The **Build GraphMTG** GitHub Actions workflow tests, builds and smoke-tests `GraphMTG.exe` (Windows) and
   `GraphMTG.app` (macOS), then publishes a Release with `GraphMTG.exe` and `GraphMTG-mac.zip` attached (notes from
   `packaging/RELEASE_NOTES.md`). Use **Run workflow** to build without releasing.

To build locally (needs Node 22+ and the `.venv`):
- Windows: `.\packaging\build_exe.ps1` → `dist\GraphMTG.exe` (~17 MB).
- macOS (on a Mac): `bash packaging/build_mac.sh` → `dist/GraphMTG.app` and `dist/GraphMTG-mac.zip`.

`graphmtg` (installed with the package) runs the same launcher without building an app.

## Setup (development)

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

- Create a **collection** with **+ New collection**: paste a card list, or click **Import ManaBox CSV…** (or drop the
  `.csv` file on the card list). A ManaBox export becomes a normal card list you can review before saving. Tokens and
  wishlist lists are left out unless you tick their checkboxes. Collections are saved in
  `%APPDATA%\mtg-card-view\decks.sqlite3`. Delete one from the header's **Delete** button or the × next to it in the sidebar.
- **Graph** (the main view; the app always opens on it, with **Scryfall tag synergy**): cards as images in a
  synergy network. Two weightings are available:
  - **Scryfall tag synergy** links payoffs to enablers (e.g. "lifegain matters" ↔ lifegain cards; see `THEMES` in
    `src/mtgcv/synergy.py`).
  - **EDHREC commander synergy** links every legendary creature in the collection to the cards EDHREC says
    over-perform with it. The first use downloads each commander's EDHREC page, about 0.5 s each, then caches it for
    a week.

  Drag anywhere to pan (cards stay where the layout puts them), scroll to zoom, and double-click empty space to
  fit. The layout is saved per collection; **Reset layout** recomputes it. Hover or click a card to highlight its links.
  Click a synergy link in the card panel to open that card alongside, with a box explaining their synergy.
  To compare the selected card with **any** other card, linked or not, right-click that card in the graph:
  - **Windows:** right-click it.
  - **Mac:** Control-click it, or click with two fingers on a trackpad (or right-click with a two-button mouse).

  Do the same on the second card again to close the comparison. The search box highlights matching cards. It works
  with whole collections (tested with 2,000 cards).
- **Board**, **Table** and **Images** views: group by category, type, mana value, color, and more. Sort by EDHREC
  rank, name, MV, or price. Choose **Group by → + New custom grouping…** to make your own groups, then drag cards
  between them in the Board view. Changes save automatically.
- **Filters** (button next to the search box): color identity (fits within / includes any / exactly), card type,
  category, mana value range, EDHREC rank, rarity, and max price. Non-matching cards are hidden in every view; in the
  Graph they keep their positions and reappear in place when you clear the filter.
- Click a card to see its details: EDHREC rank, categories, and every Scryfall tag (★ marks cards Tagger considers
  defining examples of a tag).

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
* Results are cached in `%LOCALAPPDATA%\mtg-card-view` (macOS: `~/Library/Caches/mtg-card-view`; Linux:
  `~/.cache/mtg-card-view`; override with `MTGCV_CACHE_DIR`). Collections are in `%APPDATA%\mtg-card-view` (macOS:
  `~/Library/Application Support/mtg-card-view`; override with `MTGCV_DATA_DIR`). Cards are re-fetched after 7 days. Tag data is checked for updates daily.

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

---

GraphMTG is unofficial Fan Content permitted under the Fan Content Policy. Not approved/endorsed by Wizards.
Portions of the materials used are property of Wizards of the Coast. ©Wizards of the Coast LLC.
Card data and images: [Scryfall](https://scryfall.com). Commander synergy: [EDHREC](https://edhrec.com).
