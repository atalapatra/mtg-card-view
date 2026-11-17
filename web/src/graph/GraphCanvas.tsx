// Canvas renderer for the synergy graph, built to stay smooth with thousands of cards:
//  * only nodes/edges inside the viewport are drawn
//  * level of detail: colored card shapes when zoomed out, Scryfall "small" images at
//    mid zoom, "normal" images when zoomed in
//  * images load lazily (only for visible cards, a few at a time, most recent first)
//  * edges are batched into a handful of strokes by weight bucket

import { useCallback, useEffect, useImperativeHandle, useMemo, useRef, type Ref } from 'react';
import { usePreview } from '../components/HoverPreview';
import type { Card } from '../types';

export interface GNode {
  key: string;
  card: Card;
  hub: boolean;
  x: number;
  y: number;
}

export interface GEdge {
  s: number;
  t: number;
  w: number; // normalized 0..1 (drawing)
  raw: number; // raw weight (filtering / labels)
}

export interface GraphCanvasHandle {
  fit: () => void;
  redraw: () => void;
}

interface Props {
  nodes: GNode[];
  edges: GEdge[];
  minRaw: number;
  selectedKey: string | null;
  searchMatches: Set<string> | null;
  onSelect: (card: Card | null) => void;
  onMoved: () => void;
  handle: Ref<GraphCanvasHandle>;
}

const W = 60;
const H = 84;
const HUB_SCALE = 1.7;
const MAX_LOADS = 10;

const IDENTITY_COLOR: Record<string, string> = {
  W: '#e8dfc0',
  U: '#3d7cc9',
  B: '#5b4e5a',
  R: '#cf4f3a',
  G: '#3d9358',
  M: '#d4a937',
  C: '#9aa0a6',
};

function nodeColor(c: Card): string {
  const ci = c.color_identity;
  if (ci.length === 0) return IDENTITY_COLOR.C;
  if (ci.length > 1) return IDENTITY_COLOR.M;
  return IDENTITY_COLOR[ci[0]] ?? IDENTITY_COLOR.C;
}

type ImgState = HTMLImageElement | 'queued' | 'loading' | 'error';

