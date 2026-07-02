import { isNative } from "../lib/session";

// On-device speech-to-text on native iOS via SFSpeechRecognizer (free, private,
// low-latency — the audio never leaves the phone, no server STT cost). Used only
// for the English phrase answer; the mixed RU+EN sequence exam stays on the server
// path (on-device recognizers are single-locale). The caller falls back to
// MediaRecorder + server STT whenever this is unavailable or permission is denied.
type SR = {
  available(): Promise<{ available: boolean }>;
  checkPermissions(): Promise<{ speechRecognition: string }>;
  requestPermissions(): Promise<{ speechRecognition: string }>;
  start(opts: {
    language?: string; maxResults?: number; partialResults?: boolean; popup?: boolean;
  }): Promise<{ matches?: string[] }>;
  stop(): Promise<void>;
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

/** True only on native iOS with a working on-device recognizer. */
export async function nativeSttAvailable(): Promise<boolean> {
  const sr = await plugin();
  if (!sr) return false;
  try { return (await sr.available()).available === true; } catch { return false; }
}

/** One-shot recognition. Resolves with the transcript (may be ""). Throws if the
 *  recognizer is unavailable or permission is denied — the caller then uses the
 *  server STT path. */
export async function nativeRecognize(language = "en-US"): Promise<string> {
  const sr = await plugin();
  if (!sr) throw new Error("native-stt-unavailable");
  if (!(await sr.available()).available) throw new Error("native-stt-unavailable");
  let perm = await sr.checkPermissions();
  if (perm.speechRecognition !== "granted") perm = await sr.requestPermissions();
  if (perm.speechRecognition !== "granted") throw new Error("native-stt-denied");
  const res = await sr.start({ language, maxResults: 1, partialResults: false, popup: false });
  return (res?.matches?.[0] || "").trim();
}

/** Finalize an in-flight recognition (tap-to-stop) — resolves the pending start(). */
export async function nativeSttStop(): Promise<void> {
  const sr = await plugin();
  try { await sr?.stop(); } catch { /* noop */ }
}
