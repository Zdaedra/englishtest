// Lock-screen widget data feed (native iOS only). The widget extension has no
// auth and no network: the app drops the current study set into the shared
// App-Group container via the WidgetBridge plugin (ios/App/App/WidgetBridge.swift)
// and WidgetKit rebuilds its rotation timeline from it.
import { registerPlugin } from "@capacitor/core";
import { api, BattleItem } from "../api";
import { isNative } from "./session";

interface WidgetBridgePlugin {
  // `due` = total count of phrases slipping now (the widget shows "N к освежению");
  // each phrase carries d:1 when it is itself due (the widget marks/leads them).
  update(opts: { phrases: { en: string; ru: string; b: number; d?: number }[]; due?: number }): Promise<{ count: number }>;
}
const WidgetBridge = registerPlugin<WidgetBridgePlugin>("WidgetBridge");

const MAX = 40;
const LEARNED = new Set(["familiar", "automatic"]);

// Rotation set = the user's study corpus, learned/touched first (the corpus
// already arrives learned-first from /api/battle/corpus). Within that, DUE
// phrases (SRS says they're slipping) lead the rotation — the lock screen should
// surface exactly what's about to be forgotten. Each carries d:1 so the widget
// can mark it.
function pick(items: BattleItem[]) {
  const touched = items.filter((i) => LEARNED.has(i.srs_status) || i.attempts > 0);
  const pool = touched.length >= 5 ? touched : items;
  const ordered = [...pool].sort((a, b) => Number(!!b.due) - Number(!!a.due)); // due first, else stable
  return ordered.slice(0, MAX).map((i) => ({
    en: i.phrase_en,
    ru: i.gloss_ru || i.anchor,
    b: i.batch_id,
    d: i.due ? 1 : 0,
  }));
}

let last = "";

/** Push the freshest study set to the widget. Call on launch/foreground and
 *  whenever the corpus is already in hand (Battle screen). Fire-and-forget. */
export async function syncWidget(items?: BattleItem[]): Promise<void> {
  if (!isNative()) return;
  try {
    const corpus = items ?? (await api.battleCorpus());
    const phrases = pick(corpus);
    const due = corpus.reduce((n, i) => n + (i.due ? 1 : 0), 0);
    const sig = JSON.stringify({ phrases, due });
    if (sig === last) return;          // unchanged → don't churn WidgetKit
    last = sig;
    await WidgetBridge.update({ phrases, due });
  } catch {
    /* widget feed is best-effort — never surface errors into the app */
  }
}

/** Wipe the widget on logout/account-deletion — the App-Group container keeps
 *  the last push forever otherwise, leaving the previous account's phrases on
 *  the lock screen. Also drops the dedup signature so the next login's sync
 *  always writes through. */
export async function clearWidget(): Promise<void> {
  if (!isNative()) return;
  last = "";
  try { await WidgetBridge.update({ phrases: [], due: 0 }); } catch { /* best-effort */ }
}
