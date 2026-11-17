# Decisions Log

Append-only. Newest at the bottom. To change a decision, add a new entry that supersedes the
old one (and mark the old one `Superseded by D-NNN`). Don't edit history.

Format: **ID · date · status**, then Context / Decision / Consequences.
Status: `Accepted`, `Proposed` (awaiting user), `Superseded by D-NNN`.

---

## D-001 · 2026-11-16 · Accepted
**Python core, frontend free to be non-Python**

- Context: The user asked for a Python app that pulls Scryfall data. The front end doesn't need to be Python.
- Decision: All data fetching, parsing, categorization, grouping, and sorting live in the Python package
  `mtgcv`. Any UI consumes its JSON output, or a future HTTP API that wraps it.
- Consequences: The CLI and the UI share one code path. `CardInfo`/`Report.to_dict()` is the data contract.

## D-002 · 2026-11-16 · Accepted
**Category tags come from Scryfall's Oracle Tags bulk file**

- Context: Scryfall card objects do not include Tagger tags. Alternatives considered:
  per-tag `otag:` searches (many requests), the unofficial Tagger GraphQL API (brittle, needs
  CSRF tokens), and `api.scryfall.com/private/tags/oracle` (undocumented).
- Decision: Use the official bulk file at `GET /bulk-data/oracle-tags` → `jsonl_download_uri` (~6 MB gz).
  Check for updates at most once a day. Fall back to the cached copy when offline.
- Consequences: One download covers every card. See `scryfall-notes.md` for format details.

## D-003 · 2026-11-16 · Accepted
**Inherit ancestor tags, canonicalize labels, expand aliases for matching**

- Context: The bulk file lists only *direct* taggings (`removal` has 0 direct cards, 25 child tags).
  Labels mix styles (`mana rock` vs `mana-rock`), and many tags have aliases.
- Decision: Each card gets the full ancestor closure of its direct tags. Labels become hyphenated
  slugs. Category matching uses slugs plus aliases. Refinement rules use canonical slugs only.
- Consequences: The counts match the scryfall.com `otag:` search exactly (ramp 2,495; removal 6,751).

## D-004 · 2026-11-16 · Accepted
**Collapse ~4,600 tags into ~30 curated deck-role categories**

- Context: Raw tags are too granular to group a deck by (`manarock-ccc`, `full-refund`).
- Decision: `categories.py` defines an ordered list of roles (Land, Board Wipe, Counterspell, Removal,
  Ramp, Tutor, Card Advantage, …). A card can belong to several categories. The first match in list
  order is its `primary_category`. Some categories also use rules derived from card data
  (Land from the type line, Fixing from `produced_mana`, Tokens from oracle text). Raw tags stay on every card.
- Refinements: lands aren't Ramp unless tagged land-ramp/extra-land; land-only tutors are
  Ramp, not Tutor; opponent-only lifegain (Swords to Plowshares) isn't Lifegain.
- Consequences: `--group-by category` shows a card in every group it fits. `--group-by primary` places
  each card exactly once, which suits the future drag-and-drop default placement.

## D-005 · 2026-11-16 · Accepted
**Expose Tagger `very_strong` weights as `strong_tags`**

- Context: The user wants to know how effective a card is at a role. Tagger taggings carry a `weight`.
  About 631 are `very_strong` (e.g. Sol Ring → `mana-rock`). Everything else is `median`.
- Decision: Surface these as `CardInfo.strong_tags`. Use EDHREC rank as the primary popularity signal.
- Consequences: The signal is sparse. Don't treat a missing strong tag as "weak".

## D-006 · 2026-11-16 · Accepted
**Card lookup via `/cards/collection` by front-face name, with a fuzzy fallback**

- Context: `/cards/collection` rejects full `A // B` names but resolves front-face names for
  split, adventure, and DFC cards. Response order isn't reliable to match against the request.
- Decision: Batch 75 front-face names per request. Match results by an accent-insensitive normalized
  name across all faces. Fall back to `/cards/named` exact, then fuzzy.
- Consequences: Typos resolve, but the cache key is the *requested* name (a typo gets its own cache entry).

