import { SpeechRecognition } from "@capacitor-community/speech-recognition";
import { isNative } from "../lib/session";

// On-device speech-to-text on native iOS via SFSpeechRecognizer (free, private,
// low-latency — the audio never leaves the phone, no server STT cost). Used only
// for single-locale utterances; the mixed RU+EN sequence exam stays on the server
// path. Callers fall back (server STT / typed input) when this is unavailable or
// permission is denied.
//
// Hard-won rules (the Live-mic freeze saga):
// - STATIC import. The old dynamic import() was the only await before the stop
//   watchdog armed — if the chunk load wedged, the UI froze with no way out.
// - Plugin contract (@capacitor-community/speech-recognition 6.x, Plugin.swift):
//   partialResults=false (one-shot): start() resolves WITH the matches at the
//   END of recognition. partialResults=true (live transcript): start() resolves
//   IMMEDIATELY — the END is the listeningState:"stopped" event.
// - Every quick native call is wrapped in a timeout: a wedged bridge call must
//   surface as an error (caller shows "недоступно"), never as a frozen UI.
type ListenerHandle = { remove: () => Promise<void> };
type SR = {
  available(): Promise<{ available: boolean }>;
  checkPermissions(): Promise<{ speechRecognition: string }>;
  requestPermissions(): Promise<{ speechRecognition: string }>;
  start(opts: {
    language?: string; maxResults?: number; partialResults?: boolean; popup?: boolean;
  }): Promise<{ matches?: string[] } | void>;
  stop(): Promise<void>;
  addListener(
    event: "partialResults" | "listeningState",
    cb: (data: { matches?: string[]; status?: string }) => void,
  ): Promise<ListenerHandle>;
};

const lg = (...a: unknown[]) => console.log("[LV:stt]", ...a);

function plugin(): SR | null {
  return isNative() ? (SpeechRecognition as unknown as SR) : null;
}

const delay = (ms: number) => new Promise<void>((r) => window.setTimeout(r, ms));

function withTimeout<T>(p: Promise<T>, ms: number, tag: string): Promise<T> {
  return new Promise<T>((res, rej) => {
    const tm = window.setTimeout(() => rej(new Error(`native-stt-timeout:${tag}`)), ms);
    p.then((v) => { window.clearTimeout(tm); res(v); },
           (e) => { window.clearTimeout(tm); rej(e); });
  });
}

// Resolves the in-flight live-transcript session (tap-to-stop / stopped event).
let _finish: (() => void) | null = null;

/** True on native iOS (the plugin is statically bundled and native-registered).
 *  Deliberately NOT the plugin's available() probe: that checks the DEVICE-LOCALE
 *  recognizer and false-negatives when the requested language works fine. */
export async function nativeSttAvailable(): Promise<boolean> {
  return plugin() !== null;
}

/** One-shot recognition. Resolves with the transcript (may be ""). Throws if the
 *  recognizer is unavailable or permission is denied — the caller then falls back. */
export async function nativeRecognize(
  language = "en-US",
  onPartial?: (t: string) => void,
): Promise<string> {
  const sr = plugin();
  if (!sr) throw new Error("native-stt-unavailable");
  let perm = await withTimeout(sr.checkPermissions(), 4000, "checkPermissions");
  lg("perm", perm.speechRecognition);
  // No timeout on requestPermissions — it can sit under the system dialog.
  if (perm.speechRecognition !== "granted") perm = await sr.requestPermissions();
  if (perm.speechRecognition !== "granted") throw new Error("native-stt-denied");

  // One-shot mode (no live transcript): start() IS the whole session.
  if (!onPartial) {
    lg("one-shot start", language);
    const res = await sr.start({ language, maxResults: 1, partialResults: false, popup: false });
    lg("one-shot done");
    return ((res && res.matches?.[0]) || "").trim();
  }

  // Live-transcript mode: collect partials, then wait for the real end of the
  // session — listeningState:"stopped", nativeSttStop() (tap-to-stop) or a hard
  // cap — give the recognizer a short grace so the final (fullest) partial
  // lands, and return the last one.
  let last = "";
  let partial: ListenerHandle | undefined;
  let state: ListenerHandle | undefined;
  try {
    const done = new Promise<void>((resolve) => { _finish = resolve; });
    partial = await withTimeout(sr.addListener("partialResults", (d) => {
      const m = (d?.matches?.[0] || "").trim();
      if (m) { last = m; onPartial(m); }
    }), 4000, "addListener:partial");
    state = await withTimeout(sr.addListener("listeningState", (d) => {
      lg("listeningState", d?.status);
      if (d?.status === "stopped") _finish?.();
    }), 4000, "addListener:state");
    lg("live start", language);
    await withTimeout(
      sr.start({ language, maxResults: 1, partialResults: true, popup: false }),
      6000, "start",
    );
    lg("live started, waiting for stop");
    await Promise.race([done, delay(45_000)]);   // stop tap / auto-final / cap
    await delay(400);                            // let the final partial land
    lg("live done:", JSON.stringify(last));
    return last.trim();
  } finally {
    _finish = null;
    try { await partial?.remove(); } catch { /* noop */ }
    try { await state?.remove(); } catch { /* noop */ }
    try { void sr.stop(); } catch { /* noop */ }  // cap/edge: engine must die
  }
}

/** Finalize an in-flight recognition (tap-to-stop) — ends the session in BOTH
 *  modes: one-shot resolves via the plugin, live-transcript via _finish (the
 *  stopped event may race listener removal, so we also resolve locally). */
export async function nativeSttStop(): Promise<void> {
  lg("stop tap");
  const sr = plugin();
  try { await withTimeout(sr?.stop() ?? Promise.resolve(), 3000, "stop"); }
  catch (e) { lg("stop err", String(e)); }
  _finish?.();
}
