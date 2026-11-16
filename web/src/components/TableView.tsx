import type { Card, SortBy, ViewGroup } from '../types';
import { categoryHue, countCards, formatPrice } from '../util';
import { RankBadge } from './CardRow';
import { usePreview } from './HoverPreview';
import { ManaCost } from './Symbols';

interface Props {
  groups: ViewGroup[];
  selectedKey: string | null;
  onSelect: (card: Card) => void;
  sort: SortBy;
  onSort: (s: SortBy) => void;
}

export function CategoryChips({ cats, max }: { cats: string[]; max?: number }) {
  const shown = max ? cats.slice(0, max) : cats;
  return (
    <span className="chips">
      {shown.map((c) => (
        <span key={c} className="chip" style={{ '--chip-h': categoryHue(c) } as React.CSSProperties}>
          {c}
        </span>
      ))}
      {max && cats.length > max && <span className="chip more">+{cats.length - max}</span>}
    </span>
  );
}

export function TableView({ groups, selectedKey, onSelect, sort, onSort }: Props) {
  const preview = usePreview();
  const th = (label: string, key?: SortBy, cls = '') => (
    <th
      className={`${cls}${key ? ' sortable' : ''}${key === sort ? ' sorted' : ''}`}
      onClick={key ? () => onSort(key) : undefined}
    >
      {label}
      {key === sort && ' ▾'}
    </th>
  );

  return (
    <div className="table-wrap">
      <table className="card-table">
        <thead>
          <tr>
            {th('Qty', undefined, 'num')}
            {th('Name', 'name')}
            {th('Cost')}
            {th('MV', 'cmc', 'num')}
            {th('Type')}
            {th('EDHREC', 'edhrec', 'num')}
            {th('Categories')}
            {th('Price', 'price', 'num')}
          </tr>
        </thead>
        {groups.filter((g) => g.cards.length > 0).map((g) => (
          <tbody key={g.id}>
            <tr className="group-row">
              <td colSpan={8}>
                {g.name} <span className="count">{countCards(g.cards)}</span>
              </td>
            </tr>
            {g.cards.map((c) => (
              <tr
                key={c.key}
                className={`${c.key === selectedKey ? 'selected' : ''}${c.found ? '' : ' missing'}`}
                onClick={() => onSelect(c)}
                onMouseEnter={(e) => preview.show(c, e)}
                onMouseMove={(e) => preview.show(c, e)}
                onMouseLeave={preview.hide}
              >
                <td className="num">{c.quantity}</td>
                <td className="name-cell">
                  {c.name}
                  {c.game_changer && <span className="gc">GC</span>}
                </td>
                <td>
                  <ManaCost cost={c.mana_cost} size={14} />
                </td>
                <td className="num">{c.found ? c.cmc : ''}</td>
                <td className="muted">{c.type_line}</td>
                <td className="num">
                  <RankBadge rank={c.edhrec_rank} />
                </td>
                <td>
                  <CategoryChips cats={c.categories} max={3} />
                </td>
                <td className="num">{formatPrice(c.price_usd)}</td>
              </tr>
            ))}
          </tbody>
        ))}
      </table>
    </div>
  );
}
