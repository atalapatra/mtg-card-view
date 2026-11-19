"""EDHREC commander pages: card <-> commander synergy scores.

EDHREC has no official API. Its site loads JSON from
``https://json.edhrec.com/pages/commanders/<slug>.json``. Each page lists
~250-300 cards with ``synergy`` (-1..1: how much more often the card appears in
this commander's decks than in all decks that could play it), ``num_decks`` and
``potential_decks``. Cards outside that list have no score for the commander.

We are a polite client: generic User-Agent, one request at a time with a delay,
and a 7-day on-disk cache (404s are cached for a day).
"""

from __future__ import annotations

import json
import re
import sqlite3
import threading
import time
import unicodedata
from dataclasses import dataclass, field
from pathlib import Path

import httpx

from mtgcv import __version__
from mtgcv.cache import default_cache_dir
from mtgcv.scryfall import front_face, normalize_name

BASE = "https://json.edhrec.com/pages/commanders"
# Bump when CommanderPage.to_json changes shape; older cache entries are re-fetched. v2 added lift.
CACHE_FORMAT = 2
REQUEST_INTERVAL = 0.5
PAGE_TTL = 7 * 24 * 3600
MISSING_TTL = 24 * 3600


def edhrec_slug(name: str) -> str:
    """'Atraxa, Praetors' Voice' -> 'atraxa-praetors-voice' (front face for DFCs)."""
    n = front_face(name).replace("Æ", "Ae").replace("æ", "ae")
    n = unicodedata.normalize("NFKD", n)
    n = "".join(c for c in n if not unicodedata.combining(c)).lower()
    n = re.sub(r"[^a-z0-9\s-]", "", n)
    return re.sub(r"[\s-]+", "-", n).strip("-")


@dataclass
class CommanderPage:
    slug: str
    num_decks: int = 0
    # normalized card name -> (synergy, num_decks, potential_decks, lift); lift None if absent
    cards: dict[str, tuple[float, int, int, float | None]] = field(default_factory=dict)

    @classmethod
    def parse(cls, slug: str, data: dict) -> "CommanderPage":
        jd = (data.get("container") or {}).get("json_dict") or {}
        cards: dict[str, tuple[float, int, int, float | None]] = {}
        for lst in jd.get("cardlists") or []:
            for cv in lst.get("cardviews") or []:
                name, syn = cv.get("name"), cv.get("synergy")
                if not name or syn is None:
                    continue
                key = normalize_name(front_face(name))
                lift = cv.get("lift")
                cards[key] = (float(syn), int(cv.get("num_decks") or 0), int(cv.get("potential_decks") or 0),
                              float(lift) if lift is not None else None)
        num = data.get("num_decks_avg") or (jd.get("card") or {}).get("num_decks") or 0
        return cls(slug=slug, num_decks=int(num), cards=cards)

    def to_json(self) -> str:
        return json.dumps({"v": CACHE_FORMAT, "num_decks": self.num_decks, "cards": self.cards})

    @classmethod
    def from_json(cls, slug: str, s: str) -> "CommanderPage | None":
        """None if the entry predates the current cache format (re-fetch it)."""
        d = json.loads(s)
        if d.get("v") != CACHE_FORMAT:
            return None
        return cls(slug=slug, num_decks=d["num_decks"], cards={k: tuple(v) for k, v in d["cards"].items()})


