"""Offline tests: Scryfall is replaced with an httpx.MockTransport."""

import gzip
import json

import httpx
import pytest

from mtgcv.analyze import build_report, group_cards
from mtgcv.cache import CardCache
from mtgcv.categories import categorize
from mtgcv.decklist import parse_decklist
from mtgcv.scryfall import ScryfallClient, TagIndex, normalize_name

CARDS = {
    "Sol Ring": {"name": "Sol Ring", "oracle_id": "o-sol", "cmc": 1, "mana_cost": "{1}",
                 "type_line": "Artifact", "edhrec_rank": 1, "color_identity": [],
                 "produced_mana": ["C"], "prices": {"usd": "1.50"}},
    "Swords to Plowshares": {"name": "Swords to Plowshares", "oracle_id": "o-stp", "cmc": 1,
                             "mana_cost": "{W}", "type_line": "Instant", "edhrec_rank": 20,
                             "color_identity": ["W"]},
    "Wrath of God": {"name": "Wrath of God", "oracle_id": "o-wrath", "cmc": 4,
                     "mana_cost": "{2}{W}{W}", "type_line": "Sorcery", "edhrec_rank": 300,
                     "color_identity": ["W"]},
    "Fire // Ice": {"name": "Fire // Ice", "oracle_id": "o-fire", "cmc": 4,
                    "type_line": "Instant // Instant", "edhrec_rank": 900,
                    "color_identity": ["U", "R"],
                    "card_faces": [
                        {"name": "Fire", "mana_cost": "{1}{R}",
                         "oracle_text": "Fire deals 2 damage divided as you choose among one or two targets."},
                        {"name": "Ice", "mana_cost": "{1}{U}",
                         "oracle_text": "Tap target permanent.\nDraw a card."},
                    ]},
    "Lim-Dûl the Necromancer": {"name": "Lim-Dûl the Necromancer", "oracle_id": "o-lim", "cmc": 7,
                                "type_line": "Legendary Creature — Human Wizard",
                                "color_identity": ["B"]},
    "Command Tower": {"name": "Command Tower", "oracle_id": "o-tower", "cmc": 0,
                      "type_line": "Land", "edhrec_rank": 2, "color_identity": [],
                      "produced_mana": ["W", "U", "B", "R", "G"]},
    "Lightning Bolt": {"name": "Lightning Bolt", "oracle_id": "o-bolt", "cmc": 1,
                       "type_line": "Instant", "edhrec_rank": 50, "color_identity": ["R"]},
}

def _tg(*oids, weight="median"):
    return [{"oracle_id": o, "weight": weight} for o in oids]


# Mirrors the real bulk format: direct taggings only, hierarchy via parent_ids,
# inconsistent label styles ("mana rock"), and aliases.
TAGS = [
    {"id": "t-ramp", "label": "ramp", "description": "More mana.", "parent_ids": [],
     "aliases": ["acceleration"], "taggings": []},
    {"id": "t-rock", "label": "mana rock", "parent_ids": ["t-ramp"], "aliases": [],
     "taggings": _tg("o-sol", weight="very_strong")},
    {"id": "t-removal", "label": "removal", "parent_ids": [], "taggings": []},
    {"id": "t-spot", "label": "spot-removal", "parent_ids": ["t-removal"],
     "taggings": _tg("o-stp", "o-bolt", "o-fire")},
    {"id": "t-sweeper", "label": "board wipe", "parent_ids": ["t-removal"],
     "aliases": ["sweeper"], "taggings": _tg("o-wrath")},
    {"id": "t-draw", "label": "draw", "parent_ids": [], "taggings": _tg("o-fire")},
]

FLAT_TAGS = [
    {"label": "removal", "oracle_ids": ["o-stp", "o-wrath"]},
    {"label": "sweeper", "oracle_ids": ["o-wrath"]},
]


def _names(card):
    return {normalize_name(card["name"])} | {normalize_name(f["name"]) for f in card.get("card_faces", [])}


def make_client(tmp_path, calls):
    def handler(request: httpx.Request) -> httpx.Response:
        calls.append((request.method, request.url.host, request.url.path))
        if request.url.path == "/cards/collection":
            data, nf = [], []
            for ident in json.loads(request.content)["identifiers"]:
                key = normalize_name(ident["name"])
                card = next((c for c in CARDS.values() if key in _names(c)), None)
                if card:
                    data.append(card)
                else:
                    nf.append(ident)
            return httpx.Response(200, json={"data": data, "not_found": nf})
        if request.url.path == "/cards/named":
            if request.url.params.get("fuzzy") == "Lightnig Bolt":
                return httpx.Response(200, json=CARDS["Lightning Bolt"])
            return httpx.Response(404, json={"object": "error"})
        if request.url.path == "/bulk-data/oracle-tags":
            return httpx.Response(200, json={"updated_at": "2026-01-01",
                                             "jsonl_download_uri": "https://data.example/tags.jsonl.gz"})
        if request.url.host == "data.example":
            payload = "\n".join(json.dumps(t) for t in TAGS).encode()
            return httpx.Response(200, content=gzip.compress(payload))
        return httpx.Response(404)

    http = httpx.Client(transport=httpx.MockTransport(handler))
    return ScryfallClient(cache=CardCache(tmp_path), http=http)


