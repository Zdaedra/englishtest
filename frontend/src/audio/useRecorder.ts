import { useCallback, useRef, useState } from "react";

// iOS Safari (and the standalone home-screen PWA) cannot use webkitSpeechRecognition,
// so we capture a short clip with MediaRecorder and POST it to the STT endpoint.
// MediaRecorder's supported container differs per browser: Chrome/Firefox do webm,
// iOS Safari only does mp4/aac. Probe in preference order and fall back.
const MIME_CANDIDATES = [
  "audio/webm;codecs=opus",
  "audio/webm",
  "audio/mp4",
  "audio/aac",
  "audio/mpeg",
];

function pickMime(): string {
  if (typeof MediaRecorder === "undefined" || !MediaRecorder.isTypeSupported) return "";
  for (const m of MIME_CANDIDATES) if (MediaRecorder.isTypeSupported(m)) return m;
  return ""; // let the browser pick its own default
}

function extFor(mime: string): string {
  if (mime.includes("webm")) return "webm";
  if (mime.includes("mp4")) return "mp4";
  if (mime.includes("aac")) return "aac";
  if (mime.includes("mpeg")) return "mp3";
  return "webm";
}

export type Recording = { blob: Blob; filename: string; ms: number };

export function useRecorder() {
  const [recording, setRecording] = useState(false);
  const [error, setError] = useState("");
  const mrRef = useRef<MediaRecorder | null>(null);
  const chunksRef = useRef<Blob[]>([]);
  const streamRef = useRef<MediaStream | null>(null);
  const startedAtRef = useRef(0);
  const resolveRef = useRef<((r: Recording | null) => void) | null>(null);

  const supported =
    typeof navigator !== "undefined" &&
    !!navigator.mediaDevices?.getUserMedia &&
    typeof MediaRecorder !== "undefined";

  // Must be called from a user gesture (tap) — iOS only grants the mic then.
  const start = useCallback(async (): Promise<boolean> => {
    setError("");
    if (!supported) {
      setError("Запись звука не поддерживается в этом браузере.");
      return false;
    }
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      streamRef.current = stream;
      const mime = pickMime();
      const mr = mime ? new MediaRecorder(stream, { mimeType: mime }) : new MediaRecorder(stream);
      chunksRef.current = [];
      mr.ondataavailable = (e) => {
        if (e.data && e.data.size > 0) chunksRef.current.push(e.data);
      };
      mr.onstop = () => {
        const type = mr.mimeType || mime || "audio/webm";
        const blob = new Blob(chunksRef.current, { type });
        streamRef.current?.getTracks().forEach((t) => t.stop());
        streamRef.current = null;
        const rec: Recording = {
          blob,
          filename: `clip.${extFor(type)}`,
          ms: Date.now() - startedAtRef.current,
        };
        const resolve = resolveRef.current;
        resolveRef.current = null;
        resolve?.(blob.size > 0 ? rec : null);
      };
      mrRef.current = mr;
      startedAtRef.current = Date.now();
      mr.start();
      setRecording(true);
      return true;
    } catch (e: any) {
      streamRef.current?.getTracks().forEach((t) => t.stop());
      streamRef.current = null;
      setError(
        e?.name === "NotAllowedError" || e?.name === "SecurityError"
          ? "Нет доступа к микрофону. Разрешите его в настройках сайта."
          : "Не удалось включить запись: " + String(e?.message || e)
      );
      return false;
    }
  }, [supported]);

  const stop = useCallback((): Promise<Recording | null> => {
    return new Promise((resolve) => {
      const mr = mrRef.current;
      if (!mr || mr.state === "inactive") {
        resolve(null);
        return;
      }
      resolveRef.current = resolve;
      setRecording(false);
      mr.stop();
    });
  }, []);

  return { recording, error, supported, start, stop };
}
