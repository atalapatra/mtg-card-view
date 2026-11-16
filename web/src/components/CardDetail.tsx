import { useState } from 'react';
import type { Card } from '../types';
import { formatPrice, formatRank, rankTier, RANK_TIER_LABEL } from '../util';
import { ManaCost, SymbolText } from './Symbols';
import { CategoryChips } from './TableView';

interface Props {
  card: Card;
  tagDescriptions: Record<string, string>;
  onClose: () => void;
  onSearch: (q: string) => void;
}

export function CardDetail({ card, tagDescriptions, onClose, onSearch }: Props) {
  const [showBack, setShowBack] = useState(false);
  const img = showBack && card.image_back ? card.image_back : card.image_normal;
  const strong = new Set(card.strong_tags);
  const tier = rankTier(card.edhrec_rank);

  return (
    <aside className="detail" key={card.key}>
      <header className="detail-head">
        <h2>{card.name}</h2>
        <button className="icon" onClick={onClose} title="Close (Esc)">
          ×
        </button>
      </header>

      {img && <img className="detail-img" src={img} alt={card.name} />}
      {card.image_back && (
        <button className="link-btn" onClick={() => setShowBack((v) => !v)}>
          ⟲ Show {showBack ? 'front' : 'back'} face
        </button>
      )}

      {!card.found ? (
        <p className="warn">This card wasn't found on Scryfall. Check the spelling in the deck list.</p>
      ) : (
        <>
          <dl className="stats">
            <div>
              <dt>EDHREC rank</dt>
              <dd>
                <span className={`rank rank-${tier}`}>{formatRank(card.edhrec_rank)}</span>
                <small>{RANK_TIER_LABEL[tier]}</small>
              </dd>
            </div>
            <div>
              <dt>Price</dt>
              <dd>{formatPrice(card.price_usd)}</dd>
            </div>
            <div>
              <dt>Set</dt>
              <dd title={card.set_name}>
                {card.set_code.toUpperCase()} · {card.rarity}
              </dd>
            </div>
          </dl>
          {(card.game_changer || card.commander_legal === false) && (
            <p className="flags">
              {card.game_changer && <span className="gc">Game Changer</span>}
              {card.commander_legal === false && <span className="badge-bad">Not Commander-legal</span>}
            </p>
          )}

          <div className="oracle">
            <div className="oracle-head">
              <strong>{card.type_line}</strong>
              <ManaCost cost={card.mana_cost} />
            </div>
            {card.oracle_text.split('\n').map((line, i) => (
              <p key={i}>
                <SymbolText text={line} />
              </p>
            ))}
            {(card.power || card.loyalty) && (
              <p className="pt">{card.loyalty ? `Loyalty ${card.loyalty}` : `${card.power}/${card.toughness}`}</p>
            )}
          </div>

          <h4>Categories</h4>
          {card.categories.length ? <CategoryChips cats={card.categories} /> : <p className="muted">None</p>}

          {card.user_tags.length > 0 && (
            <>
              <h4>Your tags</h4>
              <p className="muted">{card.user_tags.join(', ')}</p>
            </>
          )}

          <h4>
            Scryfall tags <span className="muted">({card.tags.length})</span>
          </h4>
          {strong.size > 0 && <p className="hint">★ = Tagger marks this card as a defining example of the tag.</p>}
          <ul className="tag-list">
            {[...card.tags]
              .sort((a, b) => Number(strong.has(b)) - Number(strong.has(a)) || a.localeCompare(b))
              .map((t) => (
                <li key={t}>
                  <button
                    className={`tag${strong.has(t) ? ' strong' : ''}`}
                    title={(tagDescriptions[t] ?? '') + '\n\nClick to filter the deck by this tag'}
                    onClick={() => onSearch(t)}
                  >
                    {strong.has(t) && '★ '}
                    {t}
                  </button>
                </li>
              ))}
          </ul>

          <p className="links">
            {card.scryfall_uri && (
              <a href={card.scryfall_uri} target="_blank" rel="noreferrer">
                Scryfall ↗
              </a>
            )}
            {card.edhrec_uri && (
              <a href={card.edhrec_uri} target="_blank" rel="noreferrer">
                EDHREC ↗
              </a>
            )}
            {card.collector_number && (
              <a
                href={`https://tagger.scryfall.com/card/${card.set_code}/${encodeURIComponent(card.collector_number)}`}
                target="_blank"
                rel="noreferrer"
              >
                Tagger ↗
              </a>
            )}
          </p>
        </>
      )}
    </aside>
  );
}
