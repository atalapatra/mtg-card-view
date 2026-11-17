"""Synergy graphs between cards.

Two weighting modes (see docs/decisions.md D-014..D-017):

* ``tags``   – card <-> card edges from Scryfall Tagger tags, using a curated list
  of *themes*. Each theme pairs **payoffs** (cards that reward something, e.g.
  ``lifegain-matters``) with **enablers** (cards that provide it, e.g. lifegain).
  Edge weight = number of themes linking the pair.
* ``edhrec`` – commander <-> card edges weighted by EDHREC synergy. Every
  legendary creature (or "can be your commander" card, or card in the Commander
  section) in the list is a hub.

Both builders cap edges per card (top-k by weight) so libraries of thousands of
cards stay drawable. Cards with no edges are reported as unconnected.
"""

from __future__ import annotations

import re
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Callable, Iterable

from mtgcv.analyze import CardInfo
from mtgcv.edhrec import CommanderPage, edhrec_slug
from mtgcv.scryfall import TagIndex, front_face, normalize_name

TAG_EDGES_PER_CARD = 8
EDHREC_EDGES_PER_CARD = 5
EDHREC_MIN_SYNERGY = 0.01

# --- themes --------------------------------------------------------------------------

CardPred = Callable[[CardInfo, set[str]], bool]


@dataclass(frozen=True)
class Theme:
    name: str
    payoff_tags: frozenset[str] = frozenset()
    enabler_tags: frozenset[str] = frozenset()
    payoff_rule: CardPred | None = None
    enabler_rule: CardPred | None = None

    def is_payoff(self, card: CardInfo, tags: set[str]) -> bool:
        return bool(self.payoff_tags & tags) or bool(self.payoff_rule and self.payoff_rule(card, tags))

    def is_enabler(self, card: CardInfo, tags: set[str]) -> bool:
        return bool(self.enabler_tags & tags) or bool(self.enabler_rule and self.enabler_rule(card, tags))


def _t(*tags: str) -> frozenset[str]:
    return frozenset(tags)


def _front_type(c: CardInfo) -> str:
    return c.type_line.split(" // ")[0]


def _type(*words: str) -> CardPred:
    return lambda c, _t: any(w in _front_type(c) for w in words)


def _cat(name: str) -> CardPred:
    return lambda c, _t: name in c.categories


_ETB_RE = re.compile(r"\bwhen(?:ever)? [^.]*?\benters\b", re.IGNORECASE)
_TOKEN_RE = re.compile(r"\bcreates?\b[^.]*\btokens?\b", re.IGNORECASE)


def _etb(c: CardInfo, _tags: set[str]) -> bool:
    return any(t in _front_type(c) for t in ("Creature", "Artifact", "Enchantment")) and bool(
        _ETB_RE.search(c.oracle_text)
    )


def _makes_tokens(c: CardInfo, _tags: set[str]) -> bool:
    return bool(_TOKEN_RE.search(c.oracle_text))


def _any(*preds: CardPred) -> CardPred:
    return lambda c, t: any(p(c, t) for p in preds)


