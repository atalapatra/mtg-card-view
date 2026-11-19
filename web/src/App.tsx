import { useCallback, useEffect, useMemo, useRef, useState, type CSSProperties } from 'react';
import { api } from './api';
import { BoardView, type BoardEditHandlers } from './components/BoardView';
import { CardDetail } from './components/CardDetail';
import { DeckEditor, NewBoardDialog } from './components/Dialogs';
import { GridView } from './components/GridView';
import { usePreview } from './components/HoverPreview';
import { ColorPips } from './components/Symbols';
import { TableView } from './components/TableView';
import { GraphView } from './graph/GraphView';
import { SynergyBox } from './components/SynergyBox';
import type {
  BoardLayout,
  Card,
  Connection,
  DeckDetail,
  DeckSummary,
  GroupMode,
  SeedMode,
  SortBy,
  Filters,
  GraphMode,
  ViewGroup,
  ViewMode,
} from './types';
import { EMPTY_FILTERS, GROUP_LABELS, SORT_LABELS, UNSORTED_ID } from './types';
import * as ops from './util';
import { activeFilterCount, matchesFilters, matchesSearch, PAIR_HINT, sortCards } from './util';
import { FilterBar } from './components/FilterBar';
import { Resizer, useStoredWidth } from './components/Resizer';

const LAST_DECK_KEY = 'mtgcv.lastDeck';
const LEFT_MIN = 160;
const LEFT_MAX = 480;
const MAIN_MIN = 360; // the main area never gets narrower than this when sidebars are resized

function usePersisted<T extends string>(key: string, initial: T, allowed: readonly T[]): [T, (v: T) => void] {
  const [value, setValue] = useState<T>(() => {
    try {
      const v = localStorage.getItem(`mtgcv.${key}`) as T | null;
      return v && allowed.includes(v) ? v : initial;
    } catch {
      return initial;
    }
  });
  const set = useCallback(
    (v: T) => {
      setValue(v);
      try {
        localStorage.setItem(`mtgcv.${key}`, v);
      } catch {
        /* storage unavailable */
      }
    },
    [key],
  );
  return [value, set];
}

type Dialog = null | 'newDeck' | 'editDeck' | 'newBoard';
type SaveState = 'idle' | 'saving' | 'saved' | 'error';

