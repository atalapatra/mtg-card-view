"""API tests: FastAPI TestClient + mocked Scryfall (no network)."""

import time

import httpx
import pytest
from fastapi.testclient import TestClient

from mtgcv.edhrec import EdhrecClient
from mtgcv.server import create_app
from mtgcv.store import DeckStore
from test_scryfall_and_analyze import make_client

DECK = "Commander\n1 Sol Ring\nDeck\n1 Swords to Plowshares\n1 Wrath of God\n2 Lightning Bolt\n1 Command Tower\n"


@pytest.fixture
def api(tmp_path, monkeypatch):
    monkeypatch.setattr("mtgcv.scryfall.MIN_INTERVAL", 0)
    edhrec_http = httpx.Client(transport=httpx.MockTransport(lambda req: httpx.Response(404)))
    app = create_app(store=DeckStore(tmp_path / "decks.sqlite3"),
                     client=make_client(tmp_path, []), web_dist=None,
                     edhrec=EdhrecClient(cache_dir=tmp_path, http=edhrec_http, interval=0))
    return TestClient(app)


def test_import_manabox(api):
    from pathlib import Path
    csv_text = (Path(__file__).parent / "fixtures" / "manabox_sample.csv").read_text(encoding="utf-8")
    r = api.post("/api/import/manabox", json={"csv": csv_text})
    assert r.status_code == 200
    assert "2 Sol Ring (TDC) 106" in r.json()["text"] and r.json()["skipped_tokens"] == 7
    r = api.post("/api/import/manabox", json={"csv": csv_text, "include_lists": True})
    assert "Rhystic Study" in r.json()["text"]
    assert api.post("/api/import/manabox", json={"csv": "a,b\n1,2\n"}).status_code == 422


def test_pair_endpoint(api):
    deck_id = api.post("/api/decks", json={"name": "D", "text": DECK}).json()["deck"]["id"]
    r = api.get(f"/api/decks/{deck_id}/pair", params={"a": "main:Swords to Plowshares", "b": "main:Wrath of God"})
    assert r.status_code == 200
    assert "Removal" in r.json()["shared_categories"] and r.json()["edhrec"] == []
    r = api.get(f"/api/decks/{deck_id}/pair", params={"a": "commander:Sol Ring", "b": "main:Wrath of God"})
    assert [e["status"] for e in r.json()["edhrec"]] == ["not_downloaded"]  # cache only, never fetches
    assert api.get(f"/api/decks/{deck_id}/pair", params={"a": "main:Nope", "b": "main:Wrath of God"}).status_code == 404


def test_graph_endpoints(api):
    deck_id = api.post("/api/decks", json={"name": "D", "text": DECK}).json()["deck"]["id"]
    r = api.get(f"/api/decks/{deck_id}/graph", params={"mode": "tags"})
    assert r.status_code == 200 and r.json()["status"] == "ready"
    g = r.json()["graph"]
    assert len(g["nodes"]) == 5 and r.json()["layout"] is None

    # EDHREC mode: the Commander-section card is a hub; its page is fetched in the
    # background (mock returns 404), so poll until ready.
    r = api.get(f"/api/decks/{deck_id}/graph", params={"mode": "edhrec"})
    for _ in range(50):
        if r.json()["status"] == "ready":
            break
        assert r.json()["progress"]["total"] == 1
        time.sleep(0.05)
        r = api.get(f"/api/decks/{deck_id}/graph", params={"mode": "edhrec"})
    g = r.json()["graph"]
    assert g["hubs"] == ["commander:Sol Ring"] and g["meta"]["missing_pages"] == ["Sol Ring"]
    assert g["edges"] == []
    assert api.get(f"/api/decks/{deck_id}/graph", params={"mode": "bogus"}).status_code == 422

    pos = {"main:Wrath of God": [1.5, -2.0]}
    assert api.put(f"/api/decks/{deck_id}/graph-layout/tags", json={"positions": pos}).status_code == 204
    assert api.get(f"/api/decks/{deck_id}/graph", params={"mode": "tags"}).json()["layout"] == pos
    assert api.delete(f"/api/decks/{deck_id}/graph-layout/tags").status_code == 204
    assert api.get(f"/api/decks/{deck_id}/graph", params={"mode": "tags"}).json()["layout"] is None
    assert api.put("/api/decks/999/graph-layout/tags", json={"positions": pos}).status_code == 404


