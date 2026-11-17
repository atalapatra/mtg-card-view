import type { ColorMode, Filters } from '../types';
import { EMPTY_FILTERS } from '../types';
import { symbolUrl } from '../util';

const COLORS = ['W', 'U', 'B', 'R', 'G', 'C'];
const TYPES = ['Creature', 'Instant', 'Sorcery', 'Artifact', 'Enchantment', 'Planeswalker', 'Land', 'Battle'];
const RARITIES = ['common', 'uncommon', 'rare', 'mythic'];
const RANK_OPTIONS: { label: string; value: number | null }[] = [
  { label: 'Any', value: null },
  { label: 'Top 100', value: 100 },
  { label: 'Top 1,000', value: 1000 },
  { label: 'Top 5,000', value: 5000 },
  { label: 'Top 10,000', value: 10000 },
];

interface Props {
  filters: Filters;
  onChange: (f: Filters) => void;
  /** Categories present in this collection, in display order. */
  categories: string[];
  shown: number;
  total: number;
}

function toggle(list: string[], v: string): string[] {
  return list.includes(v) ? list.filter((x) => x !== v) : [...list, v];
}

function num(v: string): number | null {
  if (v.trim() === '') return null;
  const n = Number(v);
  return Number.isFinite(n) ? n : null;
}

export function FilterBar({ filters: f, onChange, categories, shown, total }: Props) {
  const set = (patch: Partial<Filters>) => onChange({ ...f, ...patch });

  return (
    <div className="filter-bar">
      <div className="filter-group">
        <span className="filter-label">Colors</span>
        {COLORS.map((c) => (
          <button
            key={c}
            className={`pip-toggle${f.colors.includes(c) ? ' on' : ''}`}
            onClick={() => set({ colors: toggle(f.colors, c) })}
            title={c === 'C' ? 'Colorless' : c}
          >
            <img src={symbolUrl(`{${c}}`)} alt={c} width={18} height={18} />
          </button>
        ))}
        <select
          value={f.colorMode}
          onChange={(e) => set({ colorMode: e.target.value as ColorMode })}
          title="How color identity is matched"
        >
          <option value="within">fits within</option>
          <option value="any">includes any</option>
          <option value="exact">exactly</option>
        </select>
      </div>

      <div className="filter-group">
        <span className="filter-label">Type</span>
        {TYPES.map((t) => (
          <button key={t} className={`chip-toggle${f.types.includes(t) ? ' on' : ''}`} onClick={() => set({ types: toggle(f.types, t) })}>
            {t}
          </button>
        ))}
      </div>

      <details className="filter-group filter-categories">
        <summary>
          <span className="filter-label">Category</span>
          {f.categories.length ? <span className="filter-count">{f.categories.length} selected</span> : <span className="muted">any</span>}
        </summary>
        <div className="filter-cat-list">
          {categories.map((c) => (
            <button
              key={c}
              className={`chip-toggle${f.categories.includes(c) ? ' on' : ''}`}
              onClick={() => set({ categories: toggle(f.categories, c) })}
            >
              {c}
            </button>
          ))}
        </div>
      </details>

      <div className="filter-group">
        <span className="filter-label">Mana value</span>
        <input
          type="number"
          min={0}
          placeholder="min"
          value={f.mvMin ?? ''}
          onChange={(e) => set({ mvMin: num(e.target.value) })}
        />
        <span className="muted">–</span>
        <input
          type="number"
          min={0}
          placeholder="max"
          value={f.mvMax ?? ''}
          onChange={(e) => set({ mvMax: num(e.target.value) })}
        />
      </div>

      <div className="filter-group">
        <span className="filter-label">EDHREC</span>
        <select value={f.rankMax ?? ''} onChange={(e) => set({ rankMax: num(e.target.value) })}>
          {RANK_OPTIONS.map((o) => (
            <option key={o.label} value={o.value ?? ''}>
              {o.label}
            </option>
          ))}
        </select>
      </div>

      <div className="filter-group">
        <span className="filter-label">Rarity</span>
        {RARITIES.map((r) => (
          <button
            key={r}
            className={`chip-toggle rarity-${r}${f.rarities.includes(r) ? ' on' : ''}`}
            onClick={() => set({ rarities: toggle(f.rarities, r) })}
          >
            {r[0].toUpperCase() + r.slice(1)}
          </button>
        ))}
      </div>

      <div className="filter-group">
        <span className="filter-label">Max price $</span>
        <input
          type="number"
          min={0}
          step={0.5}
          placeholder="any"
          value={f.priceMax ?? ''}
          onChange={(e) => set({ priceMax: num(e.target.value) })}
        />
      </div>

      <div className="filter-group filter-summary">
        <span className="muted">
          {shown.toLocaleString()} of {total.toLocaleString()} cards
        </span>
        <button onClick={() => onChange(EMPTY_FILTERS)}>Clear filters</button>
      </div>
    </div>
  );
}
