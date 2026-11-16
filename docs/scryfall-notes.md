# Scryfall API Notes

Verified findings (2026-11-16). Add to this file when you learn something new. Note the date.

## General
- Docs: https://scryfall.com/docs/api. Requires `User-Agent` and `Accept` headers. Keep ~10 req/s max.
  A 429 response means slow down.
- Card objects include `edhrec_rank` (lower = more played; absent for basics), `game_changer` (bool),
  `oracle_id`, `produced_mana`, `keywords`, `legalities`, `prices`, `related_uris.edhrec`.
- Multi-face cards (`transform`, `modal_dfc`, `split`, `adventure`) may have no top-level `image_uris`,
  `mana_cost`, or `oracle_text`. Read them from `card_faces[]` instead.

## `POST /cards/collection`
- Up to 75 identifiers per request. Returns `data` and `not_found`.
- `{"name": "Fire // Ice"}` → **not found**. `{"name": "Fire"}` → returns *Fire // Ice*. The same holds
  for DFC and adventure cards (front-face name works).
- Name matching is accent-insensitive (`Lim-Dul the Necromancer` finds `Lim-Dûl`).

## `GET /cards/named`
- `?exact=Fire // Ice` works. `?fuzzy=lightning bolr` → Lightning Bolt.

## Oracle tags (Tagger)
- Not on card objects. Searchable with `otag:<tag>` in `/cards/search`.
- **Bulk file**: `GET /bulk-data/oracle-tags` → `jsonl_download_uri` (gzip JSONL, ~6 MB, updated daily).
  One tag per line:
  ```json
  {"object":"tag","id":"…","label":"tutor-creature-giant","slug":"tutor-creature-giant",
   "type":"oracle","description":"…","parent_ids":["…"],"child_ids":[],
   "aliases":["tutor-giant"],"taggings":[{"oracle_id":"…","weight":"median","annotation":"…"?}]}
  ```
  - ~4,600 tags. `taggings` are **direct only**. Parents must be inherited via `parent_ids` to match
    `otag:` search counts.
  - Labels are inconsistent: some hyphenated, some with spaces (`mana rock`, `card advantage`).
  - Weights seen: `median` (~240k), `very_strong` (~631), `strong` (1). `annotation` appears on ~3.4k taggings
    (not used yet).
- `GET /private/tags/oracle` (undocumented) returns a JSON list with **flattened** `oracle_ids` per tag
  and no hierarchy or weights. `TagIndex._from_flat` still supports this format. Don't depend on it.
- Useful tag slugs for deck roles: see `src/mtgcv/categories.py`. Notable aliases: `sweeper` /
  `wrath-of-god` / `mass-removal`; `sac-outlet` / `sacrifice-outlet`; `tribal` / `typal`; `lord` → `anthem`.
