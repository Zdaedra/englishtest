import { useEffect, useRef, useState } from "react";
import { api } from "../api";
import { useAuth } from "../auth/AuthContext";
import { useI18n } from "../i18n";

// Cover-art protagonist: male (v2 back) | female (v3 back) | mixed (alternate).
const OPTS = [
  { code: "male", glyph: "♂" },
  { code: "female", glyph: "♀" },
  { code: "mixed", glyph: "⚥" },
] as const;

/** Compact protagonist-gender switcher (mirrors LangSwitcher). Persists to the
 *  account and refreshes the user, so batch covers pick up the new variant on
 *  the next library/practice load. Reuses the `.lang-switch` popover styles. */
export default function HeroGenderSwitcher() {
  const { user, refresh } = useAuth();
  const { t } = useI18n();
  const [open, setOpen] = useState(false);
  const [busy, setBusy] = useState(false);
  const ref = useRef<HTMLDivElement>(null);
  const cur = (user?.hero_gender as string) || "male";
  const current = OPTS.find((o) => o.code === cur) ?? OPTS[0];

  useEffect(() => {
    if (!open) return;
    const onDoc = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
    };
    document.addEventListener("pointerdown", onDoc);
    return () => document.removeEventListener("pointerdown", onDoc);
  }, [open]);

  const pick = async (code: string) => {
    setOpen(false);
    if (code === cur) return;
    setBusy(true);
    await api.setHeroGender(code);
    await refresh();            // re-fetch /me so covers + this label update
    setBusy(false);
  };

  return (
    <div className="lang-switch lang-switch-pill" ref={ref}>
      <button type="button" className="lang-btn" onClick={() => setOpen((v) => !v)}
        aria-haspopup="listbox" aria-expanded={open} disabled={busy}>
        <span className="lang-globe" aria-hidden>{current.glyph}</span>
      </button>
      {open && (
        <ul className="lang-menu" role="listbox">
          {OPTS.map((o) => (
            <li key={o.code}>
              <button type="button" role="option" aria-selected={o.code === cur}
                className={`lang-opt${o.code === cur ? " on" : ""}`}
                onClick={() => pick(o.code)}>
                <span className="lang-flag" aria-hidden>{o.glyph}</span>
                <span className="lang-name">{t(`gender.${o.code}`)}</span>
                {o.code === cur && <span className="lang-check" aria-hidden>✓</span>}
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