@pytest.fixture(autouse=True)
def no_throttle(monkeypatch):
    monkeypatch.setattr("mtgcv.scryfall.MIN_INTERVAL", 0)


def test_lookup_matching_cache_and_fuzzy(tmp_path):
    calls = []
    client = make_client(tmp_path, calls)
    names = ["Sol Ring", "Fire // Ice", "Lim-Dul the Necromancer", "Lightnig Bolt", "Not A Card"]
    found, missing = client.get_cards(names)
    assert set(found) == {"Sol Ring", "Fire // Ice", "Lim-Dul the Necromancer", "Lightnig Bolt"}
    assert found["Fire // Ice"]["name"] == "Fire // Ice"
    assert found["Lightnig Bolt"]["name"] == "Lightning Bolt"
    assert missing == ["Not A Card"]

    calls.clear()
    found2, _ = client.get_cards(["Sol Ring", "sol ring"])
    assert set(found2) == {"Sol Ring", "sol ring"}
    assert calls == []  # served from cache


def test_tags_download_and_report(tmp_path):
    calls = []
    client = make_client(tmp_path, calls)
    deck = parse_decklist("Commander\n1 Sol Ring\nDeck\n1 Swords to Plowshares\n1 Wrath of God\n"
                          "1 Fire // Ice\n1 Command Tower\n2 Lightning Bolt\n")
    report = build_report(deck, client)
    by = {c.name: c for c in report.cards}
    assert by["Sol Ring"].categories == ["Ramp"]
    assert by["Sol Ring"].tags == ["mana-rock", "ramp"]  # inherited parent + slugified label
    assert by["Sol Ring"].strong_tags == ["mana-rock"]
    assert by["Wrath of God"].tags == ["board-wipe", "removal"]
    assert by["Wrath of God"].primary_category == "Board Wipe"  # matched via alias "sweeper"
    assert by["Fire // Ice"].categories == ["Removal", "Card Advantage"]
    assert by["Fire // Ice"].mana_cost == "{1}{R} // {1}{U}"
    assert by["Command Tower"].categories == ["Land", "Fixing"]

    removal = next(g for g in group_cards(report.cards, "category", "edhrec") if g.name == "Removal")
    assert [c.name for c in removal.cards] == ["Swords to Plowshares", "Lightning Bolt",
                                               "Wrath of God", "Fire // Ice"]
    assert removal.count == 5  # Lightning Bolt x2

    assert [g.name for g in group_cards(report.cards, "type")] == ["Land", "Instant", "Sorcery", "Artifact"]
    assert [g.name for g in group_cards(report.cards, "section")] == ["commander", "main"]

    data = report.to_dict("primary", "cmc")
    assert data["summary"]["lands"] == 1
    assert data["summary"]["category_counts"]["Removal"] == 5
    assert data["tag_descriptions"] == {"ramp": "More mana."}

    # Tags are cached: a second load within a day makes no requests
    calls.clear()
    client.load_oracle_tags()
    assert calls == []


def test_category_refinements():
    cultivate = {"type_line": "Sorcery"}
    assert categorize(cultivate, {"ramp", "tutor", "tutor-land-basic", "tutor-to-battlefield"}) == ["Ramp"]
    assert "Tutor" in categorize({"type_line": "Sorcery"}, {"tutor", "tutor-card", "tutor-to-hand"})
    stp = {"type_line": "Instant"}
    assert categorize(stp, {"removal", "lifegain", "opponent-lifegain"}) == ["Removal"]


def test_land_not_counted_as_ramp():
    assert categorize({"type_line": "Land", "produced_mana": ["G"]}, {"ramp", "mana-producer"}) == ["Land"]
    assert "Ramp" in categorize({"type_line": "Land"}, {"ramp", "land-ramp"})


def test_tagindex_hierarchy_and_aliases():
    idx = TagIndex.from_records(TAGS)
    assert idx.tags_for("o-wrath") == {"removal", "board-wipe"}
    assert idx.match_tags_for("o-wrath") == {"removal", "board-wipe", "sweeper"}
    assert idx.parents["spot-removal"] == {"removal"}
    assert idx.tags_for(None) == set()


def test_tagindex_flat_format():
    idx = TagIndex.from_records(FLAT_TAGS)
    assert idx.tags_for("o-wrath") == {"removal", "sweeper"}
