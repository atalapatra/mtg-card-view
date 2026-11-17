import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { api } from '../api';
import type { Card, Connection, GraphData, GraphMode, Positions } from '../types';
import { GraphCanvas, type GEdge, type GNode, type GraphCanvasHandle } from './GraphCanvas';
import type { LayoutMessage, LayoutRequest } from './layoutWorker';

interface Props {
  deckId: number;
  cardsByKey: Map<string, Card>;
  search: (card: Card) => boolean;
  searchActive: boolean;
  selectedKey: string | null;
  /** Card open in the second sidebar (from a synergy link). */
  pairKey: string | null;
  onSelect: (card: Card | null) => void;
  /** Filter bar predicate: non-matching cards (and their links) are hidden, positions kept. */
  filter: (card: Card) => boolean;
  filterActive: boolean;
  /** Weighting mode; owned by App so it defaults to tags on load but survives view switches. */
  mode: GraphMode;
  onModeChange: (m: GraphMode) => void;
  /** Reports each card's connections (for the detail panel). */
  onConnections: (conns: Map<string, Connection[]> | null) => void;
}

/** Map raw edge weight to 0..1 for drawing / layout. */
function normalize(mode: GraphMode, raw: number): number {
  return mode === 'tags' ? Math.min(1, raw / 3) : Math.min(1, Math.max(0, raw) / 0.4);
}

function edgeLabel(mode: GraphMode, g: GraphData, e: GraphData['edges'][number]): string {
  return mode === 'tags' ? g.labels[e[3]] ?? '' : `${e[2] >= 0 ? '+' : ''}${Math.round(e[2] * 100)}% EDHREC synergy`;
}

function runLayout(req: LayoutRequest, onProgress: (p: number) => void): { promise: Promise<Positions>; cancel: () => void } {
  const worker = new Worker(new URL('./layoutWorker.ts', import.meta.url), { type: 'module' });
  const promise = new Promise<Positions>((resolve, reject) => {
    worker.onmessage = (e: MessageEvent<LayoutMessage>) => {
      if (e.data.type === 'progress') onProgress(e.data.done / e.data.total);
      else {
        resolve(e.data.positions);
        worker.terminate();
      }
    };
    worker.onerror = (e) => {
      reject(new Error(e.message || 'Layout failed'));
      worker.terminate();
    };
  });
  worker.postMessage(req);
  return { promise, cancel: () => worker.terminate() };
}

type Phase =
  | { kind: 'fetching' }
  | { kind: 'edhrec'; done: number; total: number }
  | { kind: 'layout'; progress: number }
  | { kind: 'ready' }
  | { kind: 'error'; message: string };

