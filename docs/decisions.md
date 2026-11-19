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

## D-019 · 2026-11-17 · Accepted
**Graph view: synergy links open a second sidebar, with a synergy box above both** (requested by the user)

- Clicking a synergy link in the card sidebar (graph view only) opens the linked card in a second sidebar
  beside the first. A box spans the top of both and explains the pair.
- Box contents come from `GET /api/decks/{id}/pair?a=&b=` → `synergy.explain_pair()`:
  - **Scryfall themes**, in both directions: which card is the payoff and which the enabler, plus the tags or rule
    that matched on each side. Rule-based matches carry readable labels (e.g. "Artifact card",
    "has an enters-the-battlefield trigger").
  - **EDHREC**, when either card is a commander: synergy %, plus inclusion as "in N of M eligible decks". Otherwise a
    status (`not_listed`, `no_page`, `not_downloaded`). Reads the EDHREC cache only and never triggers a download.
  - **In common**: shared categories and shared Scryfall tags.
- Interaction choices (made by Claude, open to change):
  - A link clicked in the *second* sidebar walks the chain: the second card moves to the first sidebar and the
    clicked card opens in the second.
  - Closing the first sidebar promotes the second. ⇄ swaps the two cards.
  - Escape closes the second sidebar first, then the first.
  - Selecting a card on the canvas, or leaving the graph view, closes the second sidebar.
  - On the canvas the second card gets a dashed gold outline, and the link between the pair is drawn thick.
  - The canvas keeps its view centered when the side panel resizes it.

## D-020 · 2026-11-17 · Accepted
**GraphMTG / collections, Graph as the main view, card filters, deleting collections** (requested by the user)

- **Renames are UI and docs only** (chosen by the user). The app is called **GraphMTG**, and a saved card list is a
  **collection**. The Python package, `mtgcv` CLI, API routes (`/api/decks`), DB tables and data folders keep their
  names, so existing saved data is untouched. "Deck section" became "List section" in labels.
- **Graph is the main view.** It's first in the view switcher, and the app always opens on it with **Scryfall tag
  synergy**. View and graph mode are no longer remembered across page loads (`mtgcv.view` / `mtgcv.graphMode` are
  ignored). Within a session the graph mode is kept when switching views (the state lives in `App`).
- **Filters** (chosen by the user): color identity (fits within / includes any / exactly), type, category, mana value range,
  EDHREC rank (top N, unranked excluded), rarity, and max price (unpriced kept). They combine with the text search and
  **hide** non-matching cards in every view. In the Graph, hidden cards and their links disappear, but the node
  objects (and positions, saved layouts) are kept, so they reappear in place. Filters are session-only.
- **Deleting collections**: a "Delete" button in the collection header and a × on each sidebar item (shown on hover),
  both with a confirmation. Deleting cascades to custom groupings and graph layouts.
- The **Median rank** stat was removed from the collection header.

## D-021 · 2026-11-17 · Accepted
**Distribute GraphMTG as a standalone Windows exe (PyInstaller), published via GitHub Releases** (chosen by the user: option 2)

- Each person runs their own copy, and their data stays local (`%APPDATA%` / `%LOCALAPPDATA%` `\mtg-card-view`). There is no
  central server.
- `packaging/GraphMTG.spec` builds a **one-file** `GraphMTG.exe` (~17 MB) containing Python, `mtgcv` and the built UI
  (`web/dist` → `webui` in the bundle; `server.find_web_dist()` locates it). It has a **console window**: the window is
  the "running" indicator, and closing it quits. Chosen over a tray icon or native window for simplicity; a native
  window (pywebview, option 3) can come later.
- `mtgcv.launcher`:
  - **Single instance:** the running port is recorded in `<data dir>/server.json` and verified with `GET /api/health`
    (`{"app": "graphmtg", ...}`). A second launch just opens the browser. A stale file after a hard kill is ignored.
  - **Port:** 8737 if free, otherwise any free port. It binds 127.0.0.1 only.
  - **Browser:** it opens the browser once the server answers.
  - **Errors:** shown in the console, which waits for Enter so the message can be read.
