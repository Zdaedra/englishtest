// Lightweight, dependency-free i18n for the whole UI.
//
// Why custom (not react-i18next): the app intentionally ships almost no deps
// (react + router only). This module is ~80 lines, tree-shakes to nothing, and
// gives us exactly what we need — string interpolation plus `tx()` for strings
// that embed the *English being learned* (anchor words like UNDERSTAND/WALK)
// as immutable React nodes that must NOT be translated.
//
// Rule of the whole codebase: everything the user reads is a t()/tx() key EXCEPT
// the English learning content (anchor words, example sentences, batch phrases).
import {
  createContext, useCallback, useContext, useEffect, useMemo, useState,
  Fragment, type ReactNode,
} from "react";
import ru from "./locales/ru";
import es from "./locales/es";
import de from "./locales/de";
import fr from "./locales/fr";

export type Lang = "ru" | "es" | "de" | "fr";
export type Dict = Record<string, string>;

export const LANGS: { code: Lang; label: string; short: string; flag: string }[] = [
  { code: "ru", label: "Русский",  short: "RU", flag: "🇷🇺" },
  { code: "es", label: "Español",  short: "ES", flag: "🇪🇸" },
  { code: "de", label: "Deutsch",  short: "DE", flag: "🇩🇪" },
  { code: "fr", label: "Français", short: "FR", flag: "🇫🇷" },
];

const DICTS: Record<Lang, Dict> = { ru, es, de, fr };
const STORAGE_KEY = "ee-lang";

export function detectLang(): Lang {
  try {
    const saved = localStorage.getItem(STORAGE_KEY);
    if (saved && saved in DICTS) return saved as Lang;
  } catch { /* private mode */ }
  try {
    const nav = (navigator.language || "ru").slice(0, 2).toLowerCase();
    if (nav in DICTS) return nav as Lang;
  } catch { /* no navigator */ }
  return "ru";
}

function interpolate(s: string, vars?: Record<string, string | number>): string {
  if (!vars) return s;
  return s.replace(/\{\{(\w+)\}\}/g, (_, k) => (k in vars ? String(vars[k]) : `{{${k}}}`));
}

// Module-level mirror of the active language, kept in sync by <I18nProvider>.
// Lets non-React code (lib/*.ts helpers, plain modules) translate via tg() without
// a hook. Components should still use useI18n() so they re-render on change.
let currentLang: Lang = "ru";
try { currentLang = detectLang(); } catch { /* ssr */ }
export function getLang(): Lang { return currentLang; }
export function tg(key: string, vars?: Record<string, string | number>): string {
  const s = DICTS[currentLang][key] ?? ru[key] ?? key;
  return interpolate(s, vars);
}

type Ctx = {
  lang: Lang;
  setLang: (l: Lang, opts?: SetLangOpts) => void;
  /** Plain string lookup with optional {{var}} interpolation. Falls back to ru, then the key. */
  t: (key: string, vars?: Record<string, string | number>) => string;
  /** Lookup that splits on {token} and substitutes React nodes — for strings that
   *  embed the English-being-learned (anchors) or inline markup that must stay put. */
  tx: (key: string, nodes: Record<string, ReactNode>) => ReactNode;
};

export type SetLangOpts = { sync?: boolean };

const I18nContext = createContext<Ctx | null>(null);

export function I18nProvider({ children }: { children: ReactNode }) {
  const [lang, setLangState] = useState<Lang>(detectLang);

  currentLang = lang; // keep the module mirror in sync for tg()/getLang()
  useEffect(() => { try { document.documentElement.lang = lang; } catch { /* ssr */ } }, [lang]);

  const setLang = useCallback((l: Lang, opts?: SetLangOpts) => {
    setLangState(l);
    try { localStorage.setItem(STORAGE_KEY, l); } catch { /* private mode */ }
    // Best-effort cross-device sync; skipped when applying a value that just came
    // FROM the server (opts.sync === false), and silently ignored when logged out.
    if (opts?.sync !== false) {
      import("../api").then((m) => (m as any).api?.setUiLang?.(l)).catch(() => {});
    }
  }, []);

  const t = useCallback((key: string, vars?: Record<string, string | number>) => {
    const s = DICTS[lang][key] ?? ru[key] ?? key;
    return interpolate(s, vars);
  }, [lang]);

  const tx = useCallback((key: string, nodes: Record<string, ReactNode>): ReactNode => {
    const s = DICTS[lang][key] ?? ru[key] ?? key;
    // odd indices are token names captured by the group
    const parts = s.split(/\{(\w+)\}/g);
    return parts.map((p, i) =>
      i % 2 === 1
        ? <Fragment key={i}>{p in nodes ? nodes[p] : `{${p}}`}</Fragment>
        : <Fragment key={i}>{p}</Fragment>
    );
  }, [lang]);

  const value = useMemo<Ctx>(() => ({ lang, setLang, t, tx }), [lang, setLang, t, tx]);
  return <I18nContext.Provider value={value}>{children}</I18nContext.Provider>;
}

export function useI18n(): Ctx {
  const c = useContext(I18nContext);
  if (!c) throw new Error("useI18n must be used within <I18nProvider>");
  return c;
}