export function GraphCanvas({ nodes, edges, minRaw, selectedKey, searchMatches, onSelect, onMoved, handle }: Props) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const cam = useRef({ k: 0.5, tx: 0, ty: 0 });
  const size = useRef({ w: 0, h: 0 });
  const hover = useRef<number | null>(null);
  const images = useRef(new Map<string, ImgState>());
  const queue = useRef<string[]>([]);
  const active = useRef(0);
  const frame = useRef(0);
  const preview = usePreview();

  // Latest props for the draw loop without re-binding listeners.
  const props = useRef({ nodes, edges, minRaw, selectedKey, searchMatches });
  props.current = { nodes, edges, minRaw, selectedKey, searchMatches };

  const neighbors = useMemo(() => {
    const adj: number[][] = nodes.map(() => []);
    for (const e of edges) {
      adj[e.s].push(e.t);
      adj[e.t].push(e.s);
    }
    return adj;
  }, [nodes, edges]);
  const neighborsRef = useRef(neighbors);
  neighborsRef.current = neighbors;

  const requestDraw = useCallback(() => {
    if (!frame.current) frame.current = requestAnimationFrame(draw);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // --- image loading ------------------------------------------------------------------
  const pump = useCallback(() => {
    while (active.current < MAX_LOADS && queue.current.length) {
      const url = queue.current.pop()!;
      if (images.current.get(url) !== 'queued') continue;
      images.current.set(url, 'loading');
      active.current++;
      const img = new Image();
      img.decoding = 'async';
      img.onload = () => {
        images.current.set(url, img);
        active.current--;
        requestDraw();
        pump();
      };
      img.onerror = () => {
        images.current.set(url, 'error');
        active.current--;
        pump();
      };
      img.src = url;
    }
  }, [requestDraw]);

  const getImage = (url: string | null): HTMLImageElement | null => {
    if (!url) return null;
    const v = images.current.get(url);
    if (v instanceof HTMLImageElement) return v;
    if (!v) {
      images.current.set(url, 'queued');
      queue.current.push(url);
    }
    return null;
  };

  // --- drawing --------------------------------------------------------------------------
  function draw() {
    frame.current = 0;
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;
    const { nodes, edges, minRaw, selectedKey, searchMatches } = props.current;
    const { k, tx, ty } = cam.current;
    const { w, h } = size.current;
    const dpr = window.devicePixelRatio || 1;

    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    ctx.clearRect(0, 0, w, h);
    ctx.setTransform(dpr * k, 0, 0, dpr * k, dpr * tx, dpr * ty);

    const pad = (W * HUB_SCALE) / 2;
    const x0 = -tx / k - pad;
    const y0 = -ty / k - pad;
    const x1 = (w - tx) / k + pad;
    const y1 = (h - ty) / k + pad;
    const inView = (n: GNode) => n.x >= x0 && n.x <= x1 && n.y >= y0 && n.y <= y1;

    const selectedIdx = selectedKey ? nodes.findIndex((n) => n.key === selectedKey) : -1;
    const focus = hover.current ?? (selectedIdx >= 0 ? selectedIdx : null);
    const focusSet = focus != null ? new Set([focus, ...neighborsRef.current[focus]]) : null;

    const css = getComputedStyle(canvas);
    const edgeColor = css.getPropertyValue('--graph-edge').trim() || '#8f96a3';
    const accent = css.getPropertyValue('--accent').trim() || '#d4a937';

    // Edges: 4 alpha buckets, one stroke each.
    const buckets: GEdge[][] = [[], [], [], []];
    const focusEdges: GEdge[] = [];
    for (const e of edges) {
      if (e.raw < minRaw) continue;
      const a = nodes[e.s];
      const b = nodes[e.t];
      if (Math.max(a.x, b.x) < x0 || Math.min(a.x, b.x) > x1 || Math.max(a.y, b.y) < y0 || Math.min(a.y, b.y) > y1) continue;
      if (focus != null && (e.s === focus || e.t === focus)) focusEdges.push(e);
      else buckets[Math.min(3, Math.floor(e.w * 4))].push(e);
    }
    ctx.strokeStyle = edgeColor;
    ctx.lineCap = 'round';
    const dim = focusSet ? 0.35 : 1;
    buckets.forEach((list, i) => {
      if (!list.length) return;
      ctx.globalAlpha = [0.14, 0.24, 0.36, 0.5][i] * dim;
      ctx.lineWidth = (0.8 + i * 0.6) / Math.max(k, 0.15);
      ctx.beginPath();
      for (const e of list) {
        ctx.moveTo(nodes[e.s].x, nodes[e.s].y);
        ctx.lineTo(nodes[e.t].x, nodes[e.t].y);
      }
      ctx.stroke();
    });
    if (focusEdges.length) {
      ctx.strokeStyle = accent;
      ctx.globalAlpha = 0.9;
      for (const e of focusEdges) {
        ctx.lineWidth = (1.2 + e.w * 3) / Math.max(k, 0.15);
        ctx.beginPath();
        ctx.moveTo(nodes[e.s].x, nodes[e.s].y);
        ctx.lineTo(nodes[e.t].x, nodes[e.t].y);
        ctx.stroke();
      }
    }

    // Nodes: regular cards first, hubs on top, focused ones last.
    const order: number[] = [];
    const late: number[] = [];
    nodes.forEach((n, i) => {
      if (!inView(n)) return;
      if (n.hub || (focusSet && focusSet.has(i))) late.push(i);
      else order.push(i);
    });
    const textColor = css.getPropertyValue('--text').trim() || '#fff';
    for (const i of [...order, ...late]) {
      const n = nodes[i];
      const s = n.hub ? HUB_SCALE : 1;
      const nw = W * s;
      const nh = H * s;
      const sw = nw * k; // on-screen width in px
      let alpha = 1;
      if (searchMatches && !searchMatches.has(n.key)) alpha = 0.12;
      else if (focusSet && !focusSet.has(i)) alpha = 0.25;
      ctx.globalAlpha = alpha;
      const left = n.x - nw / 2;
      const top = n.y - nh / 2;

      let img: HTMLImageElement | null = null;
      if (sw >= 14 && alpha > 0.2) {
        img = sw >= 120 ? getImage(n.card.image_normal) ?? getImage(n.card.image_small) : getImage(n.card.image_small);
      }
      if (img) {
        ctx.drawImage(img, left, top, nw, nh);
      } else {
        ctx.fillStyle = nodeColor(n.card);
        ctx.fillRect(left, top, nw, nh);
        if (sw >= 40) {
          ctx.fillStyle = '#111';
          ctx.font = `${10 * s}px system-ui, sans-serif`;
          ctx.fillText(n.card.name.split(' // ')[0].slice(0, 14), left + 4 * s, top + 13 * s, nw - 8 * s);
        }
      }
      if (n.hub) {
        ctx.strokeStyle = accent;
        ctx.lineWidth = Math.max(3, 2.5 / k);
        ctx.strokeRect(left, top, nw, nh);
      }
      if (i === selectedIdx || i === hover.current) {
        ctx.globalAlpha = 1;
        ctx.strokeStyle = i === selectedIdx ? accent : textColor;
        ctx.lineWidth = Math.max(2, 2.5 / k);
        ctx.strokeRect(left - 2 / k, top - 2 / k, nw + 4 / k, nh + 4 / k);
      }
    }
    ctx.globalAlpha = 1;
    pump();
  }

  // --- camera -----------------------------------------------------------------------------
  const fit = useCallback(() => {
    const { nodes } = props.current;
    const { w, h } = size.current;
    if (!nodes.length || !w || !h) return;
    let minX = Infinity, minY = Infinity, maxX = -Infinity, maxY = -Infinity;
    for (const n of nodes) {
      minX = Math.min(minX, n.x);
      maxX = Math.max(maxX, n.x);
      minY = Math.min(minY, n.y);
      maxY = Math.max(maxY, n.y);
    }
    const bw = maxX - minX + W * 4;
    const bh = maxY - minY + H * 4;
    const k = Math.min(w / bw, h / bh, 2);
    cam.current = { k, tx: w / 2 - ((minX + maxX) / 2) * k, ty: h / 2 - ((minY + maxY) / 2) * k };
    requestDraw();
  }, [requestDraw]);

  useImperativeHandle(handle, () => ({ fit, redraw: requestDraw }), [fit, requestDraw]);

  // Resize to container (crisp on HiDPI).
  useEffect(() => {
    const canvas = canvasRef.current!;
    const ro = new ResizeObserver(() => {
      const r = canvas.getBoundingClientRect();
      const dpr = window.devicePixelRatio || 1;
      const first = size.current.w === 0;
      size.current = { w: r.width, h: r.height };
      canvas.width = Math.round(r.width * dpr);
      canvas.height = Math.round(r.height * dpr);
      if (first) fit();
      else requestDraw();
    });
    ro.observe(canvas);
    return () => ro.disconnect();
  }, [fit, requestDraw]);

  useEffect(() => {
    requestDraw();
  }, [nodes, edges, minRaw, selectedKey, searchMatches, requestDraw]);

  useEffect(() => () => cancelAnimationFrame(frame.current), []);

  // --- interaction --------------------------------------------------------------------------
  const toWorld = (clientX: number, clientY: number) => {
    const r = canvasRef.current!.getBoundingClientRect();
    const { k, tx, ty } = cam.current;
    return { x: (clientX - r.left - tx) / k, y: (clientY - r.top - ty) / k };
  };

  const hitTest = (wx: number, wy: number): number | null => {
    const { nodes } = props.current;
    // Hubs are drawn on top, so test them first.
    for (let pass = 0; pass < 2; pass++) {
      for (let i = nodes.length - 1; i >= 0; i--) {
        const n = nodes[i];
        if (n.hub !== (pass === 0)) continue;
        const s = n.hub ? HUB_SCALE : 1;
        if (Math.abs(wx - n.x) <= (W * s) / 2 && Math.abs(wy - n.y) <= (H * s) / 2) return i;
      }
    }
    return null;
  };

  const drag = useRef<
    | { kind: 'node'; idx: number; dx: number; dy: number; sx: number; sy: number; moved: boolean }
    | { kind: 'pan'; tx: number; ty: number; sx: number; sy: number; moved: boolean }
    | null
  >(null);

  const onPointerDown = (e: React.PointerEvent) => {
    if (e.button !== 0) return;
    canvasRef.current!.setPointerCapture(e.pointerId);
    preview.hide();
    const p = toWorld(e.clientX, e.clientY);
    const hit = hitTest(p.x, p.y);
    if (hit != null) {
      const n = props.current.nodes[hit];
      drag.current = { kind: 'node', idx: hit, dx: p.x - n.x, dy: p.y - n.y, sx: e.clientX, sy: e.clientY, moved: false };
    } else {
      drag.current = { kind: 'pan', tx: cam.current.tx, ty: cam.current.ty, sx: e.clientX, sy: e.clientY, moved: false };
    }
  };

  const onPointerMove = (e: React.PointerEvent) => {
    const d = drag.current;
    const canvas = canvasRef.current!;
    if (d) {
      if (!d.moved && Math.hypot(e.clientX - d.sx, e.clientY - d.sy) > 3) d.moved = true;
      if (!d.moved) return;
      if (d.kind === 'node') {
        const p = toWorld(e.clientX, e.clientY);
        const n = props.current.nodes[d.idx];
        n.x = p.x - d.dx;
        n.y = p.y - d.dy;
        hover.current = d.idx;
      } else {
        cam.current.tx = d.tx + (e.clientX - d.sx);
        cam.current.ty = d.ty + (e.clientY - d.sy);
      }
      canvas.style.cursor = 'grabbing';
      requestDraw();
      return;
    }
    const p = toWorld(e.clientX, e.clientY);
    const hit = hitTest(p.x, p.y);
    if (hit !== hover.current) {
      hover.current = hit;
      requestDraw();
    }
    canvas.style.cursor = hit != null ? 'pointer' : 'grab';
    if (hit != null) {
      const n = props.current.nodes[hit];
      const onScreen = W * (n.hub ? HUB_SCALE : 1) * cam.current.k;
      if (onScreen < 160) preview.show(n.card, e);
      else preview.hide();
    } else preview.hide();
  };

  const onPointerUp = (e: React.PointerEvent) => {
    const d = drag.current;
    drag.current = null;
    canvasRef.current!.style.cursor = 'grab';
    if (!d) return;
    if (d.kind === 'node') {
      if (d.moved) onMoved();
      else onSelect(props.current.nodes[d.idx].card);
    } else if (!d.moved) {
      onSelect(null);
    }
    void e;
  };

  const onPointerLeave = () => {
    if (!drag.current && hover.current != null) {
      hover.current = null;
      requestDraw();
    }
    preview.hide();
  };

  // Wheel zoom around the cursor (non-passive so we can preventDefault page scroll).
  useEffect(() => {
    const canvas = canvasRef.current!;
    const onWheel = (e: WheelEvent) => {
      e.preventDefault();
      preview.hide();
      const r = canvas.getBoundingClientRect();
      const mx = e.clientX - r.left;
      const my = e.clientY - r.top;
      const c = cam.current;
      const k = Math.min(6, Math.max(0.01, c.k * Math.exp(-e.deltaY * 0.0015)));
      c.tx = mx - ((mx - c.tx) * k) / c.k;
      c.ty = my - ((my - c.ty) * k) / c.k;
      c.k = k;
      requestDraw();
    };
    canvas.addEventListener('wheel', onWheel, { passive: false });
    return () => canvas.removeEventListener('wheel', onWheel);
  }, [preview, requestDraw]);

  return (
    <canvas
      ref={canvasRef}
      className="graph-canvas"
      onPointerDown={onPointerDown}
      onPointerMove={onPointerMove}
      onPointerUp={onPointerUp}
      onPointerCancel={onPointerUp}
      onPointerLeave={onPointerLeave}
      onDoubleClick={(e) => {
        const p = toWorld(e.clientX, e.clientY);
        if (hitTest(p.x, p.y) == null) fit();
      }}
    />
  );
}
