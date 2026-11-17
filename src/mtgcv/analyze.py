"""Combine a parsed deck list with Scryfall data, then group and sort it."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import asdict, dataclass, field
from typing import Callable, Literal

from mtgcv.categories import CATEGORY_ORDER, UNCATEGORIZED, categorize, primary_category
from mtgcv.decklist import DeckEntry, ParseResult
from mtgcv.scryfall import ScryfallClient, TagIndex

TYPE_ORDER = ["Land", "Creature", "Planeswalker", "Battle", "Instant", "Sorcery",
              "Artifact", "Enchantment", "Other"]
SECTION_ORDER = ["commander", "companion", "main", "sideboard", "maybeboard"]
COLOR_NAMES = {"W": "White", "U": "Blue", "B": "Black", "R": "Red", "G": "Green"}

GroupBy = Literal["category", "primary", "type", "cmc", "color", "section", "user_tag", "none"]
GROUP_MODES: list[str] = ["category", "primary", "type", "cmc", "color", "section", "user_tag", "none"]
SortBy = Literal["edhrec", "name", "cmc", "price"]


@dataclass
class CardInfo:
    name: str
    quantity: int
    section: str
    found: bool = True
    scryfall_id: str | None = None
    oracle_id: str | None = None
    mana_cost: str = ""
    cmc: float = 0.0
    type_line: str = ""
    main_type: str = "Other"
    layout: str = ""  # Scryfall layout: normal, split, transform, modal_dfc, adventure, ...
    oracle_text: str = ""
    power: str | None = None
    toughness: str | None = None
    loyalty: str | None = None
    colors: list[str] = field(default_factory=list)
    color_identity: list[str] = field(default_factory=list)
    keywords: list[str] = field(default_factory=list)
    rarity: str = ""
    set_code: str = ""
    set_name: str = ""
    collector_number: str = ""
    edhrec_rank: int | None = None
    game_changer: bool = False
    commander_legal: bool | None = None
    price_usd: float | None = None
    image_normal: str | None = None
    image_small: str | None = None
    image_art_crop: str | None = None
    image_back: str | None = None
    scryfall_uri: str | None = None
    edhrec_uri: str | None = None
    tags: list[str] = field(default_factory=list)
    # Tags where Tagger marks this card as an especially strong/defining example
    strong_tags: list[str] = field(default_factory=list)
    categories: list[str] = field(default_factory=list)
    primary_category: str = UNCATEGORIZED
    user_tags: list[str] = field(default_factory=list)

    @property
    def key(self) -> str:
        """Stable identifier within a deck (same card can be in main and sideboard)."""
        return f"{self.section}:{self.name}"

    def to_dict(self) -> dict:
        return {"key": self.key, **asdict(self)}


@dataclass
class Group:
    name: str
    cards: list[CardInfo]

    @property
    def count(self) -> int:
        return sum(c.quantity for c in self.cards)


@dataclass
class Report:
    cards: list[CardInfo]
    not_found: list[str]
    parse_errors: list[tuple[int, str]]
    tag_descriptions: dict[str, str]

    def to_dict(self, group_by: GroupBy = "category", sort_by: SortBy = "edhrec") -> dict:
        groups = group_cards(self.cards, group_by, sort_by)
        used_tags = {t for c in self.cards for t in c.tags}
        return {
            "summary": summarize(self.cards),
            "cards": [c.to_dict() for c in sort_cards(self.cards, sort_by)],
            "groups": [{"name": g.name, "count": g.count, "cards": [c.key for c in g.cards]}
                       for g in groups],
            "group_by": group_by,
            "sort_by": sort_by,
            "not_found": self.not_found,
            "parse_errors": [{"line": n, "text": t} for n, t in self.parse_errors],
            "tag_descriptions": {t: d for t, d in self.tag_descriptions.items() if t in used_tags},
        }

    def to_api_dict(self) -> dict:
        """Everything a UI needs to switch grouping/sorting client-side without refetching:
        cards, plus group membership (card keys) for every built-in grouping mode."""
        data = self.to_dict("category", "name")
        data.pop("groups")
        data.pop("group_by")
        data.pop("sort_by")
        data["groupings"] = {
            mode: [{"name": g.name, "cards": [c.key for c in g.cards]}
                   for g in group_cards(self.cards, mode, "name")]
            for mode in GROUP_MODES
        }
        return data


# --- building ------------------------------------------------------------------

def _main_type(type_line: str) -> str:
    front = type_line.split(" // ")[0]
    for t in TYPE_ORDER[:-1]:
        if t in front:
            return t
    return "Other"


def _image_uris(card: dict) -> tuple[str | None, str | None, str | None, str | None]:
    """(normal, small, art_crop, back-face normal)"""
    if "image_uris" in card:
        iu = card["image_uris"]
        return iu.get("normal"), iu.get("small"), iu.get("art_crop"), None
    faces = card.get("card_faces") or []
    front = faces[0].get("image_uris", {}) if faces else {}
    back = faces[1].get("image_uris", {}) if len(faces) > 1 else {}
    return front.get("normal"), front.get("small"), front.get("art_crop"), back.get("normal")


def _face_field(card: dict, key: str, joiner: str = " // ") -> str:
    if card.get(key):
        return card[key]
    vals = [f.get(key, "") for f in card.get("card_faces", []) if f.get(key)]
    return joiner.join(vals)


def card_info(entry: DeckEntry, card: dict | None, tags: TagIndex) -> CardInfo:
    if card is None:
        return CardInfo(name=entry.name, quantity=entry.quantity, section=entry.section,
                        found=False, user_tags=entry.user_tags)

    oid = card.get("oracle_id")
    card_tags = tags.tags_for(oid)
    cats = categorize(card, tags.match_tags_for(oid), card_tags)
    normal, small, art, back = _image_uris(card)
    faces = card.get("card_faces") or [{}]
    price = (card.get("prices") or {}).get("usd")
    legal = (card.get("legalities") or {}).get("commander")

    return CardInfo(
        name=card.get("name", entry.name),
        quantity=entry.quantity,
        section=entry.section,
        scryfall_id=card.get("id"),
        oracle_id=card.get("oracle_id"),
        mana_cost=_face_field(card, "mana_cost"),
        cmc=float(card.get("cmc") or 0),
        type_line=card.get("type_line", ""),
        main_type=_main_type(card.get("type_line", "")),
        layout=card.get("layout", ""),
        oracle_text=_face_field(card, "oracle_text", "\n//\n"),
        power=card.get("power", faces[0].get("power")),
        toughness=card.get("toughness", faces[0].get("toughness")),
        loyalty=card.get("loyalty", faces[0].get("loyalty")),
        colors=card.get("colors", faces[0].get("colors", [])),
        color_identity=card.get("color_identity", []),
        keywords=card.get("keywords", []),
        rarity=card.get("rarity", ""),
        set_code=card.get("set", ""),
        set_name=card.get("set_name", ""),
        collector_number=card.get("collector_number", ""),
        edhrec_rank=card.get("edhrec_rank"),
        game_changer=bool(card.get("game_changer")),
        commander_legal=None if legal is None else legal == "legal",
        price_usd=float(price) if price else None,
        image_normal=normal,
        image_small=small,
        image_art_crop=art,
        image_back=back,
        scryfall_uri=card.get("scryfall_uri"),
        edhrec_uri=(card.get("related_uris") or {}).get("edhrec"),
        tags=sorted(card_tags),
        strong_tags=sorted(tags.strong_tags_for(oid)),
        categories=cats,
        primary_category=primary_category(cats),
        user_tags=entry.user_tags,
    )


def build_report(parsed: ParseResult, client: ScryfallClient,
                 tags: TagIndex | None = None) -> Report:
    tags = tags or client.load_oracle_tags()
    found, not_found = client.get_cards(e.name for e in parsed.entries)
    cards = [card_info(e, found.get(e.name), tags) for e in parsed.entries]
    return Report(cards=cards, not_found=not_found, parse_errors=parsed.errors,
                  tag_descriptions=tags.descriptions)


# --- sorting & grouping ---------------------------------------------------------

def _sort_key(sort_by: SortBy) -> Callable[[CardInfo], tuple]:
    big = float("inf")
    if sort_by == "edhrec":  # lower rank = more popular; unranked last
        return lambda c: (c.edhrec_rank if c.edhrec_rank is not None else big, c.name)
    if sort_by == "cmc":
        return lambda c: (c.cmc, c.name)
    if sort_by == "price":  # most expensive first
        return lambda c: (-(c.price_usd or 0), c.name)
    return lambda c: (c.name.lower(),)


def sort_cards(cards: list[CardInfo], sort_by: SortBy = "edhrec") -> list[CardInfo]:
    return sorted(cards, key=_sort_key(sort_by))


def _color_group(c: CardInfo) -> str:
    ci = c.color_identity
    if not ci:
        return "Colorless"
    if len(ci) == 1:
        return COLOR_NAMES.get(ci[0], ci[0])
    return "Multicolor"


def group_cards(cards: list[CardInfo], group_by: GroupBy = "category",
                sort_by: SortBy = "edhrec") -> list[Group]:
    """Group cards. With ``category`` a card appears in every category it fits;
    all other modes put each card in exactly one group."""
    buckets: dict[str, list[CardInfo]] = defaultdict(list)
    order: dict[str, float] = {}

    for c in cards:
        if not c.found:
            keys = ["Not Found"]
        elif group_by == "category":
            keys = c.categories or [UNCATEGORIZED]
        elif group_by == "primary":
            keys = [c.primary_category]
        elif group_by == "type":
            keys = [c.main_type]
        elif group_by == "cmc":
            keys = ["Land" if c.main_type == "Land" else str(min(int(c.cmc), 7)) + ("+" if c.cmc >= 7 else "")]
        elif group_by == "color":
            keys = [_color_group(c)]
        elif group_by == "section":
            keys = [c.section]
        elif group_by == "user_tag":
            keys = c.user_tags or ["(no tag)"]
        else:
            keys = ["All Cards"]
        for k in keys:
            buckets[k].append(c)

    def rank(name: str) -> tuple:
        if name in ("Not Found", UNCATEGORIZED, "(no tag)"):
            return (2, name)
        if group_by in ("category", "primary"):
            return (0, CATEGORY_ORDER.get(name, 999))
        if group_by == "type":
            return (0, TYPE_ORDER.index(name) if name in TYPE_ORDER else 99)
        if group_by == "section":
            return (0, SECTION_ORDER.index(name) if name in SECTION_ORDER else 99)
        if group_by == "cmc":
            return (1, 99) if name == "Land" else (0, int(name.rstrip("+")))
        if group_by == "color":
            return (0, ["White", "Blue", "Black", "Red", "Green", "Multicolor", "Colorless"].index(name))
        return (0, name.lower())

    return [Group(name=k, cards=sort_cards(v, sort_by)) for k, v in sorted(buckets.items(), key=lambda kv: rank(kv[0]))]


def summarize(cards: list[CardInfo]) -> dict:
    found = [c for c in cards if c.found]
    nonland = [c for c in found if c.main_type != "Land"]
    total_nonland = sum(c.quantity for c in nonland)
    ranks = [c.edhrec_rank for c in found if c.edhrec_rank is not None]
    category_counts: dict[str, int] = defaultdict(int)
    for c in found:
        for cat in c.categories:
            category_counts[cat] += c.quantity
    return {
        "total_cards": sum(c.quantity for c in cards),
        "unique_cards": len(cards),
        "not_found": sum(1 for c in cards if not c.found),
        "lands": sum(c.quantity for c in found if c.main_type == "Land"),
        "average_cmc_nonland": round(sum(c.cmc * c.quantity for c in nonland) / total_nonland, 2)
        if total_nonland else 0,
        "color_identity": sorted({ci for c in found for ci in c.color_identity},
                                 key="WUBRG".index),
        "median_edhrec_rank": sorted(ranks)[len(ranks) // 2] if ranks else None,
        "game_changers": [c.name for c in found if c.game_changer],
        "total_price_usd": round(sum((c.price_usd or 0) * c.quantity for c in found), 2),
        "category_counts": dict(sorted(category_counts.items(),
                                       key=lambda kv: CATEGORY_ORDER.get(kv[0], 999))),
    }
