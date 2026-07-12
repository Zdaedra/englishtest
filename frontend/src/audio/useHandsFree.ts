import { useCallback, useRef } from "react";

// Persistent-mic recorder for the hands-free practice loop. iOS only grants the
// mic on a user gesture, so `open()` (called from the toggle tap) acquires ONE
// MediaStream and we reuse it for every card's recording — no per-card gesture.
// `record()` captures a single clip, auto-stopping after `maxMs` (or `stopNow()`).
const MIME_CANDIDATES = [
  "audio/webm;codecs=opus", "audio/webm", "audio/mp4", "audio/aac", "audio/mpeg",
];
function pickMime(): string {
  if (typeof MediaRecorder === "undefined" || !MediaRecorder.isTypeSupported) return "";
  for (const m of MIME_CANDIDATES) if (MediaRecorder.isTypeSupported(m)) return m;
  return "";
}
function extFor(mime: string): string {
  if (mime.includes("webm")) return "webm";
  if (mime.includes("mp4")) return "mp4";
  if (mime.includes("aac")) return "aac";
  if (mime.includes("mpeg")) return "mp3";
  return "webm";
}

export type HFClip = { blob: Blob; filename: string; ms: number };

export function useHandsFree() {
  const streamRef = useRef<MediaStream | null>(null);
  const mrRef = useRef<MediaRecorder | null>(null);

  const open = useCallback(async (): Promise<boolean> => {
    if (streamRef.current) return true;
    try {
      streamRef.current = await navigator.mediaDevices.getUserMedia({ audio: true });
      return true;
    } catch { return false; }
  }, []);

  const stopNow = useCallback(() => {
    try { if (mrRef.current && mrRef.current.state !== "inactive") mrRef.current.stop(); }
    catch { /* noop */ }
  }, []);

  const close = useCallback(() => {
    stopNow();
    streamRef.current?.getTracks().forEach((t) => t.stop());
    streamRef.current = null;
    mrRef.current = null;
  }, [stopNow]);

  /** Record one clip on the held stream, auto-stopping after `maxMs`. */
  const record = useCallback((maxMs = 6000): Promise<HFClip | null> => {
    return new Promise((resolve) => {
      const stream = streamRef.current;
      if (!stream) { resolve(null); return; }
      const mime = pickMime();
      let mr: MediaRecorder;
      try { mr = mime ? new MediaRecorder(stream, { mimeType: mime }) : new MediaRecorder(stream); }
      catch { resolve(null); return; }
      const chunks: Blob[] = [];
      const startedAt = Date.now();
      mr.ondataavailable = (e) => { if (e.data && e.data.size > 0) chunks.push(e.data); };
      mr.onstop = () => {
        const type = mr.mimeType || mime || "audio/webm";
        const blob = new Blob(chunks, { type });
        resolve(blob.size > 0 ? { blob, filename: `clip.${extFor(type)}`, ms: Date.now() - startedAt } : null);
      };
      mrRef.current = mr;
      mr.start();
      window.setTimeout(() => {
        try { if (mr.state !== "inactive") mr.stop(); } catch { /* noop */ }
      }, maxMs);
    });
  }, []);

  return { open, close, record, stopNow };
}
