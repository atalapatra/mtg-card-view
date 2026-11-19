import httpx

from mtgcv.analyze import CardInfo
from mtgcv.edhrec import CommanderPage, EdhrecClient, edhrec_slug
from mtgcv.scryfall import TagIndex
from mtgcv.synergy import build_edhrec_graph, build_tag_graph, commander_hubs


def card(name, type_line="Creature — Elf", tags=(), **kw):
    oid = f"o-{name}"
    return CardInfo(name=name, quantity=1, section=kw.pop("section", "main"), oracle_id=oid,
                    type_line=type_line, **kw), (oid, tags)


def make(*specs):
    cards, records = [], {}
    for c, (oid, tags) in specs:
        cards.append(c)
        for t in tags:
            records.setdefault(t, []).append(oid)
    idx = TagIndex.from_records([{"label": t, "oracle_ids": o} for t, o in records.items()])
    return cards, idx


def edge_names(graph, cards_by_key=None):
    out = {}
    for s, t, w, l in graph.edges:
        a, b = sorted([graph.nodes[s].split(":", 1)[1], graph.nodes[t].split(":", 1)[1]])
        out[(a, b)] = (w, graph.labels[l] if l >= 0 else None)
    return out


def test_slug():
    assert edhrec_slug("Atraxa, Praetors' Voice") == "atraxa-praetors-voice"
    assert edhrec_slug("Lim-Dûl the Necromancer") == "lim-dul-the-necromancer"
    assert edhrec_slug("Esika, God of the Tree // The Prismatic Bridge") == "esika-god-of-the-tree"


def test_tag_graph_payoff_enabler_and_typal():
    cards, idx = make(
        card("Ajani's Pridemate", "Creature — Cat Soldier", ["lifegain-matters"]),
        card("Soul Warden", "Creature — Human Cleric", ["lifegain"], categories=["Lifegain"]),
        card("Elvish Archdruid", "Creature — Elf Druid", ["typal-elf"]),
        card("Llanowar Elves", "Creature — Elf Druid"),
        card("Island", "Basic Land — Island"),
    )
    g = build_tag_graph(cards, idx)
    edges = edge_names(g)
    assert edges[("Ajani's Pridemate", "Soul Warden")] == (1.0, "Lifegain")
    assert edges[("Elvish Archdruid", "Llanowar Elves")] == (1.0, "Typal: Elf")
    assert g.to_dict()["unconnected"] == 1  # Island
    assert ("Ajani's Pridemate", "Llanowar Elves") not in edges


def test_typal_requires_real_subtype_and_counts_once():
    cards, idx = make(
        card("Lord of Many", "Creature — Shapeshifter", ["typal-elf", "typal-goblin", "typal-army"]),
        card("Llanowar Elves", "Creature — Elf Druid"),
        card("Goblin Guide", "Creature — Goblin Scout"),
        card("Mirror Entity", "Creature — Shapeshifter", keywords=["Changeling"]),
    )
    edges = edge_names(build_tag_graph(cards, idx))
    assert edges[("Llanowar Elves", "Lord of Many")] == (1.0, "Typal: Elf")
    assert edges[("Lord of Many", "Mirror Entity")] == (1.0, "Typal: Elf, Typal: Goblin")  # no Army
    assert not any("Army" in (label or "") for _, label in edges.values())


def test_tag_graph_caps_edges_per_card():
    specs = [card("Payoff", "Creature — Cat", ["synergy-artifact"])]
    specs += [card(f"Rock {i:02d}", "Artifact", edhrec_rank=i) for i in range(20)]
    cards, idx = make(*specs)
    g = build_tag_graph(cards, idx, k=5)
    # Each rock keeps its only edge (top-k of the rock), so all 20 survive via the rock side.
    assert len(g.edges) == 20
    # But a payoff-side-only cap is respected when the other side has many options:
    specs2 = [card(f"Payoff {i}", "Creature — Cat", ["synergy-artifact"], edhrec_rank=i) for i in range(10)]
    specs2 += [card(f"Rock {i:02d}", "Artifact", edhrec_rank=100 + i) for i in range(10)]
    cards2, idx2 = make(*specs2)
    g2 = build_tag_graph(cards2, idx2, k=3)
    deg = {}
    for s, t, *_ in g2.edges:
        deg[s] = deg.get(s, 0) + 1
        deg[t] = deg.get(t, 0) + 1
    assert len(g2.edges) < 100 and max(deg.values()) <= 10


