// Text-to-speech for the practice cue (the "trigger" prompt).
//
// Preferred path: speakCueAudio() plays the SERVER's OpenAI neural voice (cached
// on disk by the backend) — far more natural than the on-device robot. Falls back
// to the Web Speech *synthesis* API (speakCue) on any failure (offline, TTS down).
// speechSynthesis DOES work in iOS WKWebView (unlike speech *recognition*).
import { api } from "../api";

// One reused <audio> element. iOS only lets it play after a user-gesture unlock
// (see unlockAudio), so warming it on the same tap that starts hands-free is key.
let _audioEl: HTMLAudioElement | null = null;
function audioEl(): HTMLAudioElement {
  if (!_audioEl) { _audioEl = new Audio(); _audioEl.preload = "auto"; }
  return _audioEl;
}

/** Unlock HTML5 audio inside a user gesture (iOS requirement). Call from the tap
 *  that starts hands-free, before any await. */
export function unlockAudio(): void {
  try {
    const a = audioEl();
    a.muted = true;
    const p = a.play();
    const reset = () => { try { a.pause(); a.currentTime = 0; a.muted = false; } catch { /* noop */ } };
    if (p && typeof (p as Promise<void>).then === "function") (p as Promise<void>).then(reset).catch(reset);
    else reset();
  } catch { /* noop */ }
}

function playUrl(url: string): Promise<void> {
  return new Promise((resolve) => {
    try {
      const a = audioEl();
      a.muted = false;
      a.src = url;
      let done = false;
      const finish = () => { if (!done) { done = true; resolve(); } };
      a.onended = finish;
      a.onerror = finish;
      window.setTimeout(finish, 15000);          // safety net if events never fire
      const p = a.play();
      if (p && typeof (p as Promise<void>).catch === "function") (p as Promise<void>).catch(() => finish());
    } catch { resolve(); }
  });
}

// Cue-audio URL cache (dedupes the synth round-trip). Keyed by lang|text; the value
// is the in-flight/resolved promise so a prefetch and the real play share one fetch.
const cueCache = new Map<string, Promise<string>>();
function fetchCueUrl(text: string, lang: string): Promise<string> {
  const l = lang.toLowerCase().startsWith("en") ? "en" : "ru";
  const key = `${l}|${text}`;
  let p = cueCache.get(key);
  if (!p) {
    p = api.practicePromptAudio(text, l).then((r) => r.audio_url)
      .catch((e) => { cueCache.delete(key); throw e; });   // don't cache failures
    cueCache.set(key, p);
  }
  return p;
}

/** Warm a cue ahead of time (server synth + client cache) so playback is instant
 *  when it's actually needed. Fire-and-forget; safe to call repeatedly. */
export function prefetchCueAudio(text: string, lang = "en"): void {
  const t = (text || "").trim();
  if (!t) return;
  fetchCueUrl(t, lang)
    .then((url) => { try { const a = new Audio(); a.preload = "auto"; a.src = url; } catch { /* noop */ } })
    .catch(() => { /* prefetch is best-effort */ });
}

/** Speak `text` via the server neural voice (lang picks en/ru voice), resolving
 *  when playback ends. Reuses a prefetched URL when available. Falls back to the
 *  on-device voice on any failure. */
export async function speakCueAudio(text: string, lang = "en"): Promise<void> {
  const t = (text || "").trim();
  if (!t) return;
  try {
    const url = await fetchCueUrl(t, lang);
    await playUrl(url);
  } catch {
    await speakCue(t);                            // graceful fallback to the robot
  }
}

let _voices: SpeechSynthesisVoice[] = [];
function voices(): SpeechSynthesisVoice[] {
  try {
    if (!_voices.length) _voices = window.speechSynthesis.getVoices();
  } catch { /* unsupported */ }
  return _voices;
}
// Warm the voice list (Safari populates it async).
try { window.speechSynthesis?.addEventListener?.("voiceschanged", () => { _voices = window.speechSynthesis.getVoices(); }); } catch { /* noop */ }

const isCyrillic = (s: string) => /[Ѐ-ӿ]/.test(s);

export function speakSupported(): boolean {
  return typeof window !== "undefined" && "speechSynthesis" in window;
}

/** Speak `text`, auto-picking ru/en by script. Resolves when done (or at once if
 *  unsupported/empty). Cancels any in-flight utterance first. */
export function speakCue(text: string): Promise<void> {
  return new Promise((resolve) => {
    const t = (text || "").trim();
    if (!speakSupported() || !t) { resolve(); return; }
    try {
      const synth = window.speechSynthesis;
      synth.cancel();
      const u = new SpeechSynthesisUtterance(t);
      const lang = isCyrillic(t) ? "ru-RU" : "en-US";
      u.lang = lang;
      const v = voices().find((x) => x.lang?.toLowerCase().startsWith(lang.slice(0, 2)));
      if (v) u.voice = v;
      u.rate = 0.96;
      let done = false;
      const finish = () => { if (!done) { done = true; resolve(); } };
      u.onend = finish;
      u.onerror = finish;
      // Safety net: some engines never fire onend — cap by a length-based timeout.
      window.setTimeout(finish, Math.min(9000, 1500 + t.length * 90));
      synth.speak(u);
    } catch { resolve(); }
  });
}

export function cancelSpeak(): void {
  try { window.speechSynthesis?.cancel(); } catch { /* noop */ }
  try { if (_audioEl) { _audioEl.pause(); _audioEl.currentTime = 0; } } catch { /* noop */ }
}
