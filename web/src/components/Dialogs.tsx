import { useEffect, useState, type ReactNode } from 'react';
import type { SeedMode } from '../types';

function Modal({ title, onClose, children }: { title: string; onClose: () => void; children: ReactNode }) {
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => e.key === 'Escape' && onClose();
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [onClose]);
  return (
    <div className="modal-backdrop" onMouseDown={(e) => e.target === e.currentTarget && onClose()}>
      <div className="modal" role="dialog" aria-label={title}>
        <header className="modal-head">
          <h2>{title}</h2>
          <button className="icon" onClick={onClose}>
            ×
          </button>
        </header>
        {children}
      </div>
    </div>
  );
}

const PLACEHOLDER = `Paste a deck list, one card per line. For example:

Commander
1 Atraxa, Praetors' Voice

Deck
1 Sol Ring
1x Arcane Signet (C21) 263
1 Cultivate [Ramp]
4 Forest`;

function guessName(text: string): string {
  // First card under a "Commander" header, if any
  const lines = text.split(/\r?\n/).map((l) => l.trim());
  const i = lines.findIndex((l) => /^\/*\s*commanders?:?$/i.test(l));
  if (i >= 0) {
    const next = lines.slice(i + 1).find(Boolean);
    if (next) return next.replace(/^\d+x?\s+/i, '').replace(/\s+\(.*$/, '');
  }
  return '';
}

export function DeckEditor({
  initialName = '',
  initialText = '',
  isNew,
  onSave,
  onDelete,
  onClose,
}: {
  initialName?: string;
  initialText?: string;
  isNew: boolean;
  onSave: (name: string, text: string) => void;
  onDelete?: () => void;
  onClose: () => void;
}) {
  const [name, setName] = useState(initialName);
  const [text, setText] = useState(initialText);
  const suggested = guessName(text);

  return (
    <Modal title={isNew ? 'New deck' : 'Edit deck'} onClose={onClose}>
      <form
        className="deck-form"
        onSubmit={(e) => {
          e.preventDefault();
          onSave(name.trim() || suggested || 'Untitled deck', text);
        }}
      >
        <label>
          Name
          <input value={name} onChange={(e) => setName(e.target.value)} placeholder={suggested || 'Untitled deck'} />
        </label>
        <label>
          Card list
          <textarea
            value={text}
            onChange={(e) => setText(e.target.value)}
            placeholder={PLACEHOLDER}
            rows={18}
            spellCheck={false}
            autoFocus={isNew}
          />
        </label>
        <p className="hint">
          Accepts plain, Moxfield, MTGA and Archidekt exports. Archidekt <code>[Categories]</code> and{' '}
          <code>#tags</code> become “Your tags”.
        </p>
        <footer className="modal-foot">
          {onDelete && (
            <button type="button" className="danger" onClick={onDelete}>
              Delete deck
            </button>
          )}
          <span className="spacer" />
          <button type="button" onClick={onClose}>
            Cancel
          </button>
          <button type="submit" className="primary" disabled={!text.trim()}>
            {isNew ? 'Analyze & save' : 'Save'}
          </button>
        </footer>
      </form>
    </Modal>
  );
}

const SEED_OPTIONS: { value: SeedMode; label: string }[] = [
  { value: 'primary', label: 'Primary category' },
  { value: 'type', label: 'Card type' },
  { value: 'cmc', label: 'Mana value' },
  { value: 'color', label: 'Color' },
  { value: 'user_tag', label: 'Your tags' },
  { value: 'section', label: 'Deck section' },
  { value: 'empty', label: 'Nothing — start empty (all cards Unsorted)' },
];

export function NewBoardDialog({
  onCreate,
  onClose,
}: {
  onCreate: (name: string, seed: SeedMode) => void;
  onClose: () => void;
}) {
  const [name, setName] = useState('');
  const [seed, setSeed] = useState<SeedMode>('primary');
  return (
    <Modal title="New custom grouping" onClose={onClose}>
      <form
        className="deck-form"
        onSubmit={(e) => {
          e.preventDefault();
          onCreate(name.trim() || 'My grouping', seed);
        }}
      >
        <label>
          Name
          <input autoFocus value={name} onChange={(e) => setName(e.target.value)} placeholder="My grouping" />
        </label>
        <label>
          Start from
          <select value={seed} onChange={(e) => setSeed(e.target.value as SeedMode)}>
            {SEED_OPTIONS.map((o) => (
              <option key={o.value} value={o.value}>
                {o.label}
              </option>
            ))}
          </select>
        </label>
        <p className="hint">
          You can then drag cards between groups, add, rename, reorder and delete groups. Changes save automatically.
        </p>
        <footer className="modal-foot">
          <span className="spacer" />
          <button type="button" onClick={onClose}>
            Cancel
          </button>
          <button type="submit" className="primary">
            Create
          </button>
        </footer>
      </form>
    </Modal>
  );
}