def test_edhrec_graph():
    cards, _ = make(
        card("Atraxa, Praetors' Voice", "Legendary Creature — Phyrexian Angel Horror"),
        card("Doubling Season", "Enchantment"),
        card("Sol Ring", "Artifact"),
        card("Grizzly Bears", "Creature — Bear"),
    )
    page = CommanderPage(slug="atraxa-praetors-voice", num_decks=100,
                         cards={"doubling season": (0.45, 50, 100, 3.2), "sol ring": (0.0, 90, 100, 1.0)})
    assert [h.name for h in commander_hubs(cards)] == ["Atraxa, Praetors' Voice"]
    g = build_edhrec_graph(cards, {"atraxa-praetors-voice": page})
    edges = edge_names(g)
    assert edges == {("Atraxa, Praetors' Voice", "Doubling Season"): (0.45, None)}
    assert g.hubs == ["main:Atraxa, Praetors' Voice"]
    assert g.to_dict()["unconnected"] == 2

    g2 = build_edhrec_graph(cards, {})
    assert g2.meta["missing_pages"] == ["Atraxa, Praetors' Voice"]

    # Lift mode: same hubs, weighted by lift; lift <= 1 (Sol Ring) is no edge.
    g3 = build_edhrec_graph(cards, {"atraxa-praetors-voice": page}, metric="lift")
    assert g3.mode == "lift"
    assert edge_names(g3) == {("Atraxa, Praetors' Voice", "Doubling Season"): (3.2, None)}


def test_edhrec_page_parse_and_cache(tmp_path):
    calls = []
    payload = {"container": {"json_dict": {"card": {"num_decks": 1234}, "cardlists": [
        {"cardviews": [{"name": "Doubling Season", "synergy": 0.4, "lift": 2.5, "num_decks": 10,
                        "potential_decks": 20}]}]}}}

    def handler(req):
        calls.append(req.url.path)
        if req.url.path.endswith("atraxa-praetors-voice.json"):
            return httpx.Response(200, json=payload)
        return httpx.Response(404)

    client = EdhrecClient(cache_dir=tmp_path, http=httpx.Client(transport=httpx.MockTransport(handler)), interval=0)
    page = client.fetch("atraxa-praetors-voice")
    assert page.num_decks == 1234 and page.cards["doubling season"] == (0.4, 10, 20, 2.5)
    assert client.fetch("not-a-commander") is None
    assert client.missing(["atraxa-praetors-voice", "not-a-commander", "other"]) == ["other"]
    assert client.get_pages(["atraxa-praetors-voice"])["atraxa-praetors-voice"].cards == page.cards

    # Entries cached before lift was stored (no format version) count as not cached, so they're re-fetched.
    client._db.execute("UPDATE pages SET data = ? WHERE slug = ?",
                       ('{"num_decks": 1, "cards": {"doubling season": [0.4, 10, 20]}}', "atraxa-praetors-voice"))
    assert client.missing(["atraxa-praetors-voice"]) == ["atraxa-praetors-voice"]


def test_explain_pair_themes_and_typal():
    from mtgcv.synergy import explain_pair
    cards, idx = make(
        card("Ajani's Pridemate", "Creature — Cat Soldier", ["lifegain-matters"]),
        card("Soul Warden", "Creature — Human Cleric", ["lifegain"], categories=["Lifegain"]),
        card("Elvish Archdruid", "Creature — Elf Druid", ["typal-elf"]),
        card("Llanowar Elves", "Creature — Elf Druid"),
    )
    pridemate, warden, archdruid, elves = cards
    # Order of arguments doesn't matter: payoff/enabler roles are detected.
    exp = explain_pair(warden, pridemate, idx, {})
    assert exp["themes"] == [{
        "theme": "Lifegain", "payoff": "main:Ajani's Pridemate", "enabler": "main:Soul Warden",
        "payoff_reasons": ["lifegain-matters"], "enabler_reasons": ["Lifegain category"],
    }]
    assert exp["edhrec"] == []  # neither is a commander
    typal = explain_pair(archdruid, elves, idx, {})["themes"]
    assert typal == [{"theme": "Typal: Elf", "payoff": "main:Elvish Archdruid", "enabler": "main:Llanowar Elves",
                      "payoff_reasons": ["typal-elf"], "enabler_reasons": ["Elf creature"]}]


def test_explain_pair_edhrec_statuses():
    from mtgcv.synergy import explain_pair
    cards, idx = make(
        card("Atraxa, Praetors' Voice", "Legendary Creature — Phyrexian Angel Horror"),
        card("Doubling Season", "Enchantment"),
        card("Grizzly Bears", "Creature — Bear"),
    )
    atraxa, season, bears = cards
    page = CommanderPage(slug="atraxa-praetors-voice", num_decks=1000,
                         cards={"doubling season": (0.45, 500, 900, 1.9)})
    pages = {"atraxa-praetors-voice": page}
    [e] = explain_pair(season, atraxa, idx, pages)["edhrec"]
    assert e == {"commander": "main:Atraxa, Praetors' Voice", "card": "main:Doubling Season", "status": "listed",
                 "commander_decks": 1000, "synergy": 0.45, "num_decks": 500, "potential_decks": 900,
                 "lift": 1.9}
    assert explain_pair(atraxa, bears, idx, pages)["edhrec"][0]["status"] == "not_listed"
    assert explain_pair(atraxa, bears, idx, {})["edhrec"][0]["status"] == "not_downloaded"
    assert explain_pair(atraxa, bears, idx, {"atraxa-praetors-voice": None})["edhrec"][0]["status"] == "no_page"
