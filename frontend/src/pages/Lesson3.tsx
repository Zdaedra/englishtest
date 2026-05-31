import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { api, BatchDetail as Batch, Phrase, PhraseScore, SequenceScore } from "../api";
import { anchorSegments, useMnemoAudio } from "../audio/useMnemoAudio";
import { useRecorder } from "../audio/useRecorder";
import { usePlayer } from "../player/PlayerContext";
import { setProgress } from "../lib/progress";
import { RecFab, band } from "../ui/RecFab";
import { IconBack, IconCheck, IconPlay } from "../ui/icons";

type Stage = "ready" | "running" | "exam";
type Stop = { anchor_id: string; start: number; end: number };

// Pick k distinct segments at random, returned in playback order.
function sampleSorted(segs: Stop[], k: number): Stop[] {
  const idx = segs.map((_, i) => i);
  for (let i = idx.length - 1; i > 0; i--) {
    const j = Math.floor(Math.random() * (i + 1));
    [idx[i], idx[j]] = [idx[j], idx[i]];
  }
  return idx.slice(0, k).sort((a, b) => a - b).map((i) => segs[i]);
}

export default function Lesson3() {
  const { id } = useParams();
  const nav = useNavigate();
  const player = usePlayer();
  const rec = useRecorder();

  const [batch, setBatch] = useState<Batch | null>(null);
  const [err, setErr] = useState("");
  const [notice, setNotice] = useState("");
  const [stage, setStage] = useState<Stage>("ready");
  const [busy, setBusy] = useState(false);

  // Random-stop run.
  const stopsRef = useRef<Stop[]>([]);
  const pendingRef = useRef(0); // index of the next stop to fire
  const [stopTotal, setStopTotal] = useState(0);
  const [answered, setAnswered] = useState(0);
  const [stopAnchor, setStopAnchor] = useState<string | null>(null);
  const [stopResult, setStopResult] = useState<PhraseScore | null>(null);

  // Final exam (the hard gate).
  const [examResult, setExamResult] = useState<SequenceScore | null>(null);

  // Pause playback at each chosen anchor's end and raise a prompt.
  const onTick = useCallback((time: number, audio: HTMLAudioElement) => {
    const stops = stopsRef.current;
    const i = pendingRef.current;
    if (i >= stops.length) return;
    if (time >= stops[i].end) {
      pendingRef.current = i + 1;
      audio.pause();
      setStopAnchor(stops[i].anchor_id);
    }
  }, []);

  const onStoryEnded = useCallback(() => setStage("exam"), []);

  const mnemo = useMnemoAudio(id ? Number(id) : undefined, onTick, onStoryEnded);

  useEffect(() => {
    if (!id) return;
    api.getBatch(Number(id)).then((b) => {
      setBatch(b);
      player.prefetchPhrases(b.phrases.map((p) => p.id));
    }).catch((e) => setErr(String(e)));
    mnemo.prefetch("full");
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [id]);

  // anchor_id → the phrase that sits on it (for the prompt label + scoring target).
  const phraseByAnchor = useMemo(() => {
    const byId = new Map<number, Phrase>();
    batch?.phrases.forEach((p) => byId.set(p.id, p));
    const m = new Map<string, Phrase>();
    batch?.mnemo.spans.forEach((s) => {
      const p = byId.get(s.phrase_id);
      if (p) m.set(s.anchor_id, p);
    });
    return m;
  }, [batch]);

  const handleError = (e: unknown) => {
    const msg = String(e);
    if (msg.includes("429") || msg.toLowerCase().includes("limit")) {
      setNotice("Дневной лимит проверок исчерпан — продолжай без оценки.");
    } else {
      setErr(msg);
    }
  };

  const startTest = useCallback(async () => {
    setErr(""); setNotice(""); setStopResult(null); setAnswered(0);
    pendingRef.current = 0;
    await mnemo.play("full");
    const segs = anchorSegments(mnemo.planRef.current);
    const k = Math.max(1, Math.round(segs.length * 0.3));
    const chosen = sampleSorted(segs, k);
    stopsRef.current = chosen;
    setStopTotal(chosen.length);
    setStage("running");
  }, [mnemo]);

  const stopPhrase = stopAnchor ? phraseByAnchor.get(stopAnchor) ?? null : null;

  const onMicStop = useCallback(async () => {
    if (!stopPhrase) return;
    setErr("");
    if (!rec.recording) {
      setStopResult(null);
      await rec.start();
      return;
    }
    const clip = await rec.stop();
    if (!clip || clip.ms < 600) {
      setNotice("Не расслышал — нажми и говори чуть дольше.");
      return;
    }
    setBusy(true);
    try {
      const r = await api.scorePhrase(stopPhrase.id, clip.blob, clip.filename, clip.ms);
      if (!r.transcript?.trim()) {
        setNotice("Не расслышал — попробуй ещё раз.");
        return;
      }
      setStopResult(r);
    } catch (e) {
      handleError(e);
    } finally {
      setBusy(false);
    }
  }, [stopPhrase, rec]);

  const continueStops = useCallback(() => {
    setStopResult(null);
    setStopAnchor(null);
    setNotice("");
    setAnswered((n) => n + 1);
    mnemo.resume();
  }, [mnemo]);

  const onMicExam = useCallback(async () => {
    if (!batch) return;
    setErr("");
    if (!rec.recording) {
      setExamResult(null);
      await rec.start();
      return;
    }
    const clip = await rec.stop();
    if (!clip || clip.ms < 600) {
      setNotice("Не расслышал — нажми и перескажи историю.");
      return;
    }
    setBusy(true);
    try {
      const r = await api.scoreSequence(batch.id, clip.blob, clip.filename, clip.ms);
      setExamResult(r);
      if (r.passed) setProgress(batch.id, { l3_passed: true });
    } catch (e) {
      handleError(e);
    } finally {
      setBusy(false);
    }
  }, [batch, rec]);

  if (err) return <div className="screen"><p className="error">{err}</p></div>;
  if (!batch) return <div className="screen"><p className="muted">Loading…</p></div>;

  return (
    <div className="screen">
      <button className="back-link" onClick={() => nav(`/batch/${batch.id}`)}>
        <IconBack /> {batch.title}
      </button>

      <div className="screen-head">
        <span className="lesson-tag">Урок 3</span>
        <h1>Тесты</h1>
        <p className="app-sub" style={{ marginBottom: 0 }}>
          {stage === "exam"
            ? "Финал: перескажи всю историю по памяти."
            : "История читается и иногда замирает — назови нужную фразу вслух."}
        </p>
      </div>

      {!rec.supported && (
        <p className="error" style={{ marginTop: 16 }}>
          Этот браузер не умеет записывать звук. Откройте приложение в Safari/Chrome.
        </p>
      )}
      {rec.error && <p className="error" style={{ marginTop: 12 }}>{rec.error}</p>}
      {notice && <p className="muted small" style={{ marginTop: 12 }}>{notice}</p>}

      {stage === "ready" && (
        <>
          <div className="card-block" style={{ marginTop: 18 }}>
            <p className="train-hint" style={{ margin: 0, textAlign: "left" }}>
              Мнемоническая история запустится сама. На случайных якорях она остановится
              и попросит назвать фразу — скажи её своими словами, можно коротко. В конце —
              финальный пересказ всей последовательности.
            </p>
          </div>
          <button className="btn btn-primary btn-block" style={{ marginTop: 20 }} onClick={startTest}>
            <IconPlay size={16} /> Начать тест
          </button>
        </>
      )}

      {stage === "running" && (
        stopAnchor && stopPhrase ? (
          <>
            <div className="train-counter">Стоп {Math.min(answered + 1, stopTotal)} / {stopTotal}</div>
            <p className="section-label center" style={{ marginTop: 4 }}>Какая фраза?</p>
            <p className="train-prompt">{stopPhrase.anchor}</p>

            {stopResult ? (
              <StopResult
                result={stopResult}
                onNext={continueStops}
                onPlayCorrect={() => player.playPhrase(stopResult.phrase_id)}
              />
            ) : (
              <>
                <RecFab recording={rec.recording} busy={busy} onClick={onMicStop} />
                <p className="rec-label">
                  {rec.recording ? "Идёт запись — нажми «стоп»" : busy ? "Проверяем…" : "Нажми и говори"}
                </p>
                <button className="btn btn-tint btn-block" style={{ marginTop: 14 }} onClick={continueStops}>
                  Пропустить
                </button>
              </>
            )}
          </>
        ) : (
          <div className="listening-note">
            <span className="pulse-dot" />
            <p className="train-hint" style={{ margin: 0 }}>
              Слушай историю… ({answered} / {stopTotal})
            </p>
          </div>
        )
      )}

      {stage === "exam" && (
        examResult ? (
          <ExamResult
            batch={batch}
            result={examResult}
            onRetry={() => { setExamResult(null); setNotice(""); }}
            onDone={() => nav(`/batch/${batch.id}`)}
          />
        ) : (
          <>
            <p className="train-prompt sm" style={{ marginTop: 18 }}>Перескажи всю историю</p>
            <p className="train-hint">
              {rec.recording
                ? "Передавай суть и называй якоря по порядку…"
                : `Своими словами — все ${batch.mnemo.spans.length} якорей по порядку. Нужно ≥ 7, чтобы закрыть батч.`}
            </p>
            <RecFab recording={rec.recording} busy={busy} onClick={onMicExam} />
            <p className="rec-label">
              {rec.recording ? "Идёт запись — нажми «стоп»" : busy ? "Проверяем…" : "Нажми и говори"}
            </p>
          </>
        )
      )}

      <audio {...mnemo.bind} />
    </div>
  );
}

function StopResult({
  result, onNext, onPlayCorrect,
}: { result: PhraseScore; onNext: () => void; onPlayCorrect: () => void }) {
  return (
    <div className="result-card">
      <div className={`score-badge ${band(result.score)}`}>
        {result.score}<span className="score-out">/10</span>
      </div>

      <div className="result-row">
        <div className="result-k">Правильная фраза</div>
        <div className="result-v">
          {result.correct_phrase}
          <button className="inline-play" onClick={onPlayCorrect} aria-label="Прослушать">
            <IconPlay size={15} />
          </button>
        </div>
      </div>

      <div className="result-row">
        <div className="result-k">Мы услышали</div>
        <div className="result-v heard">{result.transcript || "— тишина —"}</div>
      </div>

      <button className="btn btn-primary train-cta" onClick={onNext}>Дальше</button>
    </div>
  );
}

function ExamResult({
  batch, result, onRetry, onDone,
}: { batch: Batch; result: SequenceScore; onRetry: () => void; onDone: () => void }) {
  return (
    <div className="result-card">
      <div className={`score-badge ${band(result.score)}`}>
        {result.score}<span className="score-out">/10</span>
      </div>

      <div className="center" style={{ marginBottom: 14 }}>
        <span className={`pass-pill ${result.passed ? "ok" : "no"}`}>
          {result.passed ? <><IconCheck size={15} /> Батч закрыт</> : "Ещё разок"}
        </span>
      </div>

      {result.missed_anchors.length > 0 && (
        <div className="result-row">
          <div className="result-k">Пропущенные якоря</div>
          <div className="miss-chips">
            {result.missed_anchors.map((a, i) => <span className="miss-chip" key={i}>{a}</span>)}
          </div>
        </div>
      )}

      <div className="result-row">
        <div className="result-k">Порядок</div>
        <div className="result-v">{result.order_ok ? "сохранён" : "нарушен"}</div>
      </div>

      <div className="result-row">
        <div className="result-k">Мы услышали</div>
        <div className="result-v heard">{result.transcript || "— тишина —"}</div>
      </div>

      {result.passed ? (
        <button className="btn btn-primary train-cta" onClick={onDone}>Готово</button>
      ) : (
        <button className="btn btn-primary train-cta" onClick={onRetry}>Попробовать снова</button>
      )}
    </div>
  );
}
