"""Parse card lists in the common text formats.

Supported line shapes (quantity is optional, defaults to 1):

    Sol Ring
    1 Sol Ring
    1x Sol Ring
    1 Sol Ring (C21) 263            # Moxfield / MTGA
    1 Sol Ring (C21) 263 *F*        # Moxfield foil marker
    1x Sol Ring (c21) 263 [Ramp]    # Archidekt category
    1 Sol Ring #ramp #artifact      # inline hashtags
    1 Fire // Ice                   # split / double-faced names

Section headers (``Commander``, ``Deck``, ``Sideboard``, ``// Maybeboard``,
``Commander:`` ...) switch the section that following cards belong to.
Lines starting with ``#`` or ``//`` that are not section headers are comments.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

KNOWN_SECTIONS = {
    "commander": "commander",
    "commanders": "commander",
    "companion": "companion",
    "deck": "main",
    "main": "main",
    "mainboard": "main",
    "main deck": "main",
    "sideboard": "sideboard",
    "side": "sideboard",
    "maybeboard": "maybeboard",
    "maybe": "maybeboard",
    "considering": "maybeboard",
}

_LINE_RE = re.compile(
    r"""^
    (?:(?P<qty>\d+)\s*x?\s+)?          # optional quantity: "1 ", "1x ", "1 x "
    (?P<name>.+?)                       # card name (lazy)
    (?:\s+\((?P<set>[A-Za-z0-9]{2,6})\)  # optional (SET)
       (?:\s+(?P<num>[A-Za-z0-9★\-]+))?  # optional collector number
    )?
    (?:\s+\*[A-Za-z]+\*)*               # *F*, *E* foil/etched markers
    (?:\s+\[[^\]]*\])*                  # [Archidekt categories]
    (?:\s+\#\S+)*                       # #hashtags
    \s*$""",
    re.VERBOSE,
)
_ARCHIDEKT_TAGS_RE = re.compile(r"\[([^\]]*)\]")
_HASHTAG_RE = re.compile(r"(?:^|\s)#(\S+)")


@dataclass
class DeckEntry:
    name: str
    quantity: int = 1
    section: str = "main"
    set_code: str | None = None
    collector_number: str | None = None
    user_tags: list[str] = field(default_factory=list)
    line_number: int = 0


@dataclass
class ParseResult:
    entries: list[DeckEntry]
    errors: list[tuple[int, str]]


def _section_from_header(line: str) -> str | None:
    stripped = line.strip().lstrip("/#").strip().rstrip(":").strip().lower()
    # "Commander (1)" / "Sideboard 15" style headers from some exporters
    stripped = re.sub(r"\s*[\(\[]?\d+[\)\]]?$", "", stripped)
    return KNOWN_SECTIONS.get(stripped)


def _clean_name(name: str) -> str:
    name = name.strip()
    # Normalise "Fire/Ice" and "Fire // Ice" spacing to Scryfall's " // " form
    name = re.sub(r"\s*/{1,2}\s*", " // ", name)
    return re.sub(r"\s+", " ", name)


def parse_decklist(text: str) -> ParseResult:
    entries: list[DeckEntry] = []
    errors: list[tuple[int, str]] = []
    section = "main"

    for lineno, raw in enumerate(text.splitlines(), start=1):
        line = raw.strip()
        if not line:
            continue

        header = _section_from_header(line)
        if header is not None and not re.match(r"^\d", line):
            section = header
            continue
        if line.startswith(("#", "//")):
            continue

        # "SB: 1 Card" (old MTGO/Apprentice sideboard prefix)
        entry_section = section
        if line.upper().startswith("SB:"):
            entry_section = "sideboard"
            line = line[3:].strip()

        user_tags: list[str] = []
        for group in _ARCHIDEKT_TAGS_RE.findall(line):
            user_tags.extend(t.strip() for t in group.split(",") if t.strip())
        user_tags.extend(_HASHTAG_RE.findall(line))

        m = _LINE_RE.match(line)
        if not m or not m.group("name").strip():
            errors.append((lineno, raw))
            continue

        entries.append(
            DeckEntry(
                name=_clean_name(m.group("name")),
                quantity=int(m.group("qty") or 1),
                section=entry_section,
                set_code=(m.group("set") or None) and m.group("set").lower(),
                collector_number=m.group("num"),
                user_tags=user_tags,
                line_number=lineno,
            )
        )

    return ParseResult(entries=_merge_duplicates(entries), errors=errors)


def _merge_duplicates(entries: list[DeckEntry]) -> list[DeckEntry]:
    """Combine repeated lines for the same card in the same section."""
    merged: dict[tuple[str, str], DeckEntry] = {}
    for e in entries:
        key = (e.name.lower(), e.section)
        if key in merged:
            existing = merged[key]
            existing.quantity += e.quantity
            for t in e.user_tags:
                if t not in existing.user_tags:
                    existing.user_tags.append(t)
        else:
            merged[key] = e
    return list(merged.values())
