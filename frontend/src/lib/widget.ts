// Lock-screen widget data feed (native iOS only). The widget extension has no
// auth and no network: the app drops the current study set into the shared
// App-Group container via the WidgetBridge plugin (ios/App/App/WidgetBridge.swift)
// and WidgetKit rebuilds its rotation timeline from it.
import { registerPlugin } from "@capacitor/core";
import { api, BattleItem } from "../api";
import { isNative } from "./session";

interface WidgetBridgePlugin {
  update(opts: { phrases: { en: string; ru: string; b: number }[] }): Promise<{ count: number }>;
}
const WidgetBridge = registerPlugin<WidgetBridgePlugin>("WidgetBridge");

const MAX = 40;
const LEARNED = new Set(["familiar", "automatic"]);

// Rotation set = the user's study corpus, learned/touched first (the corpus
// already arrives learned-first from /api/battle/corpus — keep its order).
function pick(items: BattleItem[]) {
  const touched = items.filter((i) => LEARNED.has(i.srs_status) || i.attempts > 0);
  const pool = touched.length >= 5 ? touched : items;
  return pool.slice(0, MAX).map((i) => ({
    en: i.phrase_en,
    ru: i.gloss_ru || i.anchor,
    b: i.batch_id,
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
    const sig = JSON.stringify(phrases);
    if (sig === last) return;          // unchanged → don't churn WidgetKit
    last = sig;
    await WidgetBridge.update({ phrases });
  } catch {
    /* widget feed is best-effort — never surface errors into the app */
  }
}
