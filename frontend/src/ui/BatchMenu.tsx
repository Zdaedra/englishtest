// Cross-cutting long-press batch menu: one provider + one bottom action-sheet used
// by every surface that lists batches (Library, Learning). A surface calls
// useBatchMenu().open({id,title}) from its useLongPress handler; the sheet's actions
// run through batchActions (optimistic + server + rollback). See TZ-batch-management.md.
import { createContext, useCallback, useContext, useEffect, useState } from "react";
import type { ReactNode } from "react";
import { useNavigate } from "react-router-dom";
import { useI18n } from "../i18n";
import { batchMenuItems, runBatchAction, MenuItem, BatchAction } from "../lib/batchActions";
import { FOCUS_CAP } from "../lib/progress";

type Target = { id: number; title: string };
const BatchMenuCtx = createContext<{ open: (b: Target) => void }>({ open: () => {} });
export function useBatchMenu() { return useContext(BatchMenuCtx); }

// Surfaces that render batch lists call this so they re-render after a menu action
// mutates progress (batchActions dispatches "ee-progress-changed").
export function useProgressVersion(): number {
  const [v, setV] = useState(0);
  useEffect(() => {
    const h = () => setV((x) => x + 1);
    window.addEventListener("ee-progress-changed", h);
    return () => window.removeEventListener("ee-progress-changed", h);
  }, []);
  return v;
}

export function BatchMenuProvider({ children }: { children: ReactNode }) {
  const { t } = useI18n();
  const nav = useNavigate();
  const [target, setTarget] = useState<Target | null>(null);
  const [items, setItems] = useState<MenuItem[]>([]);
  const [busy, setBusy] = useState(false);
  const [notice, setNotice] = useState("");

  const open = useCallback((b: Target) => { setItems(batchMenuItems(b.id)); setTarget(b); }, []);
  const close = () => { if (!busy) setTarget(null); };

  // Auto-dismiss the transient focus-full notice.
  useEffect(() => {
    if (!notice) return;
    const id = setTimeout(() => setNotice(""), 3200);
    return () => clearTimeout(id);
  }, [notice]);

  const onAction = async (action: BatchAction, disabled?: boolean) => {
    if (!target || busy) return;
    // A disabled "add to active" at the cap: explain, don't act or upsell.
    if (disabled) { setTarget(null); setNotice(t("focus.full.toast", { n: FOCUS_CAP })); return; }
    if (action === "open") { const id = target.id; setTarget(null); nav(`/batch/${id}`); return; }
    setBusy(true);
    const r = await runBatchAction(target.id, action);
    setBusy(false);
    setTarget(null);
    // Focus cap (pedagogical) → a "finish one first" nudge, NEVER an upsell.
    if (!r.ok && r.focusFull) setNotice(t("focus.full.toast", { n: FOCUS_CAP }));
    else if (!r.ok && r.locked) nav("/subscribe");   // freemium paywall → upsell
  };

  return (
    <BatchMenuCtx.Provider value={{ open }}>
      {children}
      {target && (
        <div className="bm-backdrop" onClick={close} role="presentation">
          <div className="bm-sheet" onClick={(e) => e.stopPropagation()} role="menu" aria-label={target.title}>
            <p className="bm-title">{target.title}</p>
            {items.map((it) => (
              <button key={it.action} role="menuitem" disabled={busy}
                className={`bm-item${it.destructive ? " danger" : ""}${it.disabled ? " bm-item-off" : ""}`}
                onClick={() => onAction(it.action, it.disabled)}>
                {t(it.labelKey)}
              </button>
            ))}
            <button className="bm-cancel" onClick={close} disabled={busy}>{t("batch.menu.cancel")}</button>
          </div>
        </div>
      )}
      {notice && <div className="bm-toast" role="status">{notice}</div>}
    </BatchMenuCtx.Provider>
  );
}
