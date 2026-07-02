import { useCallback, useRef, useState } from "react";

// Free, programmatic speech-to-text via the Web Speech API. On iOS Safari 14.5+
// (incl. standalone PWA) webkitSpeechRecognition transcribes via Apple's service
// at no token cost to us — but it can be flaky/slow, so the caller falls back to
// MediaRecorder + server STT when this is unsupported or errors.
type AnySR = any;

function Ctor(): AnySR {
  if (typeof window === "undefined") return null;
  return (window as any).SpeechRecognition || (window as any).webkitSpeechRecognition || null;
}

export function useSpeech() {
  const supported = !!Ctor();
  const [listening, setListening] = useState(false);
  // Live partial transcript while listening ("the app hears you"), cleared on end.
  const [interim, setInterim] = useState("");
  const ref = useRef<AnySR>(null);

  // Resolves with the recognized transcript (one-shot). Rejects on error / no speech.
  const start = useCallback((lang = "en-US"): Promise<string> => {
    return new Promise((resolve, reject) => {
      const C = Ctor();
      if (!C) { reject(new Error("unsupported")); return; }
      const r = new C();
      ref.current = r;
      r.lang = lang;
      r.interimResults = true;
      r.maxAlternatives = 1;
      r.continuous = false;
      let settled = false;
      let finalTr = "";
      r.onresult = (e: any) => {
        let partial = "";
        for (let i = e?.resultIndex ?? 0; i < (e?.results?.length ?? 0); i++) {
          const res = e.results[i];
          const tr = res?.[0]?.transcript || "";
          if (res?.isFinal) finalTr += tr;
          else partial += tr;
        }
        setInterim((finalTr + partial).trim());
      };
      r.onerror = (e: any) => {
        if (settled) return;
        settled = true;
        setListening(false); setInterim("");
        reject(new Error(e?.error || "speech-error"));
      };
      r.onend = () => {
        setListening(false); setInterim("");
        if (settled) return;
        settled = true;
        if (finalTr.trim()) resolve(finalTr.trim());
        else reject(new Error("no-speech"));
      };
      try { r.start(); setListening(true); setInterim(""); }
      catch (e) { setListening(false); reject(e as Error); }
    });
  }, []);

  const stop = useCallback(() => { try { ref.current?.stop(); } catch { /* ignore */ } }, []);

  return { supported, listening, interim, start, stop };
}
