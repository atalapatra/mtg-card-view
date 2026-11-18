import { useCallback, useRef, useState } from 'react';

/** A panel width (px) remembered in localStorage. Writes happen via `commit` (drag end), not on every move. */
export function useStoredWidth(
  key: string,
  initial: number,
): [number, (w: number) => void, (w: number) => void] {
  const storageKey = `mtgcv.width.${key}`;
  const [width, setWidth] = useState(() => {
    try {
      const v = Number(localStorage.getItem(storageKey));
      return Number.isFinite(v) && v > 0 ? v : initial;
    } catch {
      return initial;
    }
  });
  const commit = useCallback(
    (w: number) => {
      setWidth(w);
      try {
        localStorage.setItem(storageKey, String(Math.round(w)));
      } catch {
        /* storage unavailable */
      }
    },
    [storageKey],
  );
  return [width, setWidth, commit];
}

interface Props {
  /** Which panel this handle resizes: the left one grows when dragged right, the right one when dragged left. */
  side: 'left' | 'right';
  width: number;
  min: number;
  /** Upper bound; recomputed at drag start so the main area keeps some room. */
  max: () => number;
  defaultWidth: number;
  onChange: (w: number) => void;
  onCommit: (w: number) => void;
  label: string;
}

/**
 * Vertical drag handle sitting on a panel's inner edge (position comes from the caller's CSS).
 * Drag to resize, double-click to restore the default width, arrow keys for keyboard users.
 */
export function Resizer({ side, width, min, max, defaultWidth, onChange, onCommit, label }: Props) {
  const drag = useRef<{ x: number; w: number; max: number; last: number } | null>(null);
  const clamp = (w: number, hi: number) => Math.round(Math.max(min, Math.min(Math.max(min, hi), w)));

  const onPointerDown = (e: React.PointerEvent<HTMLDivElement>) => {
    if (e.button !== 0) return;
    e.preventDefault();
    e.currentTarget.setPointerCapture(e.pointerId);
    drag.current = { x: e.clientX, w: width, max: max(), last: width };
    document.body.classList.add('resizing');
  };
  const onPointerMove = (e: React.PointerEvent) => {
    const d = drag.current;
    if (!d) return;
    const dx = e.clientX - d.x;
    d.last = clamp(side === 'left' ? d.w + dx : d.w - dx, d.max);
    onChange(d.last);
  };
  const end = () => {
    const d = drag.current;
    if (!d) return;
    drag.current = null;
    document.body.classList.remove('resizing');
    onCommit(d.last);
  };
  const onKeyDown = (e: React.KeyboardEvent) => {
    const step = e.shiftKey ? 50 : 10;
    const grow = side === 'left' ? 'ArrowRight' : 'ArrowLeft';
    const shrink = side === 'left' ? 'ArrowLeft' : 'ArrowRight';
    if (e.key !== grow && e.key !== shrink) return;
    e.preventDefault();
    onCommit(clamp(width + (e.key === grow ? step : -step), max()));
  };

  return (
    <div
      className={`resizer resizer-${side}`}
      role="separator"
      aria-orientation="vertical"
      aria-label={label}
      aria-valuenow={Math.round(width)}
      aria-valuemin={min}
      tabIndex={0}
      title="Drag to resize · double-click to reset"
      onPointerDown={onPointerDown}
      onPointerMove={onPointerMove}
      onPointerUp={end}
      onPointerCancel={end}
      onDoubleClick={() => onCommit(clamp(defaultWidth, max()))}
      onKeyDown={onKeyDown}
    />
  );
}