export function GraphView({
  deckId,
  cardsByKey,
  search,
  searchActive,
  selectedKey,
  pairKey,
  onSelect,
  filter,
  filterActive,
  mode,
  onModeChange: setMode,
  onConnections,
}: Props) {
  const [phase, setPhase] = useState<Phase>({ kind: 'fetching' });
  const [graph, setGraph] = useState<GraphData | null>(null);
  const [nodes, setNodes] = useState<GNode[]>([]);
  const [minRaw, setMinRaw] = useState<Record<GraphMode, number>>({ tags: 1, edhrec: 0.05 });
  const [saveState, setSaveState] = useState<'idle' | 'saving' | 'saved' | 'error'>('idle');
  const canvas = useRef<GraphCanvasHandle>(null);
  const layoutJob = useRef<{ cancel: () => void } | null>(null);
  const saveTimer = useRef(0);

  // Order nodes: connected first, unconnected by popularity (inner ring = most played).
  const prepare = useCallback(
    (g: GraphData) => {
      const degree = new Array(g.nodes.length).fill(0);
      for (const [s, t] of g.edges) {
        degree[s]++;
        degree[t]++;
      }
      const hubs = new Set(g.hubs);
      const idx = g.nodes.map((_, i) => i).filter((i) => cardsByKey.has(g.nodes[i]));
      const rank = (i: number) => cardsByKey.get(g.nodes[i])?.edhrec_rank ?? 1e9;
      idx.sort((a, b) => (degree[a] > 0 ? 0 : 1) - (degree[b] > 0 ? 0 : 1) || (degree[a] > 0 ? a - b : rank(a) - rank(b)));
      const remap = new Map(idx.map((old, i) => [old, i]));
      const ordered = idx.map((i) => ({ key: g.nodes[i], card: cardsByKey.get(g.nodes[i])!, hub: hubs.has(g.nodes[i]) }));
      const edges: GEdge[] = g.edges
        .filter(([s, t]) => remap.has(s) && remap.has(t))
        .map((e) => ({ s: remap.get(e[0])!, t: remap.get(e[1])!, raw: e[2], w: normalize(g.mode, e[2]) }));
      return { ordered, edges, origEdges: g.edges.filter(([s, t]) => remap.has(s) && remap.has(t)) };
    },
    [cardsByKey],
  );

  const prepared = useMemo(() => (graph ? prepare(graph) : null), [graph, prepare]);

  const savePositions = useCallback(
    (list: GNode[], m: GraphMode, delay = 800) => {
      setSaveState('saving');
      clearTimeout(saveTimer.current);
      saveTimer.current = window.setTimeout(() => {
        const positions: Positions = {};
        for (const n of list) positions[n.key] = [Math.round(n.x * 10) / 10, Math.round(n.y * 10) / 10];
        api
          .saveGraphLayout(deckId, m, positions)
          .then(() => setSaveState('saved'))
          .catch(() => setSaveState('error'));
      }, delay);
    },
    [deckId],
  );

  const layout = useCallback(
    (g: GraphData, saved: Positions | null) => {
      const p = prepare(g);
      layoutJob.current?.cancel();
      const allSaved = saved && p.ordered.every((n) => saved[n.key]);
      const finish = (pos: Positions, persist: boolean) => {
        const list = p.ordered.map((n) => ({ ...n, x: pos[n.key][0], y: pos[n.key][1] }));
        setNodes(list);
        setPhase({ kind: 'ready' });
        requestAnimationFrame(() => canvas.current?.fit());
        if (persist) savePositions(list, g.mode, 0);
      };
      if (allSaved) return finish(saved!, false);
      setPhase({ kind: 'layout', progress: 0 });
      const job = runLayout(
        {
          nodes: p.ordered.map((n) => ({ id: n.key, hub: n.hub, fixed: saved?.[n.key] })),
          edges: p.edges.map((e) => ({ s: e.s, t: e.t, w: e.w })),
        },
        (progress) => setPhase({ kind: 'layout', progress }),
      );
      layoutJob.current = job;
      job.promise.then((pos) => finish(pos, true)).catch((e) => setPhase({ kind: 'error', message: e.message }));
    },
    [prepare, savePositions],
  );

  // Fetch the graph (polling while EDHREC pages download), then lay it out.
  useEffect(() => {
    let cancelled = false;
    let timer = 0;
    setPhase({ kind: 'fetching' });
    setGraph(null);
    setNodes([]);
    setSaveState('idle');
    const load = async () => {
      try {
        const r = await api.getGraph(deckId, mode);
        if (cancelled) return;
        if (r.status === 'loading') {
          setPhase({ kind: 'edhrec', ...r.progress });
          timer = window.setTimeout(load, 1500);
          return;
        }
        setGraph(r.graph);
        layout(r.graph, r.layout);
      } catch (e) {
        if (!cancelled) setPhase({ kind: 'error', message: e instanceof Error ? e.message : String(e) });
      }
    };
    load();
    return () => {
      cancelled = true;
      clearTimeout(timer);
      layoutJob.current?.cancel();
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [deckId, mode]);

  // Connections for the detail panel.
  useEffect(() => {
    if (!graph || !prepared) {
      onConnections(null);
      return;
    }
    const map = new Map<string, Connection[]>();
    const add = (a: string, b: string, label: string, weight: number) => {
      if (!map.has(a)) map.set(a, []);
      map.get(a)!.push({ key: b, label, weight });
    };
    for (const e of graph.edges) {
      const a = graph.nodes[e[0]];
      const b = graph.nodes[e[1]];
      const label = edgeLabel(graph.mode, graph, e);
      add(a, b, label, e[2]);
      add(b, a, label, e[2]);
    }
    for (const list of map.values()) list.sort((x, y) => y.weight - x.weight);
    onConnections(map);
    return () => onConnections(null);
  }, [graph, prepared, onConnections]);

  const reset = () => {
    if (!graph) return;
    if (!confirm('Reset the graph to its original layout? Your manual arrangement will be lost.')) return;
    api.deleteGraphLayout(deckId, mode).catch(() => {});
    layout(graph, null);
  };

  const searchMatches = useMemo(() => {
    if (!searchActive) return null;
    return new Set(nodes.filter((n) => search(n.card)).map((n) => n.key));
  }, [nodes, search, searchActive]);

  // Filter bar: hide non-matching cards and their links. Node objects are shared with
  // `nodes`, so positions (and drags) are kept and saved for every card.
  const shown = useMemo(() => {
    const edges = prepared?.edges ?? [];
    if (!filterActive) return { nodes, edges };
    const remap = new Map<number, number>();
    const kept: GNode[] = [];
    nodes.forEach((n, i) => {
      if (filter(n.card)) {
        remap.set(i, kept.length);
        kept.push(n);
      }
    });
    const keptEdges: GEdge[] = [];
    for (const e of edges) {
      const s = remap.get(e.s);
      const t = remap.get(e.t);
      if (s != null && t != null) keptEdges.push({ ...e, s, t });
    }
    return { nodes: kept, edges: keptEdges };
  }, [nodes, prepared, filter, filterActive]);

  const threshold = minRaw[mode];
  const visibleEdges = shown.edges.filter((e) => e.raw >= threshold).length;
  const connectedCount = useMemo(() => {
    const s = new Set<number>();
    for (const e of shown.edges) {
      s.add(e.s);
      s.add(e.t);
    }
    return s.size;
  }, [shown]);

  return (
    <div className="graph-view">
      <div className="graph-toolbar">
        <div className="segmented" role="tablist" aria-label="Weighting">
          <button className={mode === 'tags' ? 'on' : ''} onClick={() => setMode('tags')}>
            Scryfall tag synergy
          </button>
          <button className={mode === 'edhrec' ? 'on' : ''} onClick={() => setMode('edhrec')}>
            EDHREC commander synergy
          </button>
        </div>

        {mode === 'tags' ? (
          <label className="field">
            Show links with
            <select value={threshold} onChange={(e) => setMinRaw({ ...minRaw, tags: Number(e.target.value) })}>
              <option value={1}>1+ shared themes</option>
              <option value={2}>2+ shared themes</option>
              <option value={3}>3+ shared themes</option>
            </select>
          </label>
        ) : (
          <label className="field">
            Min synergy
            <input
              type="range"
              min={0}
              max={0.5}
              step={0.01}
              value={threshold}
              onChange={(e) => setMinRaw({ ...minRaw, edhrec: Number(e.target.value) })}
            />
            <span className="range-value">+{Math.round(threshold * 100)}%</span>
          </label>
        )}

        <span className="graph-stats muted">
          {prepared &&
            `${filterActive ? `${shown.nodes.length.toLocaleString()} of ` : ''}${nodes.length.toLocaleString()} cards · ${connectedCount.toLocaleString()} connected · ${visibleEdges.toLocaleString()} links`}
          {graph?.mode === 'edhrec' && ` · ${graph.hubs.length} commanders`}
        </span>

        <span className="spacer" />
        <span className={`save-state ${saveState}`}>
          {saveState === 'saving' ? 'Saving layout…' : saveState === 'saved' ? 'Layout saved' : saveState === 'error' ? 'Save failed' : ''}
        </span>
        <button onClick={() => canvas.current?.fit()} disabled={phase.kind !== 'ready'} title="Zoom to fit (or double-click empty space)">
          Fit
        </button>
        <button onClick={reset} disabled={phase.kind !== 'ready'}>
          Reset layout
        </button>
      </div>

      {graph?.mode === 'edhrec' && (graph.meta.missing_pages?.length ?? 0) > 0 && (
        <p className="hint">
          No EDHREC page for: {graph.meta.missing_pages!.slice(0, 8).join(', ')}
          {graph.meta.missing_pages!.length > 8 && ` and ${graph.meta.missing_pages!.length - 8} more`}
        </p>
      )}
      {graph?.mode === 'edhrec' && graph.hubs.length === 0 && (
        <p className="hint">No legendary creatures in this collection — EDHREC synergy needs at least one commander.</p>
      )}

      <div className="graph-stage">
        {nodes.length > 0 && (
          <GraphCanvas
            handle={canvas}
            nodes={shown.nodes}
            edges={shown.edges}
            minRaw={threshold}
            selectedKey={selectedKey}
            secondaryKey={pairKey}
            searchMatches={searchMatches}
            onSelect={onSelect}
            onMoved={() => savePositions(nodes, mode)}
          />
        )}
        {phase.kind !== 'ready' && (
          <div className="graph-overlay">
            {phase.kind === 'fetching' && <Progress label="Building graph…" />}
            {phase.kind === 'edhrec' && (
              <Progress
                label={`Downloading EDHREC data for ${phase.total} commander${phase.total === 1 ? '' : 's'}… (cached afterwards)`}
                value={phase.done / Math.max(1, phase.total)}
                detail={`${phase.done} / ${phase.total}`}
              />
            )}
            {phase.kind === 'layout' && <Progress label="Arranging cards…" value={phase.progress} />}
            {phase.kind === 'error' && <p className="warn">{phase.message}</p>}
          </div>
        )}
        {phase.kind === 'ready' && (
          <div className="graph-legend">
            <span>Scroll to zoom · drag background to pan · drag cards to arrange · click for details</span>
            {mode === 'edhrec' && (
              <span>
                <span className="legend-hub" /> commander
              </span>
            )}
          </div>
        )}
      </div>
    </div>
  );
}

function Progress({ label, value, detail }: { label: string; value?: number; detail?: string }) {
  return (
    <div className="graph-progress">
      <div>{label}</div>
      <div className="bar">
        <div className={value == null ? 'indeterminate' : ''} style={value != null ? { width: `${Math.round(value * 100)}%` } : undefined} />
      </div>
      {detail && <div className="muted">{detail}</div>}
    </div>
  );
}