export default function App() {
  const [decks, setDecks] = useState<DeckSummary[]>([]);
  const [detail, setDetail] = useState<DeckDetail | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  // Graph is the main view: the app always opens on it (D-020).
  const [view, setView] = useState<ViewMode>('graph');
  const [graphMode, setGraphMode] = useState<GraphMode>('tags'); // default: first enabled mode (tags unless disabled)
  // Enabled graph modes from the server (src/mtgcv/features.py); the graph waits for this.
  const [graphModes, setGraphModes] = useState<GraphMode[] | null>(null);
  const [filters, setFilters] = useState<Filters>(EMPTY_FILTERS);
  const [showFilters, setShowFilters] = useState(false);
  const [connections, setConnections] = useState<Map<string, Connection[]> | null>(null);
  const [sort, setSort] = usePersisted<SortBy>('sort', 'edhrec', ['edhrec', 'name', 'cmc', 'price']);
  const [grouping, setGrouping] = useState('auto:category'); // "auto:<mode>" | "board:<id>"
  const [search, setSearch] = useState('');
  const [selectedKey, setSelectedKey] = useState<string | null>(null);
  const [pairKey, setPairKey] = useState<string | null>(null);
  const [version, setVersion] = useState<string | null>(null);
  useEffect(() => {
    api
      .health()
      .then((h) => setVersion(h.version))
      .catch(() => {});
    api
      .config()
      .then((c) => {
        setGraphModes(c.graph_modes);
        setGraphMode((m) => (c.graph_modes.includes(m) ? m : c.graph_modes[0]));
      })
      .catch((e) => setError(`Couldn't load app settings: ${e instanceof Error ? e.message : String(e)}`));
  }, []);
  const [dialog, setDialog] = useState<Dialog>(null);
  const [saveState, setSaveState] = useState<SaveState>('idle');
  // Resizable sidebars: the collections list (left) and the card panel (right; separate width with two cards open).
  const [leftW, setLeftW, commitLeftW] = useStoredWidth('left', 220);
  const [detailW, setDetailW, commitDetailW] = useStoredWidth('detail', 360);
  const [pairW, setPairW, commitPairW] = useStoredWidth('pair', 720);
  const [viewportW, setViewportW] = useState(() => window.innerWidth);
  useEffect(() => {
    const onResize = () => setViewportW(window.innerWidth);
    window.addEventListener('resize', onResize);
    return () => window.removeEventListener('resize', onResize);
  }, []);
  const saveTimers = useRef(new Map<number, number>());

  const run = useCallback(async <T,>(label: string, fn: () => Promise<T>): Promise<T | undefined> => {
    setBusy(label);
    setError(null);
    try {
      return await fn();
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
      return undefined;
    } finally {
      setBusy(null);
    }
  }, []);

  const showDeck = (d: DeckDetail) => {
    setDetail(d);
    setSelectedKey(null);
    setPairKey(null);
    setSearch('');
    setGrouping((g) => (g.startsWith('board:') ? 'auto:category' : g));
    try {
      localStorage.setItem(LAST_DECK_KEY, String(d.deck.id));
    } catch {
      /* ignore */
    }
  };

  // Initial load: deck list + last opened deck
  useEffect(() => {
    run('Loading…', async () => {
      const list = await api.listDecks();
      setDecks(list);
      let last: number | null = null;
      try {
        last = Number(localStorage.getItem(LAST_DECK_KEY)) || null;
      } catch {
        /* ignore */
      }
      const target = list.find((d) => d.id === last) ?? list[0];
      if (target) showDeck(await api.getDeck(target.id));
    });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const preview = usePreview();
  useEffect(() => preview.hide(), [view, grouping, preview]);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key !== 'Escape' || dialog) return;
      // Close the second sidebar first, then the first.
      if (pairKey) setPairKey(null);
      else setSelectedKey(null);
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [dialog, pairKey]);

  // The second sidebar only exists in the graph view.
  useEffect(() => {
    if (view !== 'graph') setPairKey(null);
  }, [view]);

  // --- deck actions -----------------------------------------------------------
  const openDeck = (id: number) => run('Loading collection…', async () => showDeck(await api.getDeck(id)));

  // Guards against a second create/save starting while one is in flight (the dialog also locks its button).
  const savingDeck = useRef(false);
  const guarded = async (fn: () => Promise<unknown>) => {
    if (savingDeck.current) return;
    savingDeck.current = true;
    try {
      await fn();
    } finally {
      savingDeck.current = false;
    }
  };

  const createDeck = (name: string, text: string) =>
    guarded(() => run('Analyzing collection… (the first run downloads Scryfall tag data)', async () => {
      const d = await api.createDeck(name, text);
      showDeck(d);
      setGrouping('auto:category');
      setDialog(null);
      setDecks(await api.listDecks());
    }));

  const saveDeck = async (name: string, text: string) => {
    if (!detail) return;
    await guarded(() => run('Re-analyzing…', async () => {
      const d = await api.updateDeck(detail.deck.id, { name, text });
      setDetail(d);
      setDialog(null);
      setDecks(await api.listDecks());
    }));
  };

  const deleteCollection = (id: number, name: string) => {
    if (!confirm(`Delete the collection “${name}”? Its custom groupings and graph layouts are deleted too. This can't be undone.`))
      return;
    run('Deleting…', async () => {
      await api.deleteDeck(id);
      setDialog(null);
      const list = await api.listDecks();
      setDecks(list);
      if (detail?.deck.id === id) {
        if (list[0]) showDeck(await api.getDeck(list[0].id));
        else setDetail(null);
      }
    });
  };
  const deleteDeck = () => detail && deleteCollection(detail.deck.id, detail.deck.name);

  // --- custom groupings (boards) -------------------------------------------------
  const board =
    detail && grouping.startsWith('board:') ? detail.boards.find((b) => b.id === Number(grouping.slice(6))) : undefined;

  const createBoard = (name: string, seed: SeedMode) =>
    detail &&
    run('Creating grouping…', async () => {
      const b = await api.createBoard(detail.deck.id, name, seed);
      setDetail((d) => d && { ...d, boards: [...d.boards, b] });
      setGrouping(`board:${b.id}`);
      setView('board');
      setDialog(null);
    });

  const setBoardLayout = (boardId: number, layout: BoardLayout) => {
    setDetail((d) => d && { ...d, boards: d.boards.map((b) => (b.id === boardId ? { ...b, layout } : b)) });
    setSaveState('saving');
    const pending = saveTimers.current.get(boardId);
    if (pending) clearTimeout(pending);
    saveTimers.current.set(
      boardId,
      window.setTimeout(() => {
        saveTimers.current.delete(boardId);
        api
          .updateBoard(boardId, { layout })
          .then(() => setSaveState('saved'))
          .catch((e) => {
            setSaveState('error');
            setError(`Couldn't save grouping: ${e.message}`);
          });
      }, 400),
    );
  };

  const renameBoard = () => {
    if (!board) return;
    const name = prompt('Rename grouping', board.name)?.trim();
    if (!name || name === board.name) return;
    run('Saving…', async () => {
      const b = await api.updateBoard(board.id, { name });
      setDetail((d) => d && { ...d, boards: d.boards.map((x) => (x.id === b.id ? { ...x, name: b.name } : x)) });
    });
  };

  const deleteBoard = () => {
    if (!board || !confirm(`Delete the custom grouping “${board.name}”?`)) return;
    run('Deleting…', async () => {
      await api.deleteBoard(board.id);
      setDetail((d) => d && { ...d, boards: d.boards.filter((b) => b.id !== board.id) });
      setGrouping('auto:primary');
    });
  };

  const edit: BoardEditHandlers | undefined = board && {
    onMove: (key, to) => setBoardLayout(board.id, ops.moveCard(board.layout, key, to)),
    onRename: (id, name) => setBoardLayout(board.id, ops.renameGroup(board.layout, id, name)),
    onDelete: (id) => setBoardLayout(board.id, ops.deleteGroup(board.layout, id)),
    onShift: (id, delta) => setBoardLayout(board.id, ops.moveGroup(board.layout, id, delta)),
    onAdd: (name) => setBoardLayout(board.id, ops.addGroup(board.layout, name)),
  };

  // --- derive the groups to render -------------------------------------------------
  const cardsByKey = useMemo(() => new Map((detail?.report.cards ?? []).map((c) => [c.key, c])), [detail]);

  const groups: ViewGroup[] = useMemo(() => {
    if (!detail) return [];
    const visible = (keys: string[]) =>
      sortCards(
        keys
          .map((k) => cardsByKey.get(k))
          .filter((c): c is Card => !!c && matchesSearch(c, search) && matchesFilters(c, filters)),
        sort,
      );

    if (board) {
      const placed = new Set(board.layout.groups.flatMap((g) => g.cards));
      const unsorted = detail.report.cards.filter((c) => !placed.has(c.key)).map((c) => c.key);
      const custom = board.layout.groups.map((g) => ({ id: g.id, name: g.name, cards: visible(g.cards), editable: true }));
      return [{ id: UNSORTED_ID, name: 'Unsorted', cards: visible(unsorted), editable: false }, ...custom];
    }

    const mode = grouping.slice(5) as GroupMode;
    return (detail.report.groupings[mode] ?? [])
      .map((g, i) => ({ id: `auto-${i}`, name: g.name, cards: visible(g.cards), editable: false }))
      .filter((g) => g.cards.length > 0);
  }, [detail, board, grouping, search, sort, cardsByKey, filters]);

  const selectedCard = selectedKey ? cardsByKey.get(selectedKey) : undefined;
  const select = (c: Card) => {
    setSelectedKey((k) => (k === c.key ? null : c.key));
    setPairKey(null);
  };
  // Second sidebar (graph view only): a card opened from a synergy link.
  const pairCard =
    view === 'graph' && selectedCard && pairKey && pairKey !== selectedKey ? cardsByKey.get(pairKey) : undefined;
  /** Link clicked in the first sidebar: open (or replace) the second sidebar. */
  const openLinkFromFirst = (key: string) => {
    if (view === 'graph') setPairKey((k) => (k === key ? null : key));
    else setSelectedKey(key);
  };
  /** Link clicked in the second sidebar: walk the chain (second -> first, clicked -> second). */
  const openLinkFromSecond = (key: string) => {
    if (!pairKey || key === selectedKey) return;
    setSelectedKey(pairKey);
    setPairKey(key);
  };
  const searchFn = useCallback((c: Card) => matchesSearch(c, search), [search]);
  const filterFn = useCallback((c: Card) => matchesFilters(c, filters), [filters]);
  const filterCount = activeFilterCount(filters);
  const filteredTotal = useMemo(
    () => (detail ? detail.report.cards.filter((c) => matchesFilters(c, filters)).length : 0),
    [detail, filters],
  );
  const categoryNames = useMemo(() => Object.keys(detail?.report.summary.category_counts ?? {}), [detail]);
  const isGraph = view === 'graph';
  const colorize = grouping === 'auto:category' || grouping === 'auto:primary' || !!board;

  // Sidebar widths, clamped so the main area always keeps MAIN_MIN px (a stored width may exceed a smaller window).
  const hasRight = !!(selectedCard && detail);
  const rightMin = pairCard ? 480 : 280;
  const leftWidth = Math.max(LEFT_MIN, Math.min(leftW, LEFT_MAX, viewportW - MAIN_MIN - (hasRight ? rightMin : 0)));
  const rightWanted = pairCard ? pairW : detailW;
  const rightWidth = Math.max(rightMin, Math.min(rightWanted, viewportW - leftWidth - MAIN_MIN));
  const layoutVars = { '--left-w': `${leftWidth}px`, '--right-w': `${rightWidth}px` } as CSSProperties;

  // --- render ---------------------------------------------------------------------
  const s = detail?.report.summary;

  return (
    <div className={`app${pairCard ? ' with-pair' : selectedCard ? ' with-detail' : ''}`} style={layoutVars}>
      <Resizer
        side="left"
        label="Resize collections sidebar"
        width={leftWidth}
        min={LEFT_MIN}
        max={() => Math.min(LEFT_MAX, window.innerWidth - MAIN_MIN - (hasRight ? rightWidth : 0))}
        defaultWidth={220}
        onChange={setLeftW}
        onCommit={commitLeftW}
      />
      {hasRight && (
        <Resizer
          side="right"
          label="Resize card panel"
          width={rightWidth}
          min={rightMin}
          max={() => window.innerWidth - leftWidth - MAIN_MIN}
          defaultWidth={pairCard ? 720 : 360}
          onChange={pairCard ? setPairW : setDetailW}
          onCommit={pairCard ? commitPairW : commitDetailW}
        />
      )}
      <nav className="sidebar">
        <div className="brand">GraphMTG</div>
        <button className="primary new-deck" onClick={() => setDialog('newDeck')}>
          + New collection
        </button>
        <div className="sidebar-label">Collections</div>
        <ul className="deck-list">
          {decks.map((d) => (
            <li key={d.id}>
              <button className={d.id === detail?.deck.id ? 'active' : ''} onClick={() => openDeck(d.id)}>
                <span className="deck-name">{d.name}</span>
                <span className="muted">{d.card_count}</span>
              </button>
              <button
                className="icon danger deck-delete"
                title={`Delete “${d.name}”`}
                aria-label={`Delete ${d.name}`}
                onClick={() => deleteCollection(d.id, d.name)}
              >
                ×
              </button>
            </li>
          ))}
        </ul>
        <p className="credit">
          Card data &amp; images from <a href="https://scryfall.com" target="_blank" rel="noreferrer">Scryfall</a>.
          Ranks from EDHREC.
          {version && <span className="version">GraphMTG v{version}</span>}
        </p>
      </nav>

      <main className={`main${isGraph && detail ? ' graph-mode' : ''}`}>
        {error && (
          <div className="banner error">
            {error}
            <button className="icon" onClick={() => setError(null)}>
              ×
            </button>
          </div>
        )}

        {!detail ? (
          !busy && (
            <div className="empty-state">
              <h1>Welcome to GraphMTG</h1>
              <p>
                Paste a card list or import a ManaBox export to see how your cards work together: a synergy graph, each card's role, Scryfall tags and EDHREC rank.
              </p>
              <button className="primary" onClick={() => setDialog('newDeck')}>
                New collection
              </button>
            </div>
          )
        ) : (
          <>
            <header className="deck-head">
              <div className="deck-title">
                <h1>{detail.deck.name}</h1>
                <button onClick={() => setDialog('editDeck')}>Edit list</button>
                <button className="danger" onClick={deleteDeck}>
                  Delete
                </button>
              </div>
              {s && (
                <div className="summary">
                  <Stat label="Cards" value={`${s.total_cards}`} />
                  <Stat label="Lands" value={`${s.lands}`} />
                  <Stat label="Avg MV" value={`${s.average_cmc_nonland}`} hint="Average mana value of nonland cards" />
                  <Stat label="Identity" value={<ColorPips colors={s.color_identity} />} />
                  <Stat
                    label="Game Changers"
                    value={`${s.game_changers.length}`}
                    hint={s.game_changers.join(', ') || 'None'}
                  />
                  <Stat label="Price" value={`$${s.total_price_usd.toFixed(0)}`} hint="TCGplayer market (USD)" />
                </div>
              )}
            </header>

            {(detail.report.not_found.length > 0 || detail.report.parse_errors.length > 0) && (
              <div className="banner warn">
                {detail.report.not_found.length > 0 && (
                  <div>Not found on Scryfall: {detail.report.not_found.join(', ')}</div>
                )}
                {detail.report.parse_errors.map((e) => (
                  <div key={e.line}>
                    Couldn't read line {e.line}: <code>{e.text}</code>
                  </div>
                ))}
              </div>
            )}

            <div className="toolbar">
              <div className="segmented" role="tablist" aria-label="View">
                {(['graph', 'board', 'table', 'grid'] as ViewMode[]).map((v) => (
                  <button key={v} className={view === v ? 'on' : ''} onClick={() => setView(v)}>
                    {{ board: 'Board', table: 'Table', grid: 'Images', graph: 'Graph' }[v]}
                  </button>
                ))}
              </div>

              {!isGraph && (
              <>
              <label className="field">
                Group by
                <select
                  value={grouping}
                  onChange={(e) => (e.target.value === 'new' ? setDialog('newBoard') : setGrouping(e.target.value))}
                >
                  <optgroup label="Automatic">
                    {(Object.keys(GROUP_LABELS) as GroupMode[]).map((m) => (
                      <option key={m} value={`auto:${m}`}>
                        {GROUP_LABELS[m]}
                      </option>
                    ))}
                  </optgroup>
                  <optgroup label="Custom groupings">
                    {detail.boards.map((b) => (
                      <option key={b.id} value={`board:${b.id}`}>
                        {b.name}
                      </option>
                    ))}
                    <option value="new">+ New custom grouping…</option>
                  </optgroup>
                </select>
              </label>

              <label className="field">
                Sort
                <select value={sort} onChange={(e) => setSort(e.target.value as SortBy)}>
                  {(Object.keys(SORT_LABELS) as SortBy[]).map((k) => (
                    <option key={k} value={k}>
                      {SORT_LABELS[k]}
                    </option>
                  ))}
                </select>
              </label>
              </>
              )}

              <input
                className="search"
                type="search"
                placeholder={isGraph ? 'Highlight by name, text, tag…' : 'Filter by name, text, tag…'}
                value={search}
                onChange={(e) => setSearch(e.target.value)}
              />

              <button
                className={`filters-btn${showFilters || filterCount ? ' on' : ''}`}
                onClick={() => setShowFilters((v) => !v)}
                aria-expanded={showFilters}
              >
                Filters{filterCount > 0 && <span className="badge">{filterCount}</span>}
              </button>

              {board && !isGraph && (
                <div className="board-actions">
                  <span className={`save-state ${saveState}`}>
                    {saveState === 'saving' ? 'Saving…' : saveState === 'saved' ? 'Saved' : saveState === 'error' ? 'Save failed' : ''}
                  </span>
                  <button onClick={renameBoard}>Rename</button>
                  <button className="danger" onClick={deleteBoard}>
                    Delete grouping
                  </button>
                </div>
              )}
            </div>

            {showFilters && (
              <FilterBar
                filters={filters}
                onChange={setFilters}
                categories={categoryNames}
                shown={filteredTotal}
                total={detail.report.cards.length}
              />
            )}

            {board && view !== 'board' && !isGraph && (
              <p className="hint">Switch to Board view to drag cards between groups.</p>
            )}
            {grouping === 'auto:category' && !isGraph && (
              <p className="hint">Cards appear in every category they fit. Use “Primary category” to show each card once.</p>
            )}

            <div className="content">
              {view === 'board' && (
                <BoardView groups={groups} selectedKey={selectedKey} onSelect={select} edit={edit} colorize={colorize} />
              )}
              {view === 'table' && (
                <TableView groups={groups} selectedKey={selectedKey} onSelect={select} sort={sort} onSort={setSort} />
              )}
              {view === 'grid' && <GridView groups={groups} selectedKey={selectedKey} onSelect={select} />}
              {isGraph && graphModes && (
                <GraphView
                  deckId={detail.deck.id}
                  cardsByKey={cardsByKey}
                  search={searchFn}
                  searchActive={search.trim().length > 0}
                  filter={filterFn}
                  filterActive={filterCount > 0}
                  mode={graphMode}
                  modes={graphModes}
                  onModeChange={setGraphMode}
                  selectedKey={selectedKey}
                  pairKey={pairKey}
                  onSelect={(c) => {
                    setSelectedKey(c ? c.key : null);
                    setPairKey(null);
                  }}
                  onPair={(c) => openLinkFromFirst(c.key)}
                  onConnections={setConnections}
                />
              )}
            </div>
          </>
        )}
      </main>

      {selectedCard && detail && pairCard ? (
        <div className="side-pair">
          <SynergyBox
            deckId={detail.deck.id}
            a={selectedCard}
            b={pairCard}
            cardsByKey={cardsByKey}
            tagDescriptions={detail.report.tag_descriptions}
            onClose={() => setPairKey(null)}
            onSwap={() => {
              setSelectedKey(pairCard.key);
              setPairKey(selectedCard.key);
            }}
          />
          <div className="side-cols">
            <CardDetail
              key={selectedCard.key}
              card={selectedCard}
              tagDescriptions={detail.report.tag_descriptions}
              onClose={() => {
                // Closing the first card promotes the second one.
                setSelectedKey(pairCard.key);
                setPairKey(null);
              }}
              onSearch={setSearch}
              connections={connections?.get(selectedCard.key) ?? []}
              cardsByKey={cardsByKey}
              onSelectKey={openLinkFromFirst}
              activeLinkKey={pairCard.key}
            />
            <CardDetail
              key={pairCard.key}
              card={pairCard}
              tagDescriptions={detail.report.tag_descriptions}
              onClose={() => setPairKey(null)}
              onSearch={setSearch}
              connections={connections?.get(pairCard.key) ?? []}
              cardsByKey={cardsByKey}
              onSelectKey={openLinkFromSecond}
              activeLinkKey={selectedCard.key}
            />
          </div>
        </div>
      ) : (
        selectedCard &&
        detail && (
          <CardDetail
            key={selectedCard.key}
            card={selectedCard}
            tagDescriptions={detail.report.tag_descriptions}
            onClose={() => setSelectedKey(null)}
            onSearch={setSearch}
            connections={isGraph ? (connections?.get(selectedCard.key) ?? []) : undefined}
            cardsByKey={cardsByKey}
            onSelectKey={openLinkFromFirst}
            hint={isGraph ? PAIR_HINT : undefined}
          />
        )
      )}

      {busy && (
        <div className="busy">
          <span className="spinner" /> {busy}
        </div>
      )}

      {dialog === 'newDeck' && <DeckEditor isNew onSave={createDeck} onClose={() => setDialog(null)} />}
      {dialog === 'editDeck' && detail && (
        <DeckEditor
          isNew={false}
          initialName={detail.deck.name}
          initialText={detail.deck.text}
          onSave={saveDeck}
          onDelete={deleteDeck}
          onClose={() => setDialog(null)}
        />
      )}
      {dialog === 'newBoard' && <NewBoardDialog onCreate={createBoard} onClose={() => setDialog(null)} />}
    </div>
  );
}

function Stat({ label, value, hint }: { label: string; value: React.ReactNode; hint?: string }) {
  return (
    <div className="stat" title={hint}>
      <span className="stat-value">{value}</span>
      <span className="stat-label">{label}</span>
    </div>
  );
}
