import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState, type ReactNode } from 'react';
import type { Card } from '../types';

interface PreviewApi {
  show: (card: Card, e: { clientX: number; clientY: number }) => void;
  hide: () => void;
  /** Suppress previews (e.g. while dragging). */
  suppress: (on: boolean) => void;
}

const Ctx = createContext<PreviewApi>({ show: () => {}, hide: () => {}, suppress: () => {} });

export const usePreview = () => useContext(Ctx);

const W = 250;
const H = 349;

export function PreviewProvider({ children }: { children: ReactNode }) {
  const [state, setState] = useState<{ src: string; x: number; y: number } | null>(null);
  const suppressed = useRef(false);

  const show = useCallback((card: Card, e: { clientX: number; clientY: number }) => {
    if (suppressed.current || !card.image_normal) return;
    const x = e.clientX + 24 + W > window.innerWidth ? e.clientX - 24 - W : e.clientX + 24;
    const y = Math.max(8, Math.min(e.clientY - 60, window.innerHeight - H - 8));
    setState({ src: card.image_normal, x, y });
  }, []);
  const hide = useCallback(() => setState(null), []);
  const suppress = useCallback((on: boolean) => {
    suppressed.current = on;
    if (on) setState(null);
  }, []);
  const value = useMemo(() => ({ show, hide, suppress }), [show, hide, suppress]);

  // If the hovered element unmounts (view switch, filter), mouseleave never fires;
  // hide on any click/scroll/key so a preview can't get stuck on screen.
  useEffect(() => {
    if (!state) return;
    const off = () => setState(null);
    window.addEventListener('mousedown', off, true);
    window.addEventListener('scroll', off, true);
    window.addEventListener('keydown', off, true);
    return () => {
      window.removeEventListener('mousedown', off, true);
      window.removeEventListener('scroll', off, true);
      window.removeEventListener('keydown', off, true);
    };
  }, [state]);

  return (
    <Ctx.Provider value={value}>
      {children}
      {state && (
        <img className="hover-preview" src={state.src} alt="" style={{ left: state.x, top: state.y, width: W }} />
      )}
    </Ctx.Provider>
  );
}
