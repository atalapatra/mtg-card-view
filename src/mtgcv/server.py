"""HTTP API for the web UI (FastAPI).

    mtgcv serve            # http://127.0.0.1:8000 ; serves web/dist if it has been built

Endpoints (all JSON, under /api):
    POST   /analyze                 {text}           -> report (no saving)
    GET    /decks                                    -> [deck summary]
    POST   /decks                   {name, text}     -> deck detail
    GET    /decks/{id}                               -> deck detail
    PATCH  /decks/{id}              {name?, text?}   -> deck detail
    DELETE /decks/{id}
    POST   /decks/{id}/boards       {name, seed?}    -> board
    PATCH  /boards/{id}             {name?, layout?} -> board
    DELETE /boards/{id}
    GET    /categories                               -> category names + descriptions

"Deck detail" = {deck, report, boards}. The report contains every card plus group
membership for all built-in grouping modes, so the UI can switch views instantly.
"""

from __future__ import annotations

import hashlib
import threading
import time
from collections import OrderedDict
from pathlib import Path
from typing import Literal

from fastapi import FastAPI, HTTPException
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from mtgcv.analyze import GROUP_MODES, Report, build_report, group_cards
from mtgcv.categories import CATEGORIES
from mtgcv.decklist import parse_decklist
from mtgcv.edhrec import EdhrecClient, EdhrecFetcher, edhrec_slug
from mtgcv.importers import manabox_to_decklist
from mtgcv.scryfall import ScryfallClient, TagIndex
from mtgcv.store import DeckStore, NotFound
from mtgcv.synergy import Graph, build_edhrec_graph, build_tag_graph, commander_hubs

TAGS_RELOAD_SECONDS = 24 * 3600
WEB_DIST = Path(__file__).resolve().parents[2] / "web" / "dist"


# --- request models ---------------------------------------------------------------

class AnalyzeIn(BaseModel):
    text: str


