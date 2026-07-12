import { createContext, useCallback, useContext, useRef, useState, type ReactNode } from "react";
import { useAuth } from "../auth/AuthContext";
import { useI18n } from "../i18n";

// Lightweight contextual hints — the second tutorial layer next to the heavyweight
// coach-marks. A component calls `tip(key)` the FIRST TIME a state/event occurs
// (first score, first refresh session, …) and a one-line bubble appears, then never
// again (fire-once per key per user). This is how the method gets explained broadly
// WITHOUT more dimming overlays — see TZ-tutorial-backlog.md / the onboarding consilium.

const seenKey = (uid: string | number, key: string) => `ee-tip-${key}-${uid}`;

function tipSeen(uid: string | number | undefined, key: string): boolean {
  if (uid == null) return true;
  try { return localStorage.getItem(seenKey(uid, key)) === "1"; } catch { return true; }
}
function markTipSeen(uid: string | number, key: string): void {
  try { localStorage.setItem(seenKey(uid, key), "1"); } catch { /* noop */ }
}

// All known tip keys (for the "replay tutorial" reset).
export const TIP_KEYS = ["cue", "meaning", "spacing", "refresh", "exam", "calib", "rings"];
export function resetTips(uid: string | number): void {
  try { TIP_KEYS.forEach((k) => localStorage.removeItem(seenKey(uid, k))); } catch { /* noop */ }
}

type Ctx = { tip: (key: string) => void };
const TeachCtx = createContext<Ctx>({ tip: () => {} });
export const useTeach = () => useContext(TeachCtx);

export function TeachProvider({ children }: { children: ReactNode }) {
  const { user } = useAuth();
  const { t } = useI18n();
  const [active, setActive] = useState<string | null>(null);
  const activeRef = useRef<string | null>(null);
  const timer = useRef<number | undefined>(undefined);
  const uid = user?.id;

  const close = useCallback(() => {
    window.clearTimeout(timer.current);
    activeRef.current = null;
    setActive(null);
  }, []);

  const tip = useCallback((key: string) => {
    if (uid == null || activeRef.current || tipSeen(uid, key)) return;  // one at a time, once ever
    markTipSeen(uid, key);            // mark on show → never appears twice, even if dismissed instantly
    activeRef.current = key;
    setActive(key);
    window.clearTimeout(timer.current);
    timer.current = window.setTimeout(() => { activeRef.current = null; setActive(null); }, 6500);
  }, [uid]);

  return (
    <TeachCtx.Provider value={{ tip }}>
      {children}
      {active && (
        <div className="teach-tip" role="status" onClick={close}>
          <span className="teach-tip-text">{t(`tip.${active}`)}</span>
          <span className="teach-tip-x" aria-hidden>×</span>
        </div>
      )}
    </TeachCtx.Provider>
  );
}
