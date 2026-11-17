# EDHREC Notes

EDHREC has **no official API**. These are verified findings (2026-11-17) about the JSON its own website loads.
Add new findings here, with the date.

## Commander pages
- `GET https://json.edhrec.com/pages/commanders/<slug>.json` → ~130 KB JSON.
- Slug: lowercase front-face name, accents stripped, punctuation removed, spaces → hyphens
  (`Atraxa, Praetors' Voice` → `atraxa-praetors-voice`). See `edhrec_slug()`.
- `container.json_dict.cardlists[]`: about 11 lists (New Cards, Top Cards, Creatures, Instants, …, Lands). Each has
  `cardviews[]`:
  ```json
  {"name": "Sanctum Lurker", "sanitized": "sanctum-lurker", "synergy": 0.041, "lift": 1.69,
   "num_decks": 659, "potential_decks": 6485, "trend_zscore": 8.2, "id": "<scryfall id>"}
  ```
  About 290 distinct cards per commander. `synergy` runs from -1 to 1: the card's inclusion rate with this commander minus its
  rate in all decks of those colors.
- Total decks: `num_decks_avg` at the top level, or `container.json_dict.card.num_decks`.
- An unknown commander returns 404. That response is cached as "missing" for 1 day.
- Some pages may return `{"redirect": "/commanders/<other>"}`. `EdhrecClient.fetch` follows it (not yet observed).
- Basic lands appear with color-identity "synergy". These are excluded from graph edges.

## Etiquette
- Generic User-Agent `mtg-card-view/<ver>`, one request at a time, at least 0.5 s apart, 7-day cache.
