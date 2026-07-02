import { useCallback, useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api, AnswerResult, Scenario } from "../api";
import { IconBack, IconMic } from "../ui/icons";
import { ModelPhrase } from "../ui/ModelPhrase";
import { useI18n } from "../i18n";
import { useAuth } from "../auth/AuthContext";
import { useSpeech } from "../audio/useSpeech";
import { useRecorder } from "../audio/useRecorder";
import { isNative } from "../lib/session";
import { nativeRecognize } from "../audio/nativeStt";

// The Arena: three learned phrases woven by the LLM into ONE fresh scene — the
// review returns "in battle" (staged retrieval), not on a flashcard. Answers go
// through the normal /api/training/answer* endpoints, so Arena work advances the
// same mastery + SRS as the deck.
export default function Arena() {
  const nav = useNavigate();
  const { t } = useI18n();
  const { user } = useAuth();
  const speech = useSpeech();
  const rec = useRecorder();
  const [scenario, setScenario] = useState<Scenario | null>(null);
  const [phase, setPhase] = useState<"loading" | "locked" | "notEnough" | "error" | "play" | "recap">("loading");
  const [beat, setBeat] = useState(0);
  const [result, setResult] = useState<AnswerResult | null>(null);
  const [scores, setScores] = useState<number[]>([]);
  const [busy, setBusy] = useState(false);
  const [notice, setNotice] = useState("");
  const [recFallback, setRecFallback] = useState(false);
  const [nativeListening, setNativeListening] = useState(false);
  const sessionId = useRef(`arena-${Date.now().toString(36)}`).current;

  const load = useCallback(() => {
    setPhase("loading"); setScenario(null); setBeat(0); setScores([]); setResult(null);
    api.getScenario()
      .then((s) => { setScenario(s); setPhase("play"); })
      .catch((e) => {
        const msg = String(e);
        if (msg.includes("403")) setPhase("locked");
        else if (msg.includes("409")) setPhase("notEnough");
        else setPhase("error");
      });
  }, []);
  useEffect(() => { load(); }, [load]);

  const cur = scenario?.beats[beat];

  const scoreTranscript = async (tr: string) => {
    if (!cur) return;
    setBusy(true);
    try {
      const r = await api.trainAnswerText(sessionId, cur.phrase_id, tr);
      setResult(r); setScores((s) => [...s, r.score]);
    } catch (e) {
      setNotice(String(e).includes("429") ? t("practice.limitReached") : String(e));
    } finally { setBusy(false); }
  };

  // Mic ladder, same order as the trainer: Web Speech (web) → native on-device →
  // MediaRecorder + server STT.
  const onMic = async () => {
    if (!cur || busy || result) return;
    setNotice("");
    if (speech.supported && !recFallback && !isNative()) {
      if (speech.listening) { speech.stop(); return; }
      let tr = "";
      try { tr = await speech.start("en-US"); }
      catch { setRecFallback(true); setNotice(t("practice.micUnavailable")); return; }
      if (tr.trim()) await scoreTranscript(tr);
      return;
    }
    if (isNative() && !recFallback) {
      if (nativeListening) return;
      setNativeListening(true);
      let tr = "";
      try { tr = await nativeRecognize("en-US"); }
      catch { setNativeListening(false); setRecFallback(true); setNotice(t("practice.micUnavailable")); return; }
      setNativeListening(false);
      if (tr.trim()) await scoreTranscript(tr);
      return;
    }
    if (!rec.recording) { await rec.start(); return; }
    const clip = await rec.stop();
    if (!clip || clip.ms < 400) { setNotice(t("practice.micLonger")); return; }
    setBusy(true);
    try {
      const r = await api.trainAnswer(sessionId, cur.phrase_id, clip.blob, clip.filename, clip.ms);
      setResult(r); setScores((s) => [...s, r.score]);
    } catch (e) {
      setNotice(String(e).includes("429") ? t("practice.limitReached") : String(e));
    } finally { setBusy(false); }
  };

  const next = () => {
    setResult(null); setNotice("");
    if (beat + 1 >= (scenario?.beats.length ?? 0)) setPhase("recap");
    else setBeat(beat + 1);
  };

  const micActive = speech.listening || nativeListening || rec.recording;
  const avg = scores.length ? Math.round((scores.reduce((a, b) => a + b, 0) / scores.length) * 10) : 0;

  return (
    <div className="screen arena-screen">
      <button className="back-link" onClick={() => nav(-1)}>
        <IconBack size={18} /> {t("common.back")}
      </button>

      {phase === "loading" && <p className="muted" style={{ marginTop: 40 }}>{t("arena.loading")}</p>}

      {phase === "locked" && (
        <div className="arena-empty">
          <h1 className="arena-title">{t("arena.title")}</h1>
          <p className="league-sub">{t("arena.lockedSub")}</p>
          <button className="btn-primary" onClick={() => nav("/subscribe")}>{t("arena.lockedCta")}</button>
        </div>
      )}

      {phase === "notEnough" && (
        <div className="arena-empty">
          <h1 className="arena-title">{t("arena.title")}</h1>
          <p className="league-sub">{t("arena.notEnough")}</p>
          <button className="btn-primary" onClick={() => nav("/practice")}>{t("arena.goPractice")}</button>
        </div>
      )}

      {phase === "error" && (
        <div className="arena-empty">
          <p className="league-sub">{t("arena.error")}</p>
          <button className="btn-primary" onClick={load}>{t("arena.retry")}</button>
        </div>
      )}

      {phase === "play" && cur && (
        <div className="arena-play">
          <p className="league-count">{beat + 1} / {scenario!.beats.length}</p>
          {scenario!.title_ru && <p className="arena-scene-title">{scenario!.title_ru}</p>}
          <p className="league-situation">{cur.situation_ru}</p>
          {cur.task_ru && <p className="arena-task">{cur.task_ru}</p>}

          {result ? (
            <div className="arena-result">
              <div className={`verdict-pct ${result.score >= 8 ? "ok" : result.score < 5 ? "no" : ""}`}>
                {Math.round(result.score * 10)}<span style={{ fontSize: 20, fontWeight: 700 }}>%</span>
              </div>
              <ModelPhrase label={t("practice.modelLabel")} model={result.correct_phrase} said={result.transcript} />
              <button className="btn-primary arena-next" onClick={next}>
                {beat + 1 >= scenario!.beats.length ? t("arena.finish") : t("arena.next")}
              </button>
            </div>
          ) : (
            <div className="tr-mic-zone arena-mic">
              <button className={`tr-mic-glass${micActive ? " on" : ""}`} onClick={onMic} disabled={busy}
                aria-label={t("rec.recordAria")}>
                {busy ? <span className="tr-mic-dots">…</span> : rec.recording ? <span className="tr-mic-stop" /> : <IconMic size={28} />}
              </button>
              {speech.listening && speech.interim && <p className="tr-mic-live" aria-live="polite">{speech.interim}</p>}
              {micActive && <p className="tr-mic-label">{t("practice.micListening")}</p>}
            </div>
          )}
          {notice && <p className="tr-mic-warn" role="alert">{notice}</p>}
        </div>
      )}

      {phase === "recap" && scenario && (
        <div className="arena-empty">
          <p className="league-eyebrow">{t("arena.recapEyebrow")}</p>
          <div className="verdict-pct">{avg}<span style={{ fontSize: 20, fontWeight: 700 }}>%</span></div>
          <div className="arena-recap-list">
            {scenario.beats.map((b, i) => (
              <p className="arena-recap-row" key={b.phrase_id}>
                <span className={`arena-recap-score ${scores[i] >= 8 ? "ok" : ""}`}>
                  {scores[i] != null ? `${Math.round(scores[i] * 10)}%` : "—"}
                </span>
                {b.phrase_en}
              </p>
            ))}
          </div>
          <button className="btn-primary" onClick={load}>{t("arena.again")}</button>
          <button className="arena-home" onClick={() => nav("/learn")}>{t("arena.home")}</button>
        </div>
      )}
    </div>
  );
}