THEMES: list[Theme] = [
    Theme("Lifegain", _t("lifegain-matters", "synergy-lifegain"), enabler_rule=_cat("Lifegain")),
    Theme("Artifacts", _t("synergy-artifact", "artifact-count-matters", "synergy-artifact-creature"),
          _t("repeatable-artifact-tokens", "repeatable-treasures", "repeatable-clues", "repeatable-food"),
          enabler_rule=_type("Artifact")),
    Theme("Enchantments", _t("synergy-enchantment"), enabler_rule=_type("Enchantment")),
    Theme("Spellslinger", _t("synergy-instant", "synergy-sorcery", "prowess-like", "second-spell-matters",
                             "storm-count-matters"),
          enabler_rule=_type("Instant", "Sorcery")),
    Theme("+1/+1 Counters", _t("pp-counters-matter"), _t("gives-pp-counters", "repeatable-pp-counters")),
    Theme("Proliferate", _t("repeatable-proliferate", "pseudo-proliferate", "synergy-proliferate"),
          _t("gives-pp-counters", "repeatable-pp-counters"), enabler_rule=_type("Planeswalker")),
    Theme("Tokens", _t("synergy-token", "synergy-token-creature", "creature-count-matters", "token-doubler",
                       "copy-token"),
          _t("repeatable-token-generator", "repeatable-creature-tokens"), enabler_rule=_makes_tokens),
    Theme("Graveyard", _t("cards-in-graveyard-matter", "reanimate", "castable-from-graveyard",
                          "activate-from-graveyard", "synergy-graveyard-cast", "graveyard-fuel",
                          "card-types-in-graveyard-matter"),
          _t("mill-self", "self-mill", "discard-outlet", "wheel")),
    Theme("Sacrifice fodder", _t("sacrifice-outlet", "repeatable-sacrifice-outlet"),
          _t("repeatable-creature-tokens", "death-trigger-self", "leaves-body-behind", "multiple-bodies")),
    Theme("Death triggers", _t("death-trigger", "blood-artist-ability", "sacrifice-matters",
                               "your-sacrifice-matters"),
          _t("sacrifice-outlet", "repeatable-sacrifice-outlet")),
    Theme("Landfall", _t("landfall", "lands-matter", "land-count-matters"),
          _t("land-ramp", "extra-land", "multi-land-ramp")),
    Theme("Discard", _t("discard-matters", "self-discard-matters", "synergy-discard"),
          _t("discard-outlet", "wheel")),
    Theme("Card draw", _t("draw-matters", "second-draw-matters"), _t("repeatable-draw", "wheel")),
    Theme("Blink", _t("flicker", "blink"), enabler_rule=_etb),
    Theme("Equipment", _t("synergy-equipment"), enabler_rule=_type("Equipment")),
    Theme("Auras", _t("synergy-aura"), enabler_rule=_type("Aura")),
    Theme("Legends", _t("synergy-legendary"), enabler_rule=_type("Legendary")),
    Theme("Vehicles", _t("synergy-vehicle"), enabler_rule=_type("Vehicle")),
    Theme("Planeswalkers", _t("synergy-planeswalker"), enabler_rule=_type("Planeswalker")),
    Theme("Treasure", _t("synergy-treasure"), _t("repeatable-treasures")),
    Theme("Food", _t("synergy-food"), _t("repeatable-food")),
    Theme("Clues", _t("synergy-clue"), _t("repeatable-clues")),
    Theme("Mill", _t("synergy-mill"), _t("mill-opponent")),
    Theme("Combat", _t("attacking-matters"), _t("extra-combat", "gives-haste")),
]

# Tags shaped like typal-<subtype> that aren't a creature subtype.
_NON_SUBTYPE_TYPAL = {"creature", "coupling", "choose", "non-human", "noncreature", "changeling"}


def _typal_subtypes(tags: set[str]) -> set[str]:
    out = set()
    for t in tags:
        if t.startswith("typal-") and not t.startswith("typal-non"):
            sub = t[len("typal-"):]
            if sub not in _NON_SUBTYPE_TYPAL and "-" not in sub:
                out.add(sub)
    return out


def _creature_subtypes(c: CardInfo) -> set[str]:
    front = _front_type(c)
    if "Creature" not in front and "Kindred" not in front and "Tribal" not in front:
        return set()
    if "—" not in front:
        return set()
    return {w.lower() for w in front.split("—", 1)[1].split()}


# --- graph model ----------------------------------------------------------------------

@dataclass
class Graph:
    mode: str
    nodes: list[str]                      # card keys, stable order
    hubs: list[str] = field(default_factory=list)
    # (source_idx, target_idx, weight, label_idx); label -1 = none
    edges: list[tuple[int, int, float, int]] = field(default_factory=list)
    labels: list[str] = field(default_factory=list)
    meta: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        connected = {i for e in self.edges for i in e[:2]}
        return {
            "mode": self.mode,
            "nodes": self.nodes,
            "hubs": self.hubs,
            "edges": [list(e) for e in self.edges],
            "labels": self.labels,
            "unconnected": len(self.nodes) - len(connected),
            "meta": self.meta,
        }


def _prune(pair_weights: dict[tuple[int, int], float], k: int, tiebreak: Callable[[int], float]) -> set[tuple[int, int]]:
    """Keep an edge if it's among the top-k (by weight, then the other card's tiebreak) of either endpoint."""
    by_node: dict[int, list[tuple[float, float, tuple[int, int]]]] = defaultdict(list)
    for (a, b), w in pair_weights.items():
        by_node[a].append((-w, tiebreak(b), (a, b)))
        by_node[b].append((-w, tiebreak(a), (a, b)))
    keep: set[tuple[int, int]] = set()
    for lst in by_node.values():
        lst.sort()
        keep.update(p for _, _, p in lst[:k])
    return keep


def _popularity(cards: list[CardInfo]) -> Callable[[int], float]:
    return lambda i: cards[i].edhrec_rank if cards[i].edhrec_rank is not None else 1e9