class DeckIn(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    text: str


class DeckPatch(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    text: str | None = None


class BoardGroup(BaseModel):
    id: str
    name: str
    cards: list[str] = []


class BoardLayout(BaseModel):
    groups: list[BoardGroup] = []


SeedMode = Literal["primary", "type", "cmc", "color", "section", "user_tag", "empty"]


class BoardIn(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    seed: SeedMode = "primary"


class BoardPatch(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    layout: BoardLayout | None = None


class ManaboxIn(BaseModel):
    csv: str
    include_tokens: bool = False
    include_lists: bool = False


GraphMode = Literal["tags", "edhrec"]


class GraphLayoutIn(BaseModel):
    positions: dict[str, tuple[float, float]]


# --- app ------------------------------------------------------------------------

class Analyzer:
    """Holds the Scryfall client and in-memory tag index; serializes Scryfall access.

    Reports (and tag graphs) are memoized per deck text so big libraries don't get
    re-analyzed on every request.
    """

    CACHE_SIZE = 8

    def __init__(self, client: ScryfallClient):
        self.client = client
        self._lock = threading.Lock()
        self._tags: TagIndex | None = None
        self._tags_loaded = 0.0
        self._memo: OrderedDict[tuple[str, str], object] = OrderedDict()

    def tag_index(self) -> TagIndex:
        if self._tags is None or time.time() - self._tags_loaded > TAGS_RELOAD_SECONDS:
            self._tags = self.client.load_oracle_tags()
            self._tags_loaded = time.time()
            self._memo.clear()
        return self._tags

    def _memoized(self, kind: str, text: str, build):
        key = (kind, hashlib.sha1(text.encode("utf-8")).hexdigest())
        if key in self._memo:
            self._memo.move_to_end(key)
            return self._memo[key]
        value = build()
        self._memo[key] = value
        while len(self._memo) > self.CACHE_SIZE:
            self._memo.popitem(last=False)
        return value

    def report(self, text: str) -> Report:
        with self._lock:
            tags = self.tag_index()
            return self._memoized("report", text,
                                  lambda: build_report(parse_decklist(text), self.client, tags))

    def tag_graph(self, text: str) -> Graph:
        report = self.report(text)
        with self._lock:
            tags = self.tag_index()
            return self._memoized("tag_graph", text, lambda: build_tag_graph(report.cards, tags))


def create_app(store: DeckStore | None = None, client: ScryfallClient | None = None,
               web_dist: Path | None = WEB_DIST, edhrec: EdhrecClient | None = None) -> FastAPI:
    app = FastAPI(title="mtg-card-view")
    app.add_middleware(GZipMiddleware, minimum_size=2000)  # big libraries -> multi-MB JSON
    store = store or DeckStore()
    analyzer = Analyzer(client or ScryfallClient())
    fetcher = EdhrecFetcher(edhrec or EdhrecClient())

    def deck_summary(deck: dict) -> dict:
        parsed = parse_decklist(deck["text"])
        return {"id": deck["id"], "name": deck["name"],
                "card_count": sum(e.quantity for e in parsed.entries),
                "created_at": deck["created_at"], "updated_at": deck["updated_at"]}

    def deck_detail(deck: dict) -> dict:
        return {"deck": {**deck_summary(deck), "text": deck["text"]},
                "report": analyzer.report(deck["text"]).to_api_dict(),
                "boards": store.list_boards(deck["id"])}

    def get_or_404(fn, *args):
        try:
            return fn(*args)
        except NotFound as e:
            raise HTTPException(404, f"Not found: {e.args[0]}")

    @app.post("/api/analyze")
    def analyze(body: AnalyzeIn) -> dict:
        return analyzer.report(body.text).to_api_dict()

    @app.post("/api/import/manabox")
    def import_manabox(body: ManaboxIn) -> dict:
        """Convert a ManaBox CSV export to the plain card-list text (nothing is saved)."""
        try:
            return manabox_to_decklist(body.csv, body.include_tokens, body.include_lists).to_dict()
        except ValueError as e:
            raise HTTPException(422, str(e))

    @app.get("/api/decks")
    def list_decks() -> list[dict]:
        return [deck_summary(d) for d in store.list_decks()]

    @app.post("/api/decks", status_code=201)
    def create_deck(body: DeckIn) -> dict:
        return deck_detail(store.create_deck(body.name, body.text))

    @app.get("/api/decks/{deck_id}")
    def get_deck(deck_id: int) -> dict:
        return deck_detail(get_or_404(store.get_deck, deck_id))

    @app.patch("/api/decks/{deck_id}")
    def update_deck(deck_id: int, body: DeckPatch) -> dict:
        return deck_detail(get_or_404(store.update_deck, deck_id, body.name, body.text))

    @app.delete("/api/decks/{deck_id}", status_code=204)
    def delete_deck(deck_id: int) -> None:
        get_or_404(store.delete_deck, deck_id)

    @app.post("/api/decks/{deck_id}/boards", status_code=201)
    def create_board(deck_id: int, body: BoardIn) -> dict:
        deck = get_or_404(store.get_deck, deck_id)
        groups: list[dict] = []
        if body.seed != "empty":
            report = analyzer.report(deck["text"])
            for i, g in enumerate(group_cards(report.cards, body.seed, "name")):
                if g.name in ("(no tag)", "Not Found"):
                    continue  # leave these unsorted
                groups.append({"id": f"g{i + 1}", "name": g.name, "cards": []})
                for c in g.cards:
                    # user_tag can place a card in several groups; boards are single-placement
                    if not any(c.key in x["cards"] for x in groups):
                        groups[-1]["cards"].append(c.key)
        return store.create_board(deck_id, body.name, {"groups": groups})

    @app.patch("/api/boards/{board_id}")
    def update_board(board_id: int, body: BoardPatch) -> dict:
        layout = None
        if body.layout:
            # Boards are single-placement: keep only a card's first occurrence.
            seen: set[str] = set()
            layout = body.layout.model_dump()
            for g in layout["groups"]:
                g["cards"] = [k for k in g["cards"] if not (k in seen or seen.add(k))]
        return get_or_404(store.update_board, board_id, body.name, layout)

    @app.delete("/api/boards/{board_id}", status_code=204)
    def delete_board(board_id: int) -> None:
        get_or_404(store.delete_board, board_id)

    # --- synergy graph ---------------------------------------------------------
    @app.get("/api/decks/{deck_id}/graph")
    def get_graph(deck_id: int, mode: GraphMode = "tags") -> dict:
        """Graph for one weighting mode. In ``edhrec`` mode, missing commander pages
        are fetched in the background; the response is ``{"status": "loading",
        "progress": ...}`` until they're all cached — poll again."""
        deck = get_or_404(store.get_deck, deck_id)
        if mode == "tags":
            graph = analyzer.tag_graph(deck["text"])
        else:
            report = analyzer.report(deck["text"])
            slugs = [edhrec_slug(h.name) for h in commander_hubs(report.cards)]
            job = fetcher.ensure(deck_id, slugs)
            if job is not None:
                return {"status": "loading", "progress": {"done": job.done, "total": job.total}}
            graph = build_edhrec_graph(report.cards, fetcher.client.get_pages(slugs))
        return {"status": "ready", "graph": graph.to_dict(), "layout": store.get_layout(deck_id, mode)}

    @app.put("/api/decks/{deck_id}/graph-layout/{mode}", status_code=204)
    def save_graph_layout(deck_id: int, mode: GraphMode, body: GraphLayoutIn) -> None:
        get_or_404(store.save_layout, deck_id, mode, {k: list(v) for k, v in body.positions.items()})

    @app.delete("/api/decks/{deck_id}/graph-layout/{mode}", status_code=204)
    def delete_graph_layout(deck_id: int, mode: GraphMode) -> None:
        get_or_404(store.get_deck, deck_id)
        store.delete_layout(deck_id, mode)

    @app.get("/api/categories")
    def categories() -> dict:
        return {"categories": [{"name": c.name, "description": c.description} for c in CATEGORIES],
                "group_modes": GROUP_MODES}

    # Serve the built frontend (npm run build) if present.
    if web_dist and web_dist.is_dir():
        app.mount("/assets", StaticFiles(directory=web_dist / "assets"), name="assets")

        @app.get("/{path:path}", include_in_schema=False)
        def spa(path: str):
            if path.startswith("api/"):
                raise HTTPException(404)
            target = (web_dist / path).resolve()
            if path and target.is_file() and web_dist in target.parents:
                return FileResponse(target)
            return FileResponse(web_dist / "index.html")

    return app


def run(host: str = "127.0.0.1", port: int = 8000, open_browser: bool = False,
        reload: bool = False) -> None:
    import uvicorn

    if open_browser:
        import webbrowser
        threading.Timer(1.0, lambda: webbrowser.open(f"http://{host}:{port}")).start()
    if reload:
        uvicorn.run("mtgcv.server:create_app", factory=True, host=host, port=port, reload=True)
    else:
        uvicorn.run(create_app(), host=host, port=port)
