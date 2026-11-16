"""Map Scryfall Tagger oracle tags to a small set of functional deck categories.

Scryfall's Oracle Tags bulk file has ~5,000 community-maintained tags, many very
granular (``manarock-ccc``, ``full-refund``) or aliased (``tribal``/``typal``).
For deckbuilding we collapse them into broad *roles* a card plays.

The order of ``CATEGORIES`` is also the priority used to pick a card's single
``primary_category`` (e.g. Wrath of God is both Removal and Board Wipe; its
primary category is Board Wipe because that's listed first).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Callable


@dataclass(frozen=True)
class Category:
    name: str
    tags: frozenset[str] = field(default_factory=frozenset)
    description: str = ""
    # Extra rule evaluated against the raw Scryfall card JSON
    rule: Callable[[dict], bool] | None = None

    def matches(self, card_tags: set[str], card: dict) -> bool:
        if self.tags & card_tags:
            return True
        return bool(self.rule and self.rule(card))


def _front_type_line(card: dict) -> str:
    faces = card.get("card_faces")
    if faces and "type_line" in faces[0]:
        return faces[0]["type_line"]
    return card.get("type_line", "")


def _oracle_text(card: dict) -> str:
    if card.get("oracle_text"):
        return card["oracle_text"]
    return "\n".join(f.get("oracle_text", "") for f in card.get("card_faces", []))


def _is_land(card: dict) -> bool:
    return "Land" in _front_type_line(card)


def _is_fixing(card: dict) -> bool:
    colors = set(card.get("produced_mana") or []) - {"C"}
    return len(colors) >= 2


_TOKEN_RE = re.compile(r"\bcreates?\b[^.]*\btokens?\b", re.IGNORECASE)


def _makes_tokens(card: dict) -> bool:
    return bool(_TOKEN_RE.search(_oracle_text(card)))


def _t(*tags: str) -> frozenset[str]:
    return frozenset(tags)


CATEGORIES: list[Category] = [
    Category("Land", rule=_is_land, description="Lands."),
    Category("Board Wipe", _t("sweeper", "mass-removal", "wrath-of-god"),
             "Removes many permanents at once."),
    Category("Counterspell", _t("counterspell"), "Counters spells or abilities."),
    Category("Removal", _t("removal", "spot-removal", "creature-removal", "artifact-removal",
                           "enchantment-removal", "removal-bounce", "edict", "land-removal"),
             "Gets opposing permanents off the table."),
    Category("Ramp", _t("ramp", "mana-rock", "mana-dork", "land-ramp", "ritual",
                        "cost-reducer", "extra-land"),
             "Increases available mana now or later."),
    Category("Tutor", _t("tutor"), "Searches the library for specific cards."),
    Category("Card Advantage", _t("card-advantage", "draw", "impulse-draw", "wheel",
                                  "repeatable-draw", "repeatable-card-advantage"),
             "Draws or otherwise grants access to extra cards."),
    Category("Win Condition", _t("win-condition", "alternate-win-condition"),
             "Wins the game outright or via an alternate condition."),
    Category("Extra Turns & Combats", _t("extra-turn", "extra-combat")),
    Category("Protection", _t("protection", "protects-creature", "protects-all",
                              "protects-planeswalker", "protects-permanent", "fog"),
             "Keeps your permanents, creatures or life total safe."),
    Category("Recursion", _t("recursion", "reanimate", "regrowth", "mass-reanimation"),
             "Returns cards from the graveyard."),
    Category("Graveyard Hate", _t("graveyard-hate", "hate-graveyard")),
    Category("Theft", _t("theft"), "Steals or uses opponents' cards."),
    Category("Tokens", _t("repeatable-token-generator", "token-doubler"), rule=_makes_tokens,
             description="Creates tokens."),
    Category("Anthem", _t("anthem", "lord"), "Pumps your team."),
    Category("Sac Outlet", _t("sacrifice-outlet", "sac-outlet")),
    Category("Blink", _t("flicker", "blink")),
    Category("Copy", _t("copy", "clone")),
    Category("Burn & Drain", _t("burn-player", "drain-life"),
             "Damages or drains opponents directly."),
    Category("Lifegain", _t("lifegain", "life-gain")),
    Category("Mill", _t("mill-opponent")),
    Category("Self-Mill", _t("self-mill", "mill-self")),
    Category("Discard", _t("discard"), "Makes opponents discard."),
    Category("Discard Outlet", _t("discard-outlet", "loot", "rummage")),
    Category("Card Selection", _t("scry", "cantrip")),
    Category("Haste", _t("gives-haste")),
    Category("Untap", _t("untapper")),
    Category("Tax & Stax", _t("tax", "cost-increaser", "mass-land-denial")),
    Category("Mana Sink", _t("bottomless-mana-sink")),
    Category("Fixing", rule=_is_fixing, description="Produces two or more colors of mana."),
]

CATEGORY_ORDER = {c.name: i for i, c in enumerate(CATEGORIES)}
UNCATEGORIZED = "Uncategorized"


def categorize(card: dict, match_tags: set[str], canonical_tags: set[str] | None = None) -> list[str]:
    """All categories the card fits, in priority order.

    ``match_tags`` may include tag aliases (used to match CATEGORIES);
    ``canonical_tags`` (defaults to ``match_tags``) drives the refinement rules,
    since aliases like ``tutor-hand`` would muddy them.
    """
    cats = [c.name for c in CATEGORIES if c.matches(match_tags, card)]
    card_tags = canonical_tags if canonical_tags is not None else match_tags

    def drop(name: str) -> None:
        if name in cats:
            cats.remove(name)

    # Lands that tap for mana shouldn't also show up as Ramp just for being a land.
    if "Land" in cats and not ({"land-ramp", "extra-land"} & card_tags):
        drop("Ramp")
    # Land searchers (Cultivate, Rampant Growth) are ramp, not tutors.
    tutor_kinds = {t for t in card_tags if t.startswith("tutor-") and not t.startswith("tutor-to")}
    if tutor_kinds and all(t.startswith("tutor-land") for t in tutor_kinds):
        drop("Tutor")
    # Swords to Plowshares gives *the opponent* life; that's a drawback, not lifegain.
    if "opponent-lifegain" in card_tags and "repeatable-lifegain" not in card_tags \
            and "lifelink" not in {k.lower() for k in card.get("keywords", [])}:
        drop("Lifegain")
    return cats


def primary_category(categories: list[str]) -> str:
    return categories[0] if categories else UNCATEGORIZED