def build_tag_graph(cards: list[CardInfo], tags: TagIndex, k: int = TAG_EDGES_PER_CARD) -> Graph:
    cards = [c for c in cards if c.found]
    cards.sort(key=lambda c: c.key)
    idx_tags = [tags.match_tags_for(c.oracle_id) for c in cards]

    pair_themes: dict[tuple[int, int], set[str]] = defaultdict(set)

    def link(payoffs: Iterable[int], enablers: Iterable[int], theme: str) -> None:
        en = list(enablers)
        for p in payoffs:
            for e in en:
                if p != e:
                    pair_themes[(min(p, e), max(p, e))].add(theme)

    for theme in THEMES:
        payoffs = [i for i, c in enumerate(cards) if theme.is_payoff(c, idx_tags[i])]
        if not payoffs:
            continue
        enablers = [i for i, c in enumerate(cards) if theme.is_enabler(c, idx_tags[i])]
        link(payoffs, enablers, theme.name)

    # Typal: "typal-elf" payoffs <-> Elf creatures (changelings count as every type)
    by_subtype: dict[str, list[int]] = defaultdict(list)
    changelings = [i for i, c in enumerate(cards) if "Changeling" in c.keywords]
    for i, c in enumerate(cards):
        for s in _creature_subtypes(c):
            by_subtype[s].append(i)
    for i, c in enumerate(cards):
        for sub in _typal_subtypes(idx_tags[i]):
            # Only real creature types present in the list (drops tags like typal-army / typal-share).
            if sub in by_subtype:
                link([i], by_subtype[sub] + changelings, f"Typal: {sub.title()}")

    # Typal themes between one pair count once (changelings would otherwise match every type).
    def weight(themes: set[str]) -> float:
        typal = sum(1 for t in themes if t.startswith("Typal: "))
        return float(len(themes) - typal + (1 if typal else 0))

    weights = {p: weight(t) for p, t in pair_themes.items()}
    keep = _prune(weights, k, _popularity(cards))

    labels: list[str] = []
    label_idx: dict[str, int] = {}
    edges = []
    for p in sorted(keep):
        label = ", ".join(sorted(pair_themes[p]))
        if label not in label_idx:
            label_idx[label] = len(labels)
            labels.append(label)
        edges.append((p[0], p[1], weights[p], label_idx[label]))

    used = sorted({t for p in keep for t in pair_themes[p]})
    return Graph(mode="tags", nodes=[c.key for c in cards], edges=edges, labels=labels,
                 meta={"themes": used, "theme_count": len(THEMES)})


# --- EDHREC ------------------------------------------------------------------------------

def is_commander_candidate(c: CardInfo) -> bool:
    front = _front_type(c)
    return (
        c.section == "commander"
        or ("Legendary" in front and "Creature" in front)
        or "can be your commander" in c.oracle_text.lower()
    )


def commander_hubs(cards: list[CardInfo]) -> list[CardInfo]:
    seen: set[str] = set()
    hubs = []
    for c in sorted((c for c in cards if c.found and is_commander_candidate(c)), key=lambda c: c.key):
        slug = edhrec_slug(c.name)
        if slug not in seen:
            seen.add(slug)
            hubs.append(c)
    return hubs


def build_edhrec_graph(cards: list[CardInfo], pages: dict[str, CommanderPage | None],
                       k: int = EDHREC_EDGES_PER_CARD, min_synergy: float = EDHREC_MIN_SYNERGY) -> Graph:
    cards = sorted((c for c in cards if c.found), key=lambda c: c.key)
    index = {c.key: i for i, c in enumerate(cards)}
    by_name: dict[str, list[int]] = defaultdict(list)
    for i, c in enumerate(cards):
        by_name[normalize_name(front_face(c.name))].append(i)

    hubs = commander_hubs(cards)
    weights: dict[tuple[int, int], float] = {}
    missing_pages = []
    for hub in hubs:
        page = pages.get(edhrec_slug(hub.name))
        if page is None:
            missing_pages.append(hub.name)
            continue
        h = index[hub.key]
        for name, (syn, _n, _p) in page.cards.items():
            if syn < min_synergy:
                continue
            for i in by_name.get(name, []):
                # Basic lands carry a color-identity "synergy" that says nothing about the card.
                if i != h and "Basic" not in cards[i].type_line:
                    weights[(min(h, i), max(h, i))] = max(weights.get((min(h, i), max(h, i)), 0.0), syn)

    # Cap per *non-hub* card so each card links to its best few commanders; hubs keep all.
    hub_idx = {index[h.key] for h in hubs}
    per_card: dict[int, list[tuple[float, tuple[int, int]]]] = defaultdict(list)
    for (a, b), w in weights.items():
        for n in (a, b):
            if n not in hub_idx or (a in hub_idx and b in hub_idx):
                per_card[n].append((-w, (a, b)))
    keep: set[tuple[int, int]] = set()
    for lst in per_card.values():
        lst.sort()
        keep.update(p for _, p in lst[:k])

    edges = [(a, b, round(weights[(a, b)], 4), -1) for a, b in sorted(keep)]
    return Graph(mode="edhrec", nodes=[c.key for c in cards], hubs=[h.key for h in hubs], edges=edges,
                 meta={"commanders": len(hubs), "missing_pages": missing_pages})
