import type { Board, BoardLayout, DeckDetail, DeckSummary, SeedMode } from './types';

async function req<T>(method: string, url: string, body?: unknown): Promise<T> {
  const res = await fetch(url, {
    method,
    headers: body !== undefined ? { 'Content-Type': 'application/json' } : undefined,
    body: body !== undefined ? JSON.stringify(body) : undefined,
  });
  if (!res.ok) {
    let msg = `${res.status} ${res.statusText}`;
    try {
      const j = await res.json();
      if (j.detail) msg = typeof j.detail === 'string' ? j.detail : JSON.stringify(j.detail);
    } catch {
      /* non-JSON error body */
    }
    throw new Error(msg);
  }
  return (res.status === 204 ? undefined : await res.json()) as T;
}

export const api = {
  listDecks: () => req<DeckSummary[]>('GET', '/api/decks'),
  getDeck: (id: number) => req<DeckDetail>('GET', `/api/decks/${id}`),
  createDeck: (name: string, text: string) => req<DeckDetail>('POST', '/api/decks', { name, text }),
  updateDeck: (id: number, patch: { name?: string; text?: string }) =>
    req<DeckDetail>('PATCH', `/api/decks/${id}`, patch),
  deleteDeck: (id: number) => req<void>('DELETE', `/api/decks/${id}`),
  createBoard: (deckId: number, name: string, seed: SeedMode) =>
    req<Board>('POST', `/api/decks/${deckId}/boards`, { name, seed }),
  updateBoard: (id: number, patch: { name?: string; layout?: BoardLayout }) =>
    req<Board>('PATCH', `/api/boards/${id}`, patch),
  deleteBoard: (id: number) => req<void>('DELETE', `/api/boards/${id}`),
};