class EdhrecClient:
    def __init__(self, cache_dir: Path | None = None, http: httpx.Client | None = None,
                 interval: float = REQUEST_INTERVAL):
        d = cache_dir or default_cache_dir()
        d.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._db = sqlite3.connect(d / "edhrec.sqlite3", check_same_thread=False)
        self._db.execute(
            "CREATE TABLE IF NOT EXISTS pages (slug TEXT PRIMARY KEY, data TEXT, fetched_at REAL NOT NULL)"
        )  # data NULL = page doesn't exist (404)
        self._db.commit()
        self.http = http or httpx.Client(
            headers={"User-Agent": f"mtg-card-view/{__version__}", "Accept": "application/json"},
            timeout=30.0, follow_redirects=True,
        )
        self.interval = interval
        self._last = 0.0
        self._fetch_lock = threading.Lock()

    def _cached(self, slugs: list[str]) -> dict[str, CommanderPage | None]:
        """Fresh cache entries only. Value None = known missing page."""
        now = time.time()
        out: dict[str, CommanderPage | None] = {}
        with self._lock:
            for i in range(0, len(slugs), 500):
                chunk = slugs[i : i + 500]
                q = ",".join("?" * len(chunk))
                for slug, data, at in self._db.execute(
                    f"SELECT slug, data, fetched_at FROM pages WHERE slug IN ({q})", chunk
                ):
                    if data is None and now - at < MISSING_TTL:
                        out[slug] = None
                    elif data is not None and now - at < PAGE_TTL:
                        page = CommanderPage.from_json(slug, data)
                        if page is not None:  # old-format entries count as not cached
                            out[slug] = page
        return out

    def missing(self, slugs: list[str]) -> list[str]:
        cached = self._cached(slugs)
        return [s for s in slugs if s not in cached]

    def get_pages(self, slugs: list[str]) -> dict[str, CommanderPage | None]:
        """Cached pages only (no network). Missing/unfetched slugs are absent."""
        return self._cached(slugs)

    def fetch(self, slug: str) -> CommanderPage | None:
        """Fetch one page from EDHREC (rate-limited) and cache it."""
        with self._fetch_lock:
            wait = self.interval - (time.monotonic() - self._last)
            if wait > 0:
                time.sleep(wait)
            self._last = time.monotonic()
            resp = self.http.get(f"{BASE}/{slug}.json")
        page: CommanderPage | None = None
        if resp.status_code == 200:
            data = resp.json()
            if isinstance(data, dict) and data.get("redirect"):  # alias pages
                with self._fetch_lock:
                    time.sleep(self.interval)
                    self._last = time.monotonic()
                    r2 = self.http.get(f"https://json.edhrec.com/pages{data['redirect']}.json")
                data = r2.json() if r2.status_code == 200 else {}
            page = CommanderPage.parse(slug, data) if data else None
        elif resp.status_code not in (403, 404):
            raise httpx.HTTPStatusError(f"EDHREC {resp.status_code}", request=resp.request, response=resp)
        with self._lock:
            self._db.execute(
                "INSERT OR REPLACE INTO pages (slug, data, fetched_at) VALUES (?, ?, ?)",
                (slug, page.to_json() if page else None, time.time()),
            )
            self._db.commit()
        return page


@dataclass
class FetchJob:
    total: int
    done: int = 0
    failed: list[str] = field(default_factory=list)
    finished: bool = False
    error: str | None = None


class EdhrecFetcher:
    """Fetches missing commander pages in a background thread, one job per deck."""

    def __init__(self, client: EdhrecClient):
        self.client = client
        self._jobs: dict[int, FetchJob] = {}
        self._lock = threading.Lock()

    def ensure(self, deck_id: int, slugs: list[str]) -> FetchJob | None:
        """Returns None when every page is cached; otherwise the (possibly new) running job."""
        missing = self.client.missing(slugs)
        with self._lock:
            job = self._jobs.get(deck_id)
            if job and not job.finished:
                return job
            if not missing:
                self._jobs.pop(deck_id, None)
                return None
            if job and job.finished and job.done >= job.total and set(missing) <= set(job.failed):
                return None  # everything still missing already failed this round; don't loop
            job = FetchJob(total=len(missing))
            self._jobs[deck_id] = job
        threading.Thread(target=self._run, args=(job, missing), daemon=True).start()
        return job

    def _run(self, job: FetchJob, slugs: list[str]) -> None:
        for slug in slugs:
            try:
                self.client.fetch(slug)
            except Exception as e:  # network errors: record and continue
                job.failed.append(slug)
                job.error = str(e)
            job.done += 1
        job.finished = True
