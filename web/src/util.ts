import type { BoardLayout, Card, SortBy } from './types';
import { UNSORTED_ID } from './types';

// --- sorting & filtering -------------------------------------------------------

const byName = (a: Card, b: Card) => a.name.localeCompare(b.name);

export function sortCards(cards: Card[], by: SortBy): Card[] {
  const c = [...cards];
  switch (by) {
    case 'edhrec': // most-played first; unranked (basics, new cards) last
      return c.sort((a, b) => (a.edhrec_rank ?? 1e9) - (b.edhrec_rank ?? 1e9) || byName(a, b));
    case 'cmc':
      return c.sort((a, b) => a.cmc - b.cmc || byName(a, b));
    case 'price': // most expensive first
      return c.sort((a, b) => (b.price_usd ?? 0) - (a.price_usd ?? 0) || byName(a, b));
    default:
      return c.sort(byName);
  }
}

export function matchesSearch(card: Card, query: string): boolean {
  const q = query.trim().toLowerCase();
  if (!q) return true;
  const fields = [card.name, card.type_line, card.oracle_text, ...card.tags, ...card.categories, ...card.user_tags];
  return fields.some((f) => f && f.toLowerCase().includes(q));
}

export const countCards = (cards: Card[]) => cards.reduce((n, c) => n + c.quantity, 0);

/** Short display name: front face for DFCs/adventures; split cards keep both halves ("Fire // Ice"). */
export const displayName = (card: Card) =>
  ['split', 'aftermath', 'flip'].includes(card.layout) ? card.name : card.name.split(' // ')[0];

// --- display helpers -------------------------------------------------------------

export function symbolUrl(symbol: string): string {
  // "{W/U}" -> WU.svg, "{2}" -> 2.svg
  const inner = symbol.slice(1, -1).replace(/\//g, '');
  return `https://svgs.scryfall.io/card-symbols/${encodeURIComponent(inner)}.svg`;
}

export function rankTier(rank: number | null): 'top' | 'high' | 'mid' | 'low' | 'none' {
  if (rank == null) return 'none';
  if (rank <= 100) return 'top';
  if (rank <= 1000) return 'high';
  if (rank <= 5000) return 'mid';
  return 'low';
}

export const RANK_TIER_LABEL = {
  top: 'Top 100 on EDHREC',
  high: 'Top 1,000 on EDHREC',
  mid: 'Top 5,000 on EDHREC',
  low: 'Ranked below 5,000 on EDHREC',
  none: 'No EDHREC rank',
} as const;

export const formatRank = (rank: number | null) => (rank == null ? '—' : rank.toLocaleString());

export const formatPrice = (p: number | null) => (p == null ? '—' : `$${p.toFixed(2)}`);

/** Stable hue per category name so chips are recognisable across views. */
export function categoryHue(name: string): number {
  let h = 0;
  for (let i = 0; i < name.length; i++) h = (h * 31 + name.charCodeAt(i)) % 360;
  return h;
}

// --- custom board operations (pure) --------------------------------------------

export function moveCard(layout: BoardLayout, key: string, toGroupId: string): BoardLayout {
  return {
    groups: layout.groups.map((g) => {
      const without = g.cards.filter((k) => k !== key);
      return g.id === toGroupId && toGroupId !== UNSORTED_ID ? { ...g, cards: [...without, key] } : { ...g, cards: without };
    }),
  };
}

export function addGroup(layout: BoardLayout, name: string): BoardLayout {
  const id = `g${Date.now().toString(36)}${Math.random().toString(36).slice(2, 6)}`;
  return { groups: [...layout.groups, { id, name, cards: [] }] };
}

export function renameGroup(layout: BoardLayout, id: string, name: string): BoardLayout {
  return { groups: layout.groups.map((g) => (g.id === id ? { ...g, name } : g)) };
}

export function deleteGroup(layout: BoardLayout, id: string): BoardLayout {
  return { groups: layout.groups.filter((g) => g.id !== id) };
}

export function moveGroup(layout: BoardLayout, id: string, delta: -1 | 1): BoardLayout {
  const groups = [...layout.groups];
  const i = groups.findIndex((g) => g.id === id);
  const j = i + delta;
  if (i < 0 || j < 0 || j >= groups.length) return layout;
  [groups[i], groups[j]] = [groups[j], groups[i]];
  return { groups };
}