## D-007 · 2026-11-16 · Accepted
**Local caching: SQLite for cards (7-day TTL), file for tags**

- Decision: Cache in `%LOCALAPPDATA%\mtg-card-view` (or `~/.cache/mtg-card-view`). Override with `MTGCV_CACHE_DIR`.
- Rationale: EDHREC rank and prices drift slowly, and caching keeps repeat runs under 1 second.

## D-008 · 2026-11-16 · Accepted
**Minimal dependencies: `httpx` only (plus `pytest` for dev); dataclasses, not pydantic**

- Rationale: Keep the core light until the UI/API decision is made. Revisit if a FastAPI layer is added
  (pydantic would come along with it).

## D-009 · 2026-11-16 · Superseded by D-010
**UI stack** (awaiting the user's decision)

- Options presented: (A) React + Vite with a FastAPI server, *recommended* for dnd-kit drag and drop;
  (B) Svelte with FastAPI; (C) a Python-only UI (NiceGUI or Streamlit), weak at drag and drop; (D) a Tauri desktop wrapper around A.
- Related open decisions: layout (board columns, table, or image grid), where custom groupings are saved
  (browser only or backend SQLite), and deck input (paste, upload, or Moxfield/Archidekt URL import).

## D-010 · 2026-11-16 · Accepted
**UI stack: React + Vite (TypeScript) frontend, FastAPI backend** (chosen by the user: option A)

- Frontend in `web/`: React 19, Vite 8, TypeScript 5.9 (pinned `~5.9`, not the native TS 7 compiler),
  `@dnd-kit/core` for drag and drop, plain CSS with variables (no CSS framework).
- Backend in `src/mtgcv/server.py`, run with `mtgcv serve`. In dev, Vite (:5173) proxies `/api` to :8000.
  In prod, FastAPI serves the built `web/dist`.
- Consequences: one command runs the whole app once the frontend is built. FastAPI and uvicorn are now core
  dependencies (this supersedes the "httpx only" part of D-008).

## D-011 · 2026-11-16 · Accepted
**Layout: switchable Board / Table / Images views** (chosen by the user)

- Board (masonry-style columns per group) was built first and is the only view with drag and drop. Table and
  Images use the same grouping, sorting, and filtering.
- The API returns group membership for every built-in grouping mode in one response
  (`Report.to_api_dict()["groupings"]`), so switching grouping or view is instant and grouping logic
  exists only in Python. Sorting and text filtering happen client-side.

## D-012 · 2026-11-16 · Accepted
**Persistence: decks and custom groupings in backend SQLite** (chosen by the user)

- `src/mtgcv/store.py`: `decks.sqlite3` in a *data* dir (`%APPDATA%\mtg-card-view`, override
  `MTGCV_DATA_DIR`), kept separate from the cache dir so clearing the cache never loses user work.
- A custom grouping is a "board": `{groups: [{id, name, cards: [card keys]}]}`. Card key = `"<section>:<name>"`.
  Boards are **single-placement**: the server dedupes on save, and cards not in any group show as Unsorted.
  Boards can be seeded from primary category, type, mana value, color, section, or user tags, or start empty.
- Reports are not stored. They're recomputed on load from the card cache (fast), so they stay fresh.
- The UI saves board edits optimistically, with a 400 ms debounced PATCH.

## D-013 · 2026-11-16 · Accepted
**Deck input: paste text only** (chosen by the user)

- A paste dialog with the same parser as the CLI. File upload and Moxfield/Archidekt URL import were
  offered and not chosen.

## D-014 · 2026-11-17 · Accepted
**Graph view: card-image nodes, two weightings, built for thousands of cards** (requested by the user)

- A 4th view, "Graph". Nodes are card images, edges are synergy links. Cards can be dragged, and a Reset button
  returns to the original layout. It has to handle a whole collection (thousands of cards) pasted as text.
- Rendering: a custom **Canvas 2D** renderer (`web/src/graph/GraphCanvas.tsx`). Libraries weren't a good fit:
  Sigma.js (WebGL) only draws circular image nodes, and Cytoscape slows down with thousands of image nodes.
  The renderer draws only what's on screen, with level of detail (colored card shapes, then Scryfall `small`
  images, then `normal` images), lazy-loads images 10 at a time, and batches edges into 4 strokes.