def test_analyze(api):
    r = api.post("/api/analyze", json={"text": DECK})
    assert r.status_code == 200
    data = r.json()
    keys = {c["key"] for c in data["cards"]}
    assert "commander:Sol Ring" in keys and "main:Lightning Bolt" in keys
    removal = next(g for g in data["groupings"]["category"] if g["name"] == "Removal")
    assert set(removal["cards"]) == {"main:Swords to Plowshares", "main:Wrath of God", "main:Lightning Bolt"}
    assert set(data["groupings"]) >= {"category", "primary", "type", "cmc", "color", "section"}


def test_deck_and_board_lifecycle(api):
    r = api.post("/api/decks", json={"name": "Test", "text": DECK})
    assert r.status_code == 201
    deck_id = r.json()["deck"]["id"]
    assert r.json()["deck"]["card_count"] == 6

    assert [d["name"] for d in api.get("/api/decks").json()] == ["Test"]

    r = api.post(f"/api/decks/{deck_id}/boards", json={"name": "My groups", "seed": "primary"})
    assert r.status_code == 201
    board = r.json()
    names = [g["name"] for g in board["layout"]["groups"]]
    assert names[:3] == ["Land", "Board Wipe", "Removal"]
    placed = [k for g in board["layout"]["groups"] for k in g["cards"]]
    assert len(placed) == len(set(placed)) == 5  # each card placed exactly once

    layout = {"groups": [{"id": "x", "name": "Interaction",
                          "cards": ["main:Swords to Plowshares", "main:Wrath of God"]}]}
    r = api.patch(f"/api/boards/{board['id']}", json={"name": "Renamed", "layout": layout})
    assert r.json()["name"] == "Renamed"
    assert r.json()["layout"] == layout

    dup = {"groups": [{"id": "a", "name": "A", "cards": ["main:Wrath of God"]},
                      {"id": "b", "name": "B", "cards": ["main:Wrath of God", "main:Lightning Bolt"]}]}
    r = api.patch(f"/api/boards/{board['id']}", json={"layout": dup})
    assert [g["cards"] for g in r.json()["layout"]["groups"]] == [["main:Wrath of God"], ["main:Lightning Bolt"]]
    api.patch(f"/api/boards/{board['id']}", json={"layout": layout})

    detail = api.get(f"/api/decks/{deck_id}").json()
    assert detail["boards"][0]["layout"] == layout

    r = api.patch(f"/api/decks/{deck_id}", json={"text": DECK + "1 Fire // Ice\n"})
    assert any(c["name"] == "Fire // Ice" for c in r.json()["report"]["cards"])

    assert api.delete(f"/api/boards/{board['id']}").status_code == 204
    assert api.delete(f"/api/decks/{deck_id}").status_code == 204
    assert api.get(f"/api/decks/{deck_id}").status_code == 404
    assert api.delete(f"/api/boards/{board['id']}").status_code == 404


def test_empty_seed_and_validation(api):
    deck_id = api.post("/api/decks", json={"name": "D", "text": DECK}).json()["deck"]["id"]
    board = api.post(f"/api/decks/{deck_id}/boards", json={"name": "Blank", "seed": "empty"}).json()
    assert board["layout"] == {"groups": []}
    assert api.post("/api/decks", json={"name": "", "text": DECK}).status_code == 422
    assert api.post(f"/api/decks/{deck_id}/boards", json={"name": "x", "seed": "bogus"}).status_code == 422
