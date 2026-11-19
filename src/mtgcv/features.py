"""Feature switches. Edit this file to turn graph views on or off.

GRAPH_MODES lists every graph weighting the app can show. A mode set to False is
hidden in the UI and rejected by the API (/api/decks/{id}/graph returns 404).

The EDHREC modes ("edhrec", "lift") are the only code that talks to EDHREC. With
both disabled, the server never creates an EDHREC client: no requests to
json.edhrec.com and no edhrec.sqlite3 cache, and the two-card synergy box drops its
EDHREC section. (EDHREC *rank* comes from Scryfall and is unaffected.)

At least one mode must stay enabled; the graph is the app's main view.
"""

from __future__ import annotations

GRAPH_MODES: dict[str, bool] = {
    "tags": True,    # Scryfall tag synergy (Scryfall Tagger data only)
    "edhrec": True,  # EDHREC commander synergy (downloads EDHREC commander pages)
    "lift": True,    # EDHREC lift (same EDHREC commander pages)
}

# Modes that need EDHREC commander pages.
EDHREC_MODES = frozenset({"edhrec", "lift"})


def enabled_graph_modes(modes: dict[str, bool] | None = None) -> list[str]:
    """Enabled modes in display order. Raises if none are enabled."""
    enabled = [m for m, on in (GRAPH_MODES if modes is None else modes).items() if on]
    if not enabled:
        raise ValueError("features.GRAPH_MODES: enable at least one graph mode")
    return enabled


def edhrec_enabled(modes: list[str]) -> bool:
    return any(m in EDHREC_MODES for m in modes)