- **Version**: single source `mtgcv.__version__` (pyproject reads it via hatch). It's shown in the sidebar, and release tags
  must match it (`vX.Y.Z`, checked in CI).
- **CI**: `.github/workflows/release.yml` (windows-latest) runs on tag push or manual run: tests → build → smoke-test the exe
  → Release with the exe and `packaging/RELEASE_NOTES.md`. Manual runs only upload a workflow artifact.
- The exe is **not code-signed**, so users see a SmartScreen warning ("More info → Run anyway"). Signing would cost money and
  is deferred. macOS builds are not set up.
- An app icon (`packaging/graphmtg.ico`, generated by `packaging/make_icon.py`) is also used as the web favicon.

## D-022 · 2026-11-17 · Accepted
**macOS app: a menu-bar GraphMTG.app for Apple Silicon, unsigned, built in CI** (chosen by the user: menu-bar icon,
unsigned for now, Apple Silicon only). Extends D-021.

- **Front end:** the packaged Mac app has no window and no Dock icon (`LSUIElement`). A menu-bar icon
  (`src/mtgcv/macapp.py`, using `rumps`, a macOS-only dependency) offers Open GraphMTG / Show data folder / Quit.
  uvicorn runs in a background thread (it skips signal handlers off the main thread) and stops via `should_exit`.
  Output goes to `<data dir>/graphmtg.log`. If the server dies, an alert points at the log. Chosen over a Terminal
  window (unpolished) or a windowless app that quits when the browser closes (hard to tell if it's running).
- `launcher.main()` picks the menu-bar front end on macOS when frozen (or `GRAPHMTG_MENUBAR=1`;
  `GRAPHMTG_CONSOLE=1` forces the console). Single-instance, port and browser handling are shared with Windows.
- **Data folders on macOS** follow Apple's conventions: `~/Library/Application Support/mtg-card-view` (collections) and
  `~/Library/Caches/mtg-card-view` (cache), replacing the XDG fallbacks there. Linux is unchanged.
- **Build:** the same `packaging/GraphMTG.spec` branches on platform. macOS makes a folder-based `.app` bundle
  (PyInstaller 6 deprecates one-file `.app`s) for `arm64`, zipped with `ditto` as `GraphMTG-mac.zip`.
  `packaging/make_icon.py` also writes `graphmtg.icns` and a black-on-transparent menu-bar template icon.
- **CI:** a `mac` job (macos-latest) tests, builds and smoke-tests the app by running the real menu-bar binary. A
  separate `release` job publishes both platforms' files once both builds pass.
- **Not notarized:** users must allow it once via System Settings → Privacy & Security → Open Anyway. Notarization
  needs the Apple Developer Program ($99/yr) and can be added to the `mac` job later. No Intel build.

## D-023 · 2026-11-17 · Accepted
**Graph: cards can no longer be dragged; dragging anywhere pans** (requested by the user). Supersedes the
"drag cards to arrange" part of the graph view decisions (D-014 to D-017).

- A press-and-drag on a card or on empty space pans the view. A click without movement still selects the card (or
  clears the selection on empty space). Hover highlighting and previews are unchanged.
- The computed layout is still saved per collection and mode, so it stays stable and new cards are placed around
  existing ones. Layouts saved with manual arrangements from before this change are kept until **Reset layout**,
  which recomputes the layout (its confirmation text was updated).

## D-024 · 2026-11-17 · Accepted
**Resizable sidebars** (requested by the user; the details below are defaults Claude picked, open to change).

- Drag the inner edge of the collections sidebar (left) or the card panel (right) to resize it. The handle is an
  invisible 8px strip that shows an accent line on hover. Double-click restores the default width. When focused,
  arrow keys resize it (Shift for bigger steps).
- Widths are saved per browser in localStorage (`mtgcv.width.left|detail|pair`). The single-card panel and the
  two-card panel (graph synergy pair) remember separate widths.
- Limits: left 160 to 480px (default 220). Card panel at least 280px (default 360). Two-card panel at least 480px
  (default 720). The main area always keeps at least 360px, and widths are re-clamped when the window shrinks.
- Below 900px wide, the handles are hidden and the existing stacked/overlay layout applies.
- Implementation: `components/Resizer.tsx` (handle + `useStoredWidth`). App sets `--left-w` / `--right-w` on `.app`,
  and the grid columns use those variables.

## D-025 · 2026-11-18 · Accepted
**Graph view: right-click a card to compare it with the selected card** (requested by the user; the edge cases
below are defaults Claude picked, open to change). Extends D-019.

- With a card selected, right-clicking another card on the canvas opens it in the second sidebar with the synergy
  box, the same as clicking a synergy link. The two cards do not need to be linked: the box then says no theme
  links them.
- Right-clicking the card already open in the second sidebar closes it, matching the link toggle. Right-clicking
  the selected card, empty space, or any card when nothing is selected does nothing.
- The browser's context menu is suppressed on the graph canvas.

## D-026 · 2026-11-18 · Accepted
**Right-click hint in the card panel** (requested by the user; placement chosen by the user from options; wording
is Claude's default). Extends D-025.

- **Hint:** in the graph view, the single-card panel shows a muted line under the card image. On Windows/Linux it
  says "Right-click another card in the graph to compare it with this one." On macOS (detected from
  `navigator.platform`) it says "Control-click (or two-finger click)" instead. It's hidden once the pair is open.
  The README documents both platforms.
- **macOS Control-click:** the browser sends a left press, then `contextmenu` on press. The canvas now drops the
  pending press in its `contextmenu` handler, so the release doesn't select the card and close the pair.
- A set filter was built alongside this and then dropped at the user's request before release. Note for a future
  attempt: each card keeps only one printing (ManaBox import keeps the first, D-018), so a card owned in several sets
  would count under one set only.

## D-027 · 2026-11-19 · Accepted
**EDHREC lift as a third graph weighting** (requested by the user; label, slider range and default threshold are
Claude's defaults, open to change). Extends D-014..D-017.

- New graph mode `lift` ("EDHREC lift" button, after the two existing ones). It builds the same commander <-> card
  graph as `edhrec` (same hubs, top 5 commanders per card, basic lands excluded) but weights edges by lift instead of
  synergy. Edges need lift > 1. Layouts are saved separately per mode, as before.
- Lift = inclusion rate with the commander / rate in all decks of those colors. Its ceiling varies a lot by commander
  (Atraxa about 1.7×, Krenko about 8×), so the slider runs 1–8× with a default of 1.2×, and edge strength is
  log-scaled (8× = full).
- The two-card synergy box shows lift next to synergy for listed cards.
- `CommanderPage` now stores lift. The EDHREC cache gained a format version, so pages cached without lift are
  re-fetched (once) the next time an EDHREC mode is opened.

## D-028 · 2026-11-19 · Accepted
**Each graph view can be switched off in code** (requested by the user, e.g. to stop the app pulling data from
EDHREC; the mechanism is Claude's default).

- `src/mtgcv/features.py` holds `GRAPH_MODES = {"tags": True, "edhrec": True, "lift": True}`. Edit it and restart
  (or rebuild the exe). No env var or UI setting, by design: it's a build-time choice.
- The server is the single authority. `/api/config` returns the enabled modes in display order, and the UI shows only
  those buttons, falling back to the first enabled mode. `/api/decks/{id}/graph` returns 404 for a disabled mode.
- With both EDHREC modes (`edhrec`, `lift`) off, `create_app` never constructs an `EdhrecClient`, so there is no HTTP
  client for EDHREC and no `edhrec.sqlite3`. The pair endpoint returns `"edhrec": null` and the synergy box drops its
  EDHREC section. EDHREC rank and the "EDHREC" card link come from Scryfall data and are unaffected.
- At least one mode must stay enabled (the graph is the main view); otherwise the server refuses to start.

