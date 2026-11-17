import { useEffect, useState } from 'react';
import { api } from '../api';
import type { Card, PairEdhrec, PairExplanation } from '../types';
import { displayName } from '../util';
import { CategoryChips } from './TableView';

interface Props {
  deckId: number;
  a: Card;
  b: Card;
  cardsByKey: Map<string, Card>;
  tagDescriptions: Record<string, string>;
  onClose: () => void;
  onSwap: () => void;
}

const SHARED_TAGS_SHOWN = 14;

/** The box above the two graph sidebars: why card A and card B are linked. */
export function SynergyBox({ deckId, a, b, cardsByKey, tagDescriptions, onClose, onSwap }: Props) {
  const [data, setData] = useState<PairExplanation | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [allTags, setAllTags] = useState(false);

  useEffect(() => {
    let cancelled = false;
    setData(null);
    setError(null);
    setAllTags(false);
    api
      .getPair(deckId, a.key, b.key)
      .then((d) => !cancelled && setData(d))
      .catch((e) => !cancelled && setError(e instanceof Error ? e.message : String(e)));
    return () => {
      cancelled = true;
    };
  }, [deckId, a.key, b.key]);

  const name = (key: string) => {
    const c = cardsByKey.get(key);
    return <em>{c ? displayName(c) : key}</em>;
  };
  const reasons = (list: string[]) =>
    list.map((r, i) => (
      <span key={r}>
        {i > 0 && ', '}
        <code title={tagDescriptions[r]}>{r}</code>
      </span>
    ));

  return (
    <section className="synergy-box" aria-label="Synergy between the two cards">
      <header className="synergy-head">
        {a.image_art_crop && <img src={a.image_art_crop} alt="" />}
        <h3>
          {displayName(a)} <span className="synergy-arrow">⟷</span> {displayName(b)}
        </h3>
        {b.image_art_crop && <img src={b.image_art_crop} alt="" />}
        <span className="spacer" />
        <button className="icon" title="Swap sides" onClick={onSwap}>
          ⇄
        </button>
        <button className="icon" title="Close the second card" onClick={onClose}>
          ×
        </button>
      </header>

      {error && <p className="warn">{error}</p>}
      {!data && !error && <p className="muted">Loading…</p>}

      {data && (
        <div className="synergy-body">
          <div>
            <h4>Scryfall tag synergy</h4>
            {data.themes.length === 0 ? (
              <p className="muted">No payoff ↔ enabler theme links these two cards.</p>
            ) : (
              <ul className="synergy-list">
                {data.themes.map((t, i) => (
                  <li key={i}>
                    <strong>{t.theme}</strong>: {name(t.payoff)} rewards it ({reasons(t.payoff_reasons)}),{' '}
                    {name(t.enabler)} provides it ({reasons(t.enabler_reasons)}).
                  </li>
                ))}
              </ul>
            )}
          </div>

          <div>
            <h4>EDHREC</h4>
            {data.edhrec.length === 0 ? (
              <p className="muted">Neither card is a commander, so EDHREC has no data for this pair.</p>
            ) : (
              <ul className="synergy-list">
                {data.edhrec.map((e, i) => (
                  <li key={i}>
                    <EdhrecLine e={e} name={name} />
                  </li>
                ))}
              </ul>
            )}
          </div>

          <div>
            <h4>In common</h4>
            {data.shared_categories.length > 0 ? (
              <CategoryChips cats={data.shared_categories} />
            ) : (
              <p className="muted">No shared categories.</p>
            )}
            {data.shared_tags.length > 0 && (
              <p className="shared-tags">
                <span className="muted">{data.shared_tags.length} shared Scryfall tags: </span>
                {(allTags ? data.shared_tags : data.shared_tags.slice(0, SHARED_TAGS_SHOWN)).map((t) => (
                  <code key={t} title={tagDescriptions[t]}>
                    {t}
                  </code>
                ))}
                {data.shared_tags.length > SHARED_TAGS_SHOWN && (
                  <button className="link-btn" onClick={() => setAllTags((v) => !v)}>
                    {allTags ? 'fewer' : `+${data.shared_tags.length - SHARED_TAGS_SHOWN} more`}
                  </button>
                )}
              </p>
            )}
          </div>
        </div>
      )}
    </section>
  );
}

function EdhrecLine({ e, name }: { e: PairEdhrec; name: (key: string) => React.ReactNode }) {
  switch (e.status) {
    case 'listed': {
      const syn = Math.round((e.synergy ?? 0) * 100);
      const pct = e.potential_decks ? Math.round(((e.num_decks ?? 0) / e.potential_decks) * 100) : null;
      return (
        <>
          <strong className={syn > 0 ? 'syn-pos' : 'syn-neg'}>
            {syn >= 0 ? '+' : ''}
            {syn}% synergy
          </strong>{' '}
          for {name(e.card)} with commander {name(e.commander)}
          {pct != null && (
            <span className="muted">
              {' '}
              · in {(e.num_decks ?? 0).toLocaleString()} of {(e.potential_decks ?? 0).toLocaleString()} eligible decks ({pct}
              %)
            </span>
          )}
        </>
      );
    }
    case 'not_listed':
      return (
        <>
          {name(e.card)} isn't among the ~300 cards EDHREC lists for {name(e.commander)}.
        </>
      );
    case 'no_page':
      return <>EDHREC has no commander page for {name(e.commander)}.</>;
    default:
      return (
        <>
          EDHREC data for {name(e.commander)} isn't downloaded yet. Switch the graph to EDHREC commander synergy to
          fetch it.
        </>
      );
  }
}