- Layout: d3-force in a **Web Worker**, computed once, so dragging moves one card and doesn't re-run the
  physics. It's deterministic (d3-force v3 uses a seeded random number generator and the server returns a stable node order), so
  **Reset = delete the saved layout and recompute**. That yields the same original layout (verified: 0.00 difference).
- Measured on a 2,000-card list: tags graph ready in about 3 s, EDHREC graph in about 3.3 s (pages cached).

## D-015 · 2026-11-17 · Accepted
**EDHREC weighting: every legendary creature is a commander hub** (chosen by the user)

- Hubs are cards in the Commander section, legendary creatures, and "can be your commander" cards. Edges go
  from a commander to a card, weighted by EDHREC `synergy`. Each non-commander card keeps its top 5 commanders.
  Synergy below 1% and basic lands are dropped.
- Data comes from EDHREC's unofficial JSON (`json.edhrec.com/pages/commanders/<slug>.json`). See
  `docs/edhrec-notes.md`. Pages are fetched by a background job (`EdhrecFetcher`) at 0.5 s per request and
  cached for 7 days (404s for 1 day). The UI polls and shows progress. About 200 commanders took about 106 s
  the first time.
- Risk: it's an unofficial endpoint and may change without notice. All parsing lives in `CommanderPage.parse`.

## D-016 · 2026-11-17 · Accepted
**Tag weighting: payoff ↔ enabler themes** (chosen by the user)

- `src/mtgcv/synergy.py` defines `THEMES`: about 25 curated themes, each pairing payoff tags with enabler tags or rules
  (e.g. `lifegain-matters` ↔ the Lifegain category; `synergy-artifact` ↔ artifact cards and artifact-token makers).
  There are also generic typal themes: a `typal-<type>` payoff links to creatures of that type actually present in the list,
  with changelings counting as every type.
- Edge weight is the number of themes linking the pair. All typal themes between one pair count as one,
  since changelings would otherwise inflate it. Each card keeps its top 8 edges; an edge survives if
  either endpoint keeps it.
- Enter-the-battlefield effects have no Tagger tag, so the Blink theme detects them from oracle text.

## D-017 · 2026-11-17 · Accepted
**Graph positions saved per deck and mode; unconnected cards shown in an outer ring** (chosen by the user)

- A `graph_layouts` table holds `(deck_id, mode) → {card_key: [x, y]}`. The computed layout is saved too, so
  reopening is instant. Drags save after an 800 ms debounce. When the deck changes, saved cards stay pinned and only new
  cards get laid out.
- Cards with no edges go on a sunflower-pattern ring outside the connected graph, most popular (EDHREC rank) innermost.
- The edge filter in the toolbar (minimum themes / minimum synergy) only affects drawing, not layout.

## D-018 · 2026-11-17 · Accepted
**ManaBox CSV import: converted to the plain card-list text; binders ignored for now** (chosen by the user)

- Supersedes the "paste text only" part of D-013. Paste still works, and a file can now be picked or dropped.
- `src/mtgcv/importers.py` `manabox_to_decklist()` turns a ManaBox export into the same text a user would
  paste: one `<qty> <name> (<SET>) <number>` line per card name. Rows for the same name (other printings, foils,
  other binders) are summed, and the first printing is kept. The result goes through the normal `parse_decklist` path.
- **Binder Name and Binder Type are intentionally not used** as deck boundaries or tags. The user said to leave them
  out for now, but they're still in the CSV if we revisit this later.
- Left out by default, each with a checkbox to include it: token cards (Set name ends in "Tokens") and
  wishlist-type lists (`Binder Type = list`).
- `POST /api/import/manabox` does the conversion and saves nothing. The UI fills the card-list box so the user can
  review it before saving. The CLI auto-detects ManaBox CSVs (`--include-tokens`, `--include-lists`).
