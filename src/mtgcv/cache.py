"""Local on-disk cache so repeated analyses don't re-hit Scryfall.

* Card JSON is stored in SQLite keyed by normalised card name.
* The Oracle Tags bulk file is stored as a gzip'd JSONL file and refreshed
  when Scryfall publishes a newer one (checked at most once per day).
"""

from __future__ import annotations

import json
import os
import sqlite3
import time
from pathlib import Path

CARD_TTL_SECONDS = 7 * 24 * 3600  # EDHREC ranks / prices drift; refresh weekly


def default_cache_dir() -> Path:
    override = os.environ.get("MTGCV_CACHE_DIR")
    if override:
        return Path(override)
    if os.name == "nt" and os.environ.get("LOCALAPPDATA"):
        return Path(os.environ["LOCALAPPDATA"]) / "mtg-card-view"
    xdg = os.environ.get("XDG_CACHE_HOME")
    return (Path(xdg) if xdg else Path.home() / ".cache") / "mtg-card-view"


class CardCache:
    def __init__(self, cache_dir: Path | None = None, ttl: float = CARD_TTL_SECONDS):
        self.dir = cache_dir or default_cache_dir()
        self.dir.mkdir(parents=True, exist_ok=True)
        self.ttl = ttl
        self._db = sqlite3.connect(self.dir / "cards.sqlite3")
        self._db.execute(
            "CREATE TABLE IF NOT EXISTS cards ("
            " key TEXT PRIMARY KEY, data TEXT NOT NULL, fetched_at REAL NOT NULL)"
        )
        self._db.execute(
            "CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value TEXT NOT NULL)"
        )
        self._db.commit()

    # --- cards -----------------------------------------------------------
    def get_cards(self, keys: list[str]) -> dict[str, dict]:
        if not keys:
            return {}
        cutoff = time.time() - self.ttl
        found: dict[str, dict] = {}
        for i in range(0, len(keys), 500):
            chunk = keys[i : i + 500]
            q = ",".join("?" * len(chunk))
            for key, data in self._db.execute(
                f"SELECT key, data FROM cards WHERE fetched_at >= ? AND key IN ({q})",
                [cutoff, *chunk],
            ):
                found[key] = json.loads(data)
        return found

    def put_cards(self, items: dict[str, dict]) -> None:
        now = time.time()
        self._db.executemany(
            "INSERT OR REPLACE INTO cards (key, data, fetched_at) VALUES (?, ?, ?)",
            [(k, json.dumps(v), now) for k, v in items.items()],
        )
        self._db.commit()

    # --- metadata --------------------------------------------------------
    def get_meta(self, key: str) -> str | None:
        row = self._db.execute("SELECT value FROM meta WHERE key = ?", (key,)).fetchone()
        return row[0] if row else None

    def set_meta(self, key: str, value: str) -> None:
        self._db.execute("INSERT OR REPLACE INTO meta (key, value) VALUES (?, ?)", (key, value))
        self._db.commit()

    @property
    def tags_path(self) -> Path:
        return self.dir / "oracle-tags.jsonl.gz"

    def close(self) -> None:
        self._db.close()
