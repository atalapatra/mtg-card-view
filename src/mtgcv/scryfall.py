"""Thin Scryfall API client.

Follows Scryfall's API guidelines (https://scryfall.com/docs/api):
  * send a descriptive User-Agent and an Accept header
  * keep request rate around 10/s (we wait >=100 ms between requests)
  * prefer batch endpoints (/cards/collection, up to 75 identifiers) and bulk data
"""

from __future__ import annotations

import gzip
import json
import re
import time
import unicodedata
from collections import defaultdict
from pathlib import Path
from typing import Iterable

import httpx

from mtgcv import __version__
from mtgcv.cache import CardCache

API = "https://api.scryfall.com"
USER_AGENT = f"mtg-card-view/{__version__}"
MIN_INTERVAL = 0.1
COLLECTION_BATCH = 75
TAGS_CHECK_INTERVAL = 24 * 3600


def normalize_name(name: str) -> str:
    """Case/accent-insensitive key for matching card names ("Lim-Dûl" == "lim-dul")."""
    name = name.replace("Æ", "Ae").replace("æ", "ae")
    name = unicodedata.normalize("NFKD", name)
    name = "".join(c for c in name if not unicodedata.combining(c))
    return re.sub(r"\s+", " ", name).strip().lower()


def front_face(name: str) -> str:
    return name.split(" // ")[0].strip()


class ScryfallError(RuntimeError):
    pass


class ScryfallClient:
    def __init__(self, cache: CardCache | None = None, http: httpx.Client | None = None):
        self.cache = cache or CardCache()
        self.http = http or httpx.Client(
            headers={"User-Agent": USER_AGENT, "Accept": "application/json"},
            timeout=30.0,
            follow_redirects=True,
        )
        self._last_request = 0.0

    # --- low level ---------------------------------------------------------
    def _throttle(self) -> None:
        wait = MIN_INTERVAL - (time.monotonic() - self._last_request)
        if wait > 0:
            time.sleep(wait)
        self._last_request = time.monotonic()

    def _request(self, method: str, url: str, **kw) -> httpx.Response:
        for attempt in range(4):
            self._throttle()
            resp = self.http.request(method, url, **kw)
            if resp.status_code == 429:  # rate limited: back off and retry
                time.sleep(1.0 * (attempt + 1))
                continue
            return resp
        raise ScryfallError(f"Rate limited by Scryfall for {url}")

    # --- cards -------------------------------------------------------------
    def get_cards(self, names: Iterable[str]) -> tuple[dict[str, dict], list[str]]:
        """Resolve card names to Scryfall card objects.

        Returns ``(found, not_found)`` where ``found`` maps each *requested* name
        (as given) to its card JSON.
        """
        requested = list(dict.fromkeys(names))
        key_for = {n: normalize_name(n) for n in requested}

        cached = self.cache.get_cards(list(set(key_for.values())))
        missing = [n for n in requested if key_for[n] not in cached]

        fetched: dict[str, dict] = {}
        if missing:
            fetched = self._fetch_collection(missing)
            still_missing = [n for n in missing if n not in fetched]
            for n in still_missing:
                card = self._fetch_named(n)
                if card:
                    fetched[n] = card
            self.cache.put_cards({key_for[n]: c for n, c in fetched.items()})

        found: dict[str, dict] = {}
        not_found: list[str] = []
        for n in requested:
            card = cached.get(key_for[n]) or fetched.get(n)
            if card:
                found[n] = card
            else:
                not_found.append(n)
        return found, not_found

    def _fetch_collection(self, names: list[str]) -> dict[str, dict]:
        """Batch lookup via /cards/collection.

        Full "A // B" names aren't accepted by this endpoint, so we look up the
        front face and match results back using every face name on the card.
        """
        result: dict[str, dict] = {}
        for i in range(0, len(names), COLLECTION_BATCH):
            batch = names[i : i + COLLECTION_BATCH]
            wanted: dict[str, list[str]] = defaultdict(list)
            for n in batch:
                wanted[normalize_name(front_face(n))].append(n)
            body = {"identifiers": [{"name": front_face(n)} for n in batch]}
            resp = self._request("POST", f"{API}/cards/collection", json=body)
            if resp.status_code != 200:
                raise ScryfallError(f"/cards/collection failed: {resp.status_code} {resp.text[:200]}")
            for card in resp.json().get("data", []):
                for face_name in _all_names(card):
                    for original in wanted.pop(normalize_name(face_name), []):
                        result[original] = card
        return result

    def _fetch_named(self, name: str) -> dict | None:
        """Single lookup with fuzzy matching, used for typos and odd names."""
        for mode in ("exact", "fuzzy"):
            resp = self._request("GET", f"{API}/cards/named", params={mode: name})
            if resp.status_code == 200:
                return resp.json()
        return None

    # --- oracle tags ---------------------------------------------------------
    def load_oracle_tags(self, force_refresh: bool = False) -> "TagIndex":
        """Download (if stale) and load Scryfall's Oracle Tags bulk file."""
        path = self.cache.tags_path
        last_check = float(self.cache.get_meta("tags_checked_at") or 0)
        should_check = force_refresh or not path.exists() or time.time() - last_check > TAGS_CHECK_INTERVAL

        if should_check:
            try:
                self._refresh_tags(path, force_refresh)
            except (httpx.HTTPError, ScryfallError):
                if not path.exists():
                    raise
                # Offline / API hiccup: fall back to the copy we already have.
        return TagIndex.from_file(path)

    def _refresh_tags(self, path: Path, force: bool) -> None:
        resp = self._request("GET", f"{API}/bulk-data/oracle-tags")
        if resp.status_code != 200:
            raise ScryfallError(f"bulk-data lookup failed: {resp.status_code}")
        meta = resp.json()
        updated_at = meta.get("updated_at", "")
        if force or not path.exists() or updated_at != self.cache.get_meta("tags_updated_at"):
            url = meta.get("jsonl_download_uri") or meta.get("download_uri")
            tmp = path.with_suffix(".tmp")
            with self.http.stream("GET", url) as stream:
                stream.raise_for_status()
                with open(tmp, "wb") as f:
                    for chunk in stream.iter_bytes():
                        f.write(chunk)
            tmp.replace(path)
            self.cache.set_meta("tags_updated_at", updated_at)
        self.cache.set_meta("tags_checked_at", str(time.time()))

    def close(self) -> None:
        self.http.close()
        self.cache.close()


