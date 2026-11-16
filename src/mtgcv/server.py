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

import threading
import time
from pathlib import Path
from typing import Literal

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from mtgcv.analyze import GROUP_MODES, build_report, group_cards
from mtgcv.categories import CATEGORIES
from mtgcv.decklist import parse_decklist
from mtgcv.scryfall import ScryfallClient, TagIndex
from mtgcv.store import DeckStore, NotFound

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


# --- app ------------------------------------------------------------------------

class Analyzer:
    """Holds the Scryfall client and in-memory tag index; serializes Scryfall access."""

    def __init__(self, client: ScryfallClient):
        self.client = client
        self._lock = threading.Lock()
        self._tags: TagIndex | None = None
        self._tags_loaded = 0.0

    def _tag_index(self) -> TagIndex:
        if self._tags is None or time.time() - self._tags_loaded > TAGS_RELOAD_SECONDS:
            self._tags = self.client.load_oracle_tags()
            self._tags_loaded = time.time()
        return self._tags

    def report(self, text: str):
        with self._lock:
            return build_report(parse_decklist(text), self.client, self._tag_index())


def create_app(store: DeckStore | None = None, client: ScryfallClient | None = None,
               web_dist: Path | None = WEB_DIST) -> FastAPI:
    app = FastAPI(title="mtg-card-view")
    store = store or DeckStore()
    analyzer = Analyzer(client or ScryfallClient())

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
