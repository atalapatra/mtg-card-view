import type { Card } from '../types';
import { displayName, formatRank, rankTier, RANK_TIER_LABEL } from '../util';
import { usePreview } from './HoverPreview';
import { ManaCost } from './Symbols';

interface Props {
  card: Card;
  selected?: boolean;
  onSelect?: (card: Card) => void;
  overlay?: boolean;
}

export function RankBadge({ rank }: { rank: number | null }) {
  const tier = rankTier(rank);
  return (
    <span className={`rank rank-${tier}`} title={`EDHREC rank ${formatRank(rank)} · ${RANK_TIER_LABEL[tier]}`}>
      {formatRank(rank)}
    </span>
  );
}

/** Compact one-line card used in board columns. */
export function CardRow({ card, selected, onSelect, overlay }: Props) {
  const preview = usePreview();
  return (
    <div
      className={`card-row${selected ? ' selected' : ''}${overlay ? ' overlay' : ''}${card.found ? '' : ' missing'}`}
      onClick={() => onSelect?.(card)}
      onMouseEnter={(e) => preview.show(card, e)}
      onMouseMove={(e) => preview.show(card, e)}
      onMouseLeave={preview.hide}
      title={card.found ? undefined : 'Not found on Scryfall'}
    >
      <span className="qty">{card.quantity > 1 ? `${card.quantity}×` : ''}</span>
      <span className="name" title={card.name}>
        {displayName(card)}
        {card.game_changer && (
          <span className="gc" title="Game Changer (Commander bracket list)">
            GC
          </span>
        )}
      </span>
      <ManaCost cost={card.mana_cost} size={14} />
      <RankBadge rank={card.edhrec_rank} />
    </div>
  );
}
