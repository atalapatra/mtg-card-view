import { useEffect, useRef, useState, type ReactNode } from 'react';
import { api } from '../api';
import type { ImportResult, SeedMode } from '../types';

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

const PLACEHOLDER = `Paste a card list, one card per line. For example:

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

  // ManaBox CSV import: converted server-side into the same text format as a paste.
  const fileInput = useRef<HTMLInputElement>(null);
  const [csv, setCsv] = useState<{ text: string; file: string } | null>(null);
  const [includeTokens, setIncludeTokens] = useState(false);
  const [includeLists, setIncludeLists] = useState(false);
  const [imported, setImported] = useState<ImportResult | null>(null);
  const [importError, setImportError] = useState<string | null>(null);
  const [importing, setImporting] = useState(false);

  const convert = async (csvText: string, file: string, tokens: boolean, lists: boolean) => {
    setImporting(true);
    setImportError(null);
    try {
      const r = await api.importManabox(csvText, tokens, lists);
      setCsv({ text: csvText, file });
      setImported(r);
      setText(r.text);
      setName((n) => n || file.replace(/\.csv$/i, '').replace(/[_]+/g, ' '));
    } catch (e) {
      setImportError(e instanceof Error ? e.message : String(e));
    } finally {
      setImporting(false);
    }
  };

  const readFile = async (file: File | undefined) => {
    if (!file) return;
    const content = await file.text();
    if (/\.csv$/i.test(file.name) || /^﻿?[^\n]*\bQuantity\b/.test(content)) {
      await convert(content, file.name, includeTokens, includeLists);
    } else {
      // Plain text deck list file: use as-is.
      setCsv(null);
      setImported(null);
      setText(content);
      setName((n) => n || file.name.replace(/\.[^.]+$/, ''));
    }
  };

  return (
    <Modal title={isNew ? 'New collection' : 'Edit collection'} onClose={onClose}>
      <form
        className="deck-form"
        onSubmit={(e) => {
          e.preventDefault();
          onSave(name.trim() || suggested || 'Untitled collection', text);
        }}
      >
        <label>
          Name
          <input value={name} onChange={(e) => setName(e.target.value)} placeholder={suggested || 'Untitled collection'} />
        </label>
        <div className="import-row">
          <button type="button" onClick={() => fileInput.current?.click()} disabled={importing}>
            {importing ? 'Importing…' : 'Import ManaBox CSV…'}
          </button>
          <input
            ref={fileInput}
            type="file"
            accept=".csv,.txt,text/csv,text/plain"
            hidden
            onChange={(e) => {
              readFile(e.target.files?.[0]);
              e.target.value = '';
            }}
          />
          <label className="check">
            <input
              type="checkbox"
              checked={includeTokens}
              onChange={(e) => {
                setIncludeTokens(e.target.checked);
                if (csv) convert(csv.text, csv.file, e.target.checked, includeLists);
              }}
            />
            Include tokens
          </label>
          <label className="check">
            <input
              type="checkbox"
              checked={includeLists}
              onChange={(e) => {
                setIncludeLists(e.target.checked);
                if (csv) convert(csv.text, csv.file, includeTokens, e.target.checked);
              }}
            />
            Include wishlist lists
          </label>
        </div>
        {imported && csv && (
          <p className="hint import-summary">
            {csv.file}: {imported.cards.toLocaleString()} cards ({imported.unique.toLocaleString()} unique) imported
            {(imported.skipped_tokens > 0 || imported.skipped_lists > 0) &&
              ` · left out ${[
                imported.skipped_tokens > 0 && `${imported.skipped_tokens} tokens`,
                imported.skipped_lists > 0 && `${imported.skipped_lists} wishlist-list cards`,
              ]
                .filter(Boolean)
                .join(' and ')}`}
            {imported.errors.length > 0 && ` · ${imported.errors.length} rows skipped`}
          </p>
        )}
        {importError && <p className="warn">{importError}</p>}
        <label>
          Card list
          <textarea
            value={text}
            onChange={(e) => setText(e.target.value)}
            onDragOver={(e) => e.preventDefault()}
            onDrop={(e) => {
              if (e.dataTransfer.files.length) {
                e.preventDefault();
                readFile(e.dataTransfer.files[0]);
              }
            }}
            placeholder={PLACEHOLDER}
            rows={18}
            spellCheck={false}
            autoFocus={isNew}
          />
        </label>
        <p className="hint">
          Paste a list or drop a file here. Accepts plain, Moxfield, MTGA and Archidekt lists, and ManaBox CSV
          exports. Archidekt <code>[Categories]</code> and <code>#tags</code> become “Your tags”.
        </p>
        <footer className="modal-foot">
          {onDelete && (
            <button type="button" className="danger" onClick={onDelete}>
              Delete collection
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
  { value: 'section', label: 'List section' },
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
