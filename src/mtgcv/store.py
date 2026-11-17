"""Persistent storage for saved decks and custom groupings ("boards").

Lives in a *data* directory, separate from the Scryfall cache, so clearing the
cache never loses user work.

A board is a named custom grouping for a deck:
    {"groups": [{"id": "g1", "name": "Ramp", "cards": ["main:Sol Ring", ...]}, ...]}
Card keys are ``CardInfo.key`` (``"<section>:<name>"``). Cards not placed in any
group are "unsorted" and are shown as such by the UI.
"""

from __future__ import annotations

import json
import os
import sqlite3
import sys
import threading
import time
from pathlib import Path


def default_data_dir() -> Path:
    override = os.environ.get("MTGCV_DATA_DIR")
    if override:
        return Path(override)
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / "mtg-card-view"
    if os.name == "nt" and os.environ.get("APPDATA"):
        return Path(os.environ["APPDATA"]) / "mtg-card-view"
    xdg = os.environ.get("XDG_DATA_HOME")
    return (Path(xdg) if xdg else Path.home() / ".local" / "share") / "mtg-card-view"


SCHEMA = """
CREATE TABLE IF NOT EXISTS decks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    text TEXT NOT NULL,
    created_at REAL NOT NULL,
    updated_at REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS boards (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    deck_id INTEGER NOT NULL REFERENCES decks(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    layout TEXT NOT NULL,
    created_at REAL NOT NULL,
    updated_at REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS boards_deck ON boards(deck_id);
CREATE TABLE IF NOT EXISTS graph_layouts (
    deck_id INTEGER NOT NULL REFERENCES decks(id) ON DELETE CASCADE,
    mode TEXT NOT NULL,
    positions TEXT NOT NULL,
    updated_at REAL NOT NULL,
    PRIMARY KEY (deck_id, mode)
);
"""


class NotFound(KeyError):
    pass


class DeckStore:
    def __init__(self, path: Path | None = None):
        if path is None:
            data_dir = default_data_dir()
            data_dir.mkdir(parents=True, exist_ok=True)
            path = data_dir / "decks.sqlite3"
        self._lock = threading.Lock()
        self._db = sqlite3.connect(path, check_same_thread=False)
        self._db.row_factory = sqlite3.Row
        self._db.execute("PRAGMA foreign_keys = ON")
        self._db.executescript(SCHEMA)
        self._db.commit()

    # --- decks ---------------------------------------------------------------
    def list_decks(self) -> list[dict]:
        with self._lock:
            rows = self._db.execute(
                "SELECT id, name, text, created_at, updated_at FROM decks ORDER BY updated_at DESC"
            ).fetchall()
        return [dict(r) for r in rows]

    def get_deck(self, deck_id: int) -> dict:
        with self._lock:
            row = self._db.execute("SELECT * FROM decks WHERE id = ?", (deck_id,)).fetchone()
        if not row:
            raise NotFound(f"deck {deck_id}")
        return dict(row)

    def create_deck(self, name: str, text: str) -> dict:
        now = time.time()
        with self._lock:
            cur = self._db.execute(
                "INSERT INTO decks (name, text, created_at, updated_at) VALUES (?, ?, ?, ?)",
                (name, text, now, now),
            )
            self._db.commit()
        return self.get_deck(cur.lastrowid)

    def update_deck(self, deck_id: int, name: str | None = None, text: str | None = None) -> dict:
        deck = self.get_deck(deck_id)
        with self._lock:
            self._db.execute(
                "UPDATE decks SET name = ?, text = ?, updated_at = ? WHERE id = ?",
                (name if name is not None else deck["name"],
                 text if text is not None else deck["text"], time.time(), deck_id),
            )
            self._db.commit()
        return self.get_deck(deck_id)

    def delete_deck(self, deck_id: int) -> None:
        with self._lock:
            cur = self._db.execute("DELETE FROM decks WHERE id = ?", (deck_id,))
            self._db.commit()
        if cur.rowcount == 0:
            raise NotFound(f"deck {deck_id}")

    # --- boards --------------------------------------------------------------
    @staticmethod
    def _board(row: sqlite3.Row) -> dict:
        d = dict(row)
        d["layout"] = json.loads(d["layout"])
        return d

    def list_boards(self, deck_id: int) -> list[dict]:
        with self._lock:
            rows = self._db.execute(
                "SELECT * FROM boards WHERE deck_id = ? ORDER BY created_at", (deck_id,)
            ).fetchall()
        return [self._board(r) for r in rows]

    def get_board(self, board_id: int) -> dict:
        with self._lock:
            row = self._db.execute("SELECT * FROM boards WHERE id = ?", (board_id,)).fetchone()
        if not row:
            raise NotFound(f"board {board_id}")
        return self._board(row)

    def create_board(self, deck_id: int, name: str, layout: dict) -> dict:
        self.get_deck(deck_id)
        now = time.time()
        with self._lock:
            cur = self._db.execute(
                "INSERT INTO boards (deck_id, name, layout, created_at, updated_at) "
                "VALUES (?, ?, ?, ?, ?)",
                (deck_id, name, json.dumps(layout), now, now),
            )
            self._db.commit()
        return self.get_board(cur.lastrowid)

    def update_board(self, board_id: int, name: str | None = None,
                     layout: dict | None = None) -> dict:
        board = self.get_board(board_id)
        with self._lock:
            self._db.execute(
                "UPDATE boards SET name = ?, layout = ?, updated_at = ? WHERE id = ?",
                (name if name is not None else board["name"],
                 json.dumps(layout if layout is not None else board["layout"]),
                 time.time(), board_id),
            )
            self._db.commit()
        return self.get_board(board_id)

    def delete_board(self, board_id: int) -> None:
        with self._lock:
            cur = self._db.execute("DELETE FROM boards WHERE id = ?", (board_id,))
            self._db.commit()
        if cur.rowcount == 0:
            raise NotFound(f"board {board_id}")

    # --- graph layouts ---------------------------------------------------------
    # positions: {card_key: [x, y]} for one deck + graph weighting mode
    def get_layout(self, deck_id: int, mode: str) -> dict | None:
        with self._lock:
            row = self._db.execute(
                "SELECT positions FROM graph_layouts WHERE deck_id = ? AND mode = ?", (deck_id, mode)
            ).fetchone()
        return json.loads(row["positions"]) if row else None

    def save_layout(self, deck_id: int, mode: str, positions: dict) -> None:
        self.get_deck(deck_id)
        with self._lock:
            self._db.execute(
                "INSERT OR REPLACE INTO graph_layouts (deck_id, mode, positions, updated_at) VALUES (?, ?, ?, ?)",
                (deck_id, mode, json.dumps(positions), time.time()),
            )
            self._db.commit()

    def delete_layout(self, deck_id: int, mode: str) -> None:
        with self._lock:
            self._db.execute("DELETE FROM graph_layouts WHERE deck_id = ? AND mode = ?", (deck_id, mode))
            self._db.commit()

    def close(self) -> None:
        self._db.close()
