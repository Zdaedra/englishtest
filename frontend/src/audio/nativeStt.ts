import { isNative } from "../lib/session";

// On-device speech-to-text on native iOS via SFSpeechRecognizer (free, private,
// low-latency — the audio never leaves the phone, no server STT cost). Used only
// for single-locale utterances; the mixed RU+EN sequence exam stays on the server
// path. Callers fall back (server STT / typed input) when this is unavailable or
// permission is denied.
//
// ⚠️ Plugin contract (@capacitor-community/speech-recognition 6.x, Plugin.swift):
// - partialResults=false (one-shot): start() resolves WITH the matches when the
//   recognizer finalizes (silence timeout or stop()). Training/Arena/League path.
// - partialResults=true (live transcript): start() resolves IMMEDIATELY after the
//   audio engine starts — its resolve is NOT the end of the session! Partials
//   stream as "partialResults" events (the final, fullest one included), and the
//   END is signaled by listeningState:"stopped" (isFinal / error / stop()).
//   Treating start()'s resolve as the finish is what froze the Live mic.
type ListenerHandle = { remove: () => Promise<void> };
type SR = {
  available(): Promise<{ available: boolean }>;
  checkPermissions(): Promise<{ speechRecognition: string }>;
  requestPermissions(): Promise<{ speechRecognition: string }>;
  start(opts: {
    language?: string; maxResults?: number; partialResults?: boolean; popup?: boolean;
  }): Promise<{ matches?: string[] } | void>;
  stop(): Promise<void>;
  addListener?(
    event: "partialResults" | "listeningState",
    cb: (data: { matches?: string[]; status?: string }) => void,
  ): Promise<ListenerHandle>;
};

let _sr: SR | null | undefined;

async function plugin(): Promise<SR | null> {
  if (_sr !== undefined) return _sr;
  if (!isNative()) { _sr = null; return _sr; }
  try {
    const mod = await import("@capacitor-community/speech-recognition");
    _sr = (mod as { SpeechRecognition: SR }).SpeechRecognition;
  } catch { _sr = null; }
  return _sr;
}

const delay = (ms: number) => new Promise<void>((r) => window.setTimeout(r, ms));

// Resolves the in-flight live-transcript session (tap-to-stop / stopped event).
let _finish: (() => void) | null = null;

/** True on native iOS with the recognizer plugin present. Deliberately NOT the
 *  plugin's available() probe: that checks the DEVICE-LOCALE recognizer and
 *  false-negatives on phones whose system locale has no on-device model even
 *  when the requested language (en-US/ru-RU) works fine. A truly dead recognizer
 *  just ends the session with an empty transcript / a thrown start(). */
export async function nativeSttAvailable(): Promise<boolean> {
  return (await plugin()) !== null;
}

/** One-shot recognition. Resolves with the transcript (may be ""). Throws if the
 *  recognizer is unavailable or permission is denied — the caller then falls back. */
export async function nativeRecognize(
  language = "en-US",
  onPartial?: (t: string) => void,
): Promise<string> {
  const sr = await plugin();
  if (!sr) throw new Error("native-stt-unavailable");
  let perm = await sr.checkPermissions();
  if (perm.speechRecognition !== "granted") perm = await sr.requestPermissions();
  if (perm.speechRecognition !== "granted") throw new Error("native-stt-denied");

  // One-shot mode (no live transcript): start() IS the whole session.
  if (!(onPartial && sr.addListener)) {
    const res = await sr.start({ language, maxResults: 1, partialResults: false, popup: false });
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
    partial = await sr.addListener("partialResults", (d) => {
      const m = (d?.matches?.[0] || "").trim();
      if (m) { last = m; onPartial(m); }
    });
    try {
      state = await sr.addListener("listeningState", (d) => {
        if (d?.status === "stopped") _finish?.();
      });
    } catch { /* older builds: tap-to-stop / the cap still end the session */ }
    await sr.start({ language, maxResults: 1, partialResults: true, popup: false });
    await Promise.race([done, delay(45_000)]);   // stop tap / auto-final / cap
    await delay(400);                            // let the final partial land
    return last.trim();
  } finally {
    _finish = null;
    try { await partial?.remove(); } catch { /* noop */ }
    try { await state?.remove(); } catch { /* noop */ }
    try { await sr.stop(); } catch { /* noop */ }  // cap/edge: engine must die
  }
}

/** Finalize an in-flight recognition (tap-to-stop) — ends the session in BOTH
 *  modes: one-shot resolves via the plugin, live-transcript via _finish (the
 *  stopped event may race listener removal, so we also resolve locally). */
export async function nativeSttStop(): Promise<void> {
  const sr = await plugin();
  try { await sr?.stop(); } catch { /* noop */ }
  _finish?.();
}
