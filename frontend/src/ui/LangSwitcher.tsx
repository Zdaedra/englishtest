import { useEffect, useRef, useState } from "react";
import { LANGS, useI18n } from "../i18n";

/** Compact globe switcher: button (🌐 + current code) → popover list of the 4 UI
 *  languages. Used on the pre-login screens (auth / onboarding) and in the cabinet. */
export default function LangSwitcher({ variant = "pill" }: { variant?: "pill" | "ghost" }) {
  const { lang, setLang } = useI18n();
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);
  const current = LANGS.find((l) => l.code === lang) ?? LANGS[0];

  useEffect(() => {
    if (!open) return;
    const onDoc = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
    };
    document.addEventListener("pointerdown", onDoc);
    return () => document.removeEventListener("pointerdown", onDoc);
  }, [open]);

  return (
    <div className={`lang-switch lang-switch-${variant}`} ref={ref}>
      <button type="button" className="lang-btn" onClick={() => setOpen((v) => !v)}
        aria-haspopup="listbox" aria-expanded={open}>
        <span className="lang-globe" aria-hidden>🌐</span>
        <span className="lang-code">{current.short}</span>
      </button>
      {open && (
        <ul className="lang-menu" role="listbox">
          {LANGS.map((l) => (
            <li key={l.code}>
              <button type="button" role="option" aria-selected={l.code === lang}
                className={`lang-opt${l.code === lang ? " on" : ""}`}
                onClick={() => { setLang(l.code); setOpen(false); }}>
                <span className="lang-flag" aria-hidden>{l.flag}</span>
                <span className="lang-name">{l.label}</span>
                {l.code === lang && <span className="lang-check" aria-hidden>✓</span>}
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
