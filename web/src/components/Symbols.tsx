import { symbolUrl } from '../util';

const SYMBOL_RE = /(\{[^}]+\})/g;
const IS_SYMBOL = /^\{[^}]+\}$/;

function Sym({ s, size }: { s: string; size: number }) {
  return <img className="sym" src={symbolUrl(s)} alt={s} title={s} width={size} height={size} draggable={false} />;
}

/** Mana cost like "{2}{W}{U}" or "{1}{R} // {1}{U}" rendered as Scryfall symbols. */
export function ManaCost({ cost, size = 15 }: { cost: string; size?: number }) {
  if (!cost) return null;
  const faces = cost.split(' // ');
  return (
    <span className="mana-cost">
      {faces.map((face, i) => (
        <span key={i} className="mana-face">
          {i > 0 && <span className="face-sep">//</span>}
          {(face.match(SYMBOL_RE) ?? []).map((s, j) => (
            <Sym key={j} s={s} size={size} />
          ))}
        </span>
      ))}
    </span>
  );
}

/** Oracle text with inline mana/tap symbols. */
export function SymbolText({ text }: { text: string }) {
  return (
    <>
      {text.split(SYMBOL_RE).map((part, i) =>
        IS_SYMBOL.test(part) ? <Sym key={i} s={part} size={14} /> : <span key={i}>{part}</span>,
      )}
    </>
  );
}

export function ColorPips({ colors, size = 16 }: { colors: string[]; size?: number }) {
  const list = colors.length ? colors : ['C'];
  return (
    <span className="mana-cost">
      {list.map((c) => (
        <Sym key={c} s={`{${c}}`} size={size} />
      ))}
    </span>
  );
}
