// A batch card rendered as a <button> with tap = open and long-press = context menu.
// One component instance per card (so useLongPress is a valid per-instance hook),
// which is how the long-press menu is applied across all batch surfaces without
// duplicating gesture logic. See TZ-batch-management.md §5.
import type { CSSProperties, ReactNode } from "react";
import { useNavigate } from "react-router-dom";
import { useLongPress } from "../lib/useLongPress";
import { useBatchMenu } from "./BatchMenu";

export function BatchTapButton({
  batchId, title, className, ariaLabel, style, children, onOpen,
}: {
  batchId: number;
  title: string;
  className?: string;
  ariaLabel?: string;
  style?: CSSProperties;
  children: ReactNode;
  onOpen?: () => void;   // defaults to navigating to the batch detail
}) {
  const nav = useNavigate();
  const { open } = useBatchMenu();
  const lp = useLongPress(() => open({ id: batchId, title }), {
    onClick: () => (onOpen ? onOpen() : nav(`/batch/${batchId}`)),
  });
  return (
    <button className={className} aria-label={ariaLabel} {...lp} style={{ ...lp.style, ...style }}>
      {children}
    </button>
  );
}
