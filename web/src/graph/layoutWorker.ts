/// <reference lib="webworker" />
// Force-directed layout off the main thread (d3-force).
//
// Deterministic: d3-force v3 uses a seeded LCG and places nodes without x/y on a
// phyllotaxis spiral, so the same graph (same node order) always yields the same
// layout. That's what makes "Reset" return to the original arrangement.
//
// Nodes with a saved position are pinned (fx/fy); only new nodes move.
// Unconnected nodes skip the simulation and go on a sunflower ring outside it.

import {
  forceCollide,
  forceLink,
  forceManyBody,
  forceSimulation,
  forceX,
  forceY,
  type SimulationLinkDatum,
  type SimulationNodeDatum,
} from 'd3-force';

export interface LayoutRequest {
  // Connected nodes first, then unconnected ones in ring order (most popular first).
  nodes: { id: string; hub: boolean; fixed?: [number, number] }[];
  edges: { s: number; t: number; w: number }[]; // w normalized 0..1
}

export type LayoutMessage =
  | { type: 'progress'; done: number; total: number }
  | { type: 'done'; positions: Record<string, [number, number]> };

interface N extends SimulationNodeDatum {
  id: string;
  hub: boolean;
  i: number; // index into the request's nodes
}
interface L extends SimulationLinkDatum<N> {
  w: number;
}

const RING_GAP = 220;
const RING_CELL = 110 * 135; // world area per unconnected card

self.onmessage = (e: MessageEvent<LayoutRequest>) => {
  const { nodes, edges } = e.data;
  const degree = new Array(nodes.length).fill(0);
  for (const ed of edges) {
    degree[ed.s]++;
    degree[ed.t]++;
  }

  const sim: N[] = nodes.map((n, i) => {
    const d: N = { id: n.id, hub: n.hub, i };
    if (n.fixed) {
      d.x = d.fx = n.fixed[0];
      d.y = d.fy = n.fixed[1];
    }
    return d;
  });
  const connected = sim.filter((_, i) => degree[i] > 0);
  const unconnected = sim.filter((_, i) => degree[i] === 0);

  const needsSim = connected.some((n) => n.fx == null);
  if (needsSim) {
    const links: L[] = edges.map((ed) => ({ source: sim[ed.s], target: sim[ed.t], w: ed.w }));
    const simulation = forceSimulation(connected)
      .force(
        'link',
        forceLink<N, L>(links)
          .distance((l) => 90 + (1 - l.w) * 260)
          .strength((l) => (0.25 + 0.75 * l.w) / Math.min(degree[(l.source as N).i], degree[(l.target as N).i])),
      )
      .force('charge', forceManyBody<N>().strength((n) => (n.hub ? -900 : -260)).theta(0.9).distanceMax(2500))
      .force('collide', forceCollide<N>((n) => (n.hub ? 95 : 58)).strength(0.8))
      .force('x', forceX<N>(0).strength(0.03))
      .force('y', forceY<N>(0).strength(0.03))
      .stop();

    const total = Math.ceil(Math.log(simulation.alphaMin()) / Math.log(1 - simulation.alphaDecay()));
    for (let i = 0; i < total; i++) {
      simulation.tick();
      if (i % 10 === 0) (self as unknown as Worker).postMessage({ type: 'progress', done: i, total } satisfies LayoutMessage);
    }
  }

  // Sunflower ring for unconnected cards, outside the connected graph.
  let cx = 0;
  let cy = 0;
  if (connected.length) {
    for (const n of connected) {
      cx += n.x!;
      cy += n.y!;
    }
    cx /= connected.length;
    cy /= connected.length;
  }
  let R = 0;
  for (const n of connected) R = Math.max(R, Math.hypot(n.x! - cx, n.y! - cy));
  R = connected.length ? R + RING_GAP : 0;
  const golden = Math.PI * (3 - Math.sqrt(5));
  let i = 0;
  for (const n of unconnected) {
    if (n.fx != null) continue;
    const r = Math.sqrt(R * R + (i * RING_CELL) / Math.PI);
    n.x = cx + r * Math.cos(i * golden);
    n.y = cy + r * Math.sin(i * golden);
    i++;
  }

  const positions: Record<string, [number, number]> = {};
  for (const n of sim) positions[n.id] = [Math.round(n.x! * 10) / 10, Math.round(n.y! * 10) / 10];
  (self as unknown as Worker).postMessage({ type: 'done', positions } satisfies LayoutMessage);
};
