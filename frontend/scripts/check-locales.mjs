#!/usr/bin/env node
// Locale consistency checker for frontend/src/i18n/locales/*.ts
//
// Run:  node frontend/scripts/check-locales.mjs
// Exit: 0 = all checks pass, 1 = problems found (printed, grouped by check).
//
// Russian (ru.ts) is the reference language: it defines the key set and the
// placeholder/token contract every other locale must mirror.
//
// Checks
//   1. key set       — identical keys everywhere, no missing / no extra
//   2. {{vars}}      — t() interpolation placeholders: same names, same counts
//   3. {tokens}      — tx() React-node slots: same names, same counts
//   4. cyrillic      — no untranslated Russian left in a non-ru locale
//   5. empty         — no blank values
//   6. echo          — no value that is just its own key
//
// The locale files are TypeScript, so we strip the two TS-only bits (`import
// type` + the `: Dict` annotation) and import the result as real ESM — that way
// the JS parser handles quoting/escapes instead of a fragile regex.

import { readFileSync, writeFileSync, mkdtempSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import { join, dirname } from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";

const HERE = dirname(fileURLToPath(import.meta.url));
const LOCALES_DIR = join(HERE, "..", "src", "i18n", "locales");
const REFERENCE = "ru";
const LANGS = ["ru", "en", "es", "de", "fr"];

async function loadLocale(lang, scratch) {
  const src = readFileSync(join(LOCALES_DIR, `${lang}.ts`), "utf8")
    .replace(/^\s*import\s+type\s+.*$/m, "")           // drop `import type { Dict }`
    .replace(/const\s+(\w+)\s*:\s*Dict\s*=/, "const $1 =");  // drop the type annotation
  const tmp = join(scratch, `${lang}.mjs`);
  writeFileSync(tmp, src);
  return (await import(pathToFileURL(tmp).href)).default;
}

// Multiset of placeholder/token names, e.g. {a:2, b:1}, so a *count* change is
// caught too (a string that uses {{n}} twice must use it twice in every locale).
function marks(str, re) {
  const out = {};
  for (const m of str.matchAll(re)) out[m[1]] = (out[m[1]] || 0) + 1;
  return out;
}
const vars   = (s) => marks(s, /\{\{(\w+)\}\}/g);   // t()  → "{{n}}"
const tokens = (s) => marks(s, /(?<!\{)\{(\w+)\}(?!\})/g); // tx() → "{b}" (not "{{n}}")
const fmt = (m) => Object.entries(m).sort().map(([k, n]) => (n > 1 ? `${k}×${n}` : k)).join(",") || "—";
const same = (a, b) => fmt(a) === fmt(b);

const CYRILLIC = /[Ѐ-ӿ]/;

const scratch = mkdtempSync(join(tmpdir(), "locale-check-"));
let dicts;
try {
  dicts = Object.fromEntries(
    await Promise.all(LANGS.map(async (l) => [l, await loadLocale(l, scratch)])),
  );
} finally {
  rmSync(scratch, { recursive: true, force: true });
}

const ref = dicts[REFERENCE];
const refKeys = Object.keys(ref);
const problems = [];
const add = (check, lang, key, detail) => problems.push({ check, lang, key, detail });

for (const lang of LANGS) {
  const d = dicts[lang];
  const keys = new Set(Object.keys(d));

  // 1. key set
  for (const k of refKeys) if (!keys.has(k)) add("key set", lang, k, "missing");
  for (const k of keys) if (!(k in ref)) add("key set", lang, k, "extra (not in ru)");

  for (const [k, v] of Object.entries(d)) {
    if (typeof v !== "string") { add("type", lang, k, `not a string (${typeof v})`); continue; }

    // 5. empty  /  6. echo
    if (!v.trim()) add("empty", lang, k, "blank value");
    if (v.trim() === k) add("echo", lang, k, "value equals the key");

    // 4. cyrillic (ru is the source, so it is exempt)
    if (lang !== REFERENCE && CYRILLIC.test(v)) {
      add("cyrillic", lang, k, `untranslated: ${JSON.stringify(v.slice(0, 60))}`);
    }

    // 2. {{vars}}  /  3. {tokens}
    if (k in ref && lang !== REFERENCE) {
      if (!same(vars(v), vars(ref[k]))) {
        add("{{vars}}", lang, k, `ru has [${fmt(vars(ref[k]))}], ${lang} has [${fmt(vars(v))}]`);
      }
      if (!same(tokens(v), tokens(ref[k]))) {
        add("{tokens}", lang, k, `ru has [${fmt(tokens(ref[k]))}], ${lang} has [${fmt(tokens(v))}]`);
      }
    }
  }
}

// ── report ────────────────────────────────────────────────────────────
console.log(`locales: ${LANGS.join(", ")}   reference: ${REFERENCE}`);
for (const lang of LANGS) {
  console.log(`  ${lang}.ts — ${Object.keys(dicts[lang]).length} keys`);
}
console.log("");

const CHECKS = ["key set", "type", "{{vars}}", "{tokens}", "cyrillic", "empty", "echo"];
for (const check of CHECKS) {
  const hits = problems.filter((p) => p.check === check);
  if (!hits.length) { console.log(`  OK   ${check}`); continue; }
  console.log(`  FAIL ${check} — ${hits.length}`);
  for (const h of hits) console.log(`         ${h.lang}  ${h.key}  ${h.detail}`);
}

console.log("");
if (problems.length) {
  console.log(`${problems.length} problem(s) found.`);
  process.exit(1);
}
console.log(`All checks pass across ${LANGS.length} locales × ${refKeys.length} keys.`);