def _all_names(card: dict) -> list[str]:
    names = [card.get("name", "")]
    names += [f.get("name", "") for f in card.get("card_faces", [])]
    return [n for n in names if n]


def tag_slug(label: str) -> str:
    """Tagger labels mix styles ("mana rock", "mana-rock"); normalise to hyphens."""
    return re.sub(r"[\s_]+", "-", label.strip().lower())


STRONG_WEIGHTS = {"strong", "very_strong"}


class TagIndex:
    """Scryfall Tagger oracle tags, indexed by card.

    The bulk file lists only *direct* taggings; a card tagged ``manarock`` is
    implicitly also ``ramp`` via the tag hierarchy, so each card receives the
    full ancestor closure of its direct tags (this matches how ``otag:`` search
    behaves on scryfall.com).
    """

    def __init__(
        self,
        by_oracle: dict[str, set[str]],
        descriptions: dict[str, str],
        aliases: dict[str, set[str]] | None = None,
        strong: dict[str, set[str]] | None = None,
        parents: dict[str, set[str]] | None = None,
    ):
        self.by_oracle = by_oracle
        self.descriptions = descriptions
        self.aliases = aliases or {}
        self.strong = strong or {}
        self.parents = parents or {}

    def tags_for(self, oracle_id: str | None) -> set[str]:
        """Canonical tag slugs (direct + inherited) for a card."""
        return self.by_oracle.get(oracle_id or "", set())

    def match_tags_for(self, oracle_id: str | None) -> set[str]:
        """Canonical slugs plus every alias, for category matching."""
        tags = self.tags_for(oracle_id)
        out = set(tags)
        for t in tags:
            out |= self.aliases.get(t, set())
        return out

    def strong_tags_for(self, oracle_id: str | None) -> set[str]:
        """Tags where the card is marked as an especially strong/defining example."""
        return self.strong.get(oracle_id or "", set())

    @classmethod
    def from_records(cls, records: Iterable[dict]) -> "TagIndex":
        records = [r for r in records if r.get("label")]
        if records and "taggings" not in records[0]:
            return cls._from_flat(records)

        by_id = {r["id"]: r for r in records}
        slug_of = {r["id"]: tag_slug(r.get("slug") or r["label"]) for r in records}

        ancestors_memo: dict[str, set[str]] = {}

        def ancestors(tag_id: str, stack: frozenset[str] = frozenset()) -> set[str]:
            if tag_id in ancestors_memo:
                return ancestors_memo[tag_id]
            out: set[str] = set()
            for pid in by_id[tag_id].get("parent_ids") or []:
                if pid in by_id and pid not in stack:
                    out.add(pid)
                    out |= ancestors(pid, stack | {tag_id})
            ancestors_memo[tag_id] = out
            return out

        by_oracle: dict[str, set[str]] = defaultdict(set)
        strong: dict[str, set[str]] = defaultdict(set)
        descriptions: dict[str, str] = {}
        aliases: dict[str, set[str]] = {}
        parents: dict[str, set[str]] = {}

        for r in records:
            slug = slug_of[r["id"]]
            if r.get("description"):
                descriptions[slug] = r["description"]
            if r.get("aliases"):
                aliases[slug] = {tag_slug(a) for a in r["aliases"]}
            if r.get("parent_ids"):
                parents[slug] = {slug_of[p] for p in r["parent_ids"] if p in slug_of}
            inherited = {slug} | {slug_of[a] for a in ancestors(r["id"])}
            for tagging in r.get("taggings") or []:
                oid = tagging.get("oracle_id")
                if not oid:
                    continue
                by_oracle[oid] |= inherited
                if tagging.get("weight") in STRONG_WEIGHTS:
                    strong[oid].add(slug)

        return cls(dict(by_oracle), descriptions, aliases, dict(strong), parents)

    @classmethod
    def _from_flat(cls, records: list[dict]) -> "TagIndex":
        """Older/private format: each tag lists already-flattened ``oracle_ids``."""
        by_oracle: dict[str, set[str]] = defaultdict(set)
        descriptions: dict[str, str] = {}
        for r in records:
            slug = tag_slug(r["label"])
            if r.get("description"):
                descriptions[slug] = r["description"]
            for oid in r.get("oracle_ids", []):
                by_oracle[oid].add(slug)
        return cls(dict(by_oracle), descriptions)

    @classmethod
    def from_file(cls, path: Path) -> "TagIndex":
        opener = gzip.open if path.suffix == ".gz" else open
        with opener(path, "rt", encoding="utf-8") as f:
            if ".jsonl" in path.name:
                return cls.from_records(json.loads(line) for line in f if line.strip())
            data = json.load(f)
            return cls.from_records(data["data"] if isinstance(data, dict) else data)
