"""Convert collection-app exports into the plain text card-list format.

The result is exactly what a user could paste: one ``<qty> <name> (<SET>) <number>``
line per card name, so imports go through the normal ``parse_decklist`` path.

ManaBox CSV (export from the ManaBox app), columns used:
    Name, Quantity, Set code, Set name, Collector number, Binder Type
Rows for the same card name (different printings, foils, binders) are combined
into one line with the summed quantity; the first printing seen is kept.
Binder/deck names are intentionally ignored (see docs/decisions.md D-018).
"""

from __future__ import annotations

import csv
import io
from dataclasses import dataclass, field

MANABOX_REQUIRED = {"Name", "Quantity"}
MANABOX_MARKERS = {"ManaBox ID", "Binder Type", "Binder Name"}


@dataclass
class ImportResult:
    text: str
    rows: int = 0
    cards: int = 0                # total quantity included
    unique: int = 0               # distinct card names included
    skipped_tokens: int = 0       # quantity left out
    skipped_lists: int = 0        # quantity left out
    errors: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return self.__dict__.copy()


def looks_like_manabox(text: str) -> bool:
    first = text.lstrip("﻿").split("\n", 1)[0]
    try:
        header = set(next(csv.reader([first])))
    except StopIteration:
        return False
    return MANABOX_REQUIRED <= header and bool(MANABOX_MARKERS & header)


def _is_token(row: dict) -> bool:
    return (row.get("Set name") or "").strip().endswith("Tokens")


def _is_list(row: dict) -> bool:
    return (row.get("Binder Type") or "").strip().lower() == "list"


def manabox_to_decklist(csv_text: str, include_tokens: bool = False,
                        include_lists: bool = False) -> ImportResult:
    reader = csv.DictReader(io.StringIO(csv_text.lstrip("﻿")))
    missing = MANABOX_REQUIRED - set(reader.fieldnames or [])
    if missing:
        raise ValueError(f"Not a ManaBox CSV export (missing columns: {', '.join(sorted(missing))})")

    result = ImportResult(text="")
    combined: dict[str, list] = {}  # lower(name) -> [qty, name, set, number]
    for lineno, row in enumerate(reader, start=2):
        result.rows += 1
        name = (row.get("Name") or "").strip()
        try:
            qty = int((row.get("Quantity") or "1").strip() or 1)
        except ValueError:
            result.errors.append(f"Row {lineno}: bad quantity {row.get('Quantity')!r}")
            continue
        if not name or qty <= 0:
            continue
        if _is_token(row) and not include_tokens:
            result.skipped_tokens += qty
            continue
        if _is_list(row) and not include_lists:
            result.skipped_lists += qty
            continue
        key = name.lower()
        if key in combined:
            combined[key][0] += qty
        else:
            combined[key] = [qty, name, (row.get("Set code") or "").strip(),
                             (row.get("Collector number") or "").strip()]

    lines = []
    for qty, name, set_code, number in combined.values():
        line = f"{qty} {name}"
        if set_code:
            line += f" ({set_code.upper()})" + (f" {number}" if number else "")
        lines.append(line)
        result.cards += qty
    result.unique = len(lines)
    result.text = "\n".join(lines) + ("\n" if lines else "")
    return result
