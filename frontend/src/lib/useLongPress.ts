// iOS-style long-press (force-press) detection for batch cards. 500ms hold,
// cancelled if the finger moves >10px (so scroll/swipe wins). The click that
// follows a fired long-press is suppressed. Desktop right-click opens the menu too.
// Returns props to spread onto the card element; pass your normal tap as `onClick`.
import { useRef } from "react";
import type React from "react";
import { haptic } from "./session";

export type LongPressProps = {
  onPointerDown: (e: React.PointerEvent) => void;
  onPointerMove: (e: React.PointerEvent) => void;
  onPointerUp: () => void;
  onPointerLeave: () => void;
  onPointerCancel: () => void;
  onContextMenu: (e: React.MouseEvent) => void;
  onClick: (e: React.MouseEvent) => void;
  style: React.CSSProperties;
};

export function useLongPress(
  onLongPress: () => void,
  opts?: { onClick?: () => void; delay?: number; moveTolerance?: number },
): LongPressProps {
  const delay = opts?.delay ?? 500;
  const tol = opts?.moveTolerance ?? 10;
  const timer = useRef<number | null>(null);
  const start = useRef<{ x: number; y: number } | null>(null);
  const fired = useRef(false);

  const clear = () => {
    if (timer.current != null) { window.clearTimeout(timer.current); timer.current = null; }
    start.current = null;
  };

  const trigger = () => { fired.current = true; haptic("medium"); onLongPress(); };

  return {
    onPointerDown: (e) => {
      if (e.pointerType === "mouse" && e.button !== 0) return;
      fired.current = false;
      start.current = { x: e.clientX, y: e.clientY };
      timer.current = window.setTimeout(() => { timer.current = null; trigger(); }, delay);
    },
    onPointerMove: (e) => {
      if (!start.current) return;
      const dx = e.clientX - start.current.x, dy = e.clientY - start.current.y;
      if (dx * dx + dy * dy > tol * tol) clear();   // moved → scroll/swipe, not a long-press
    },
    onPointerUp: clear,
    onPointerLeave: clear,
    onPointerCancel: clear,
    onContextMenu: (e) => {                          // right-click / iOS callout
      e.preventDefault();
      if (!fired.current) trigger();
    },
    onClick: (e) => {
      if (fired.current) {                           // swallow the click after a long-press
        e.preventDefault(); e.stopPropagation();
        fired.current = false;
        return;
      }
      opts?.onClick?.();
    },
    // Kill the iOS text-selection / share callout on hold.
    style: { WebkitTouchCallout: "none", WebkitUserSelect: "none", userSelect: "none" },
  };
}
