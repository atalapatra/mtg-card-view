import type { Card, ViewGroup } from '../types';
import { countCards } from '../util';
import { RankBadge } from './CardRow';

interface Props {
  groups: ViewGroup[];
  selectedKey: string | null;
  onSelect: (card: Card) => void;
}

export function GridView({ groups, selectedKey, onSelect }: Props) {
  return (
    <div className="grid-view">
      {groups.filter((g) => g.cards.length > 0).map((g) => (
        <section key={g.id} className="grid-group">
          <h3>
            {g.name} <span className="count">{countCards(g.cards)}</span>
          </h3>
          <div className="grid-cards">
            {g.cards.map((c) => (
              <button
                key={c.key}
                className={`grid-card${c.key === selectedKey ? ' selected' : ''}`}
                onClick={() => onSelect(c)}
                title={c.name}
              >
                {c.image_normal ? (
                  <img src={c.image_normal} alt={c.name} loading="lazy" draggable={false} />
                ) : (
                  <div className="no-image">{c.name}</div>
                )}
                {c.quantity > 1 && <span className="grid-qty">{c.quantity}×</span>}
                <span className="grid-rank">
                  <RankBadge rank={c.edhrec_rank} />
                </span>
              </button>
            ))}
          </div>
        </section>
      ))}
    </div>
  );
}
