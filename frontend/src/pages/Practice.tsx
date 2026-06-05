import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api, PracticeQuestion } from "../api";
import { useRecorder } from "../audio/useRecorder";
import { RecFab } from "../ui/RecFab";
import { IconHeadphones, IconPlay } from "../ui/icons";
import { isEngaged } from "../lib/progress";

type Attempt = { prompt: string; heard: string; score: number; anchor: string; batch: string };

// Engaged batches — activated, in-progress, or passed — straight from localStorage
// (no round-trip). Practice draws from everything in the learner's active set, not
// only fully-passed batches.
function engagedBatchIds(): number[] {
  const out: number[] = [];
  try {
    for (let i = 0; i < localStorage.length; i++) {
      const k = localStorage.key(i);
      if (!k || !k.startsWith("ee-progress-")) continue;
      const id = Number(k.slice("ee-progress-".length));
      if (Number.isNaN(id)) continue;
      const p = JSON.parse(localStorage.getItem(k) || "{}");
      if (isEngaged(p)) out.push(id);
    }
  } catch { /* ignore */ }
  return out;
}

export default function Practice() {
  const nav = useNavigate();
  const rec = useRecorder();

  const [questions, setQuestions] = useState<PracticeQuestion[] | null>(null);
  const [started, setStarted] = useState(false);
  const [pos, setPos] = useState(0);
  const [log, setLog] = useState<Attempt[]>([]);
  const usedRef = useRef<Set<number>>(new Set()); // phrase_ids already nailed (≥8) this session
  const [busy, setBusy] = useState(false);
  const [notice, setNotice] = useState("");
  const [err, setErr] = useState("");
  const promptAudio = useRef<HTMLAudioElement>(null);

  const ids = useMemo(() => engagedBatchIds(), []);

  useEffect(() => {
    if (ids.length === 0) { setQuestions([]); return; }
    api.getPracticeQuestions(ids).then((r) => setQuestions(r.questions)).catch((e) => setErr(String(e)));
  }, [ids]);

  const cur = questions && questions.length ? questions[pos % questions.length] : null;

  // Voice-first: try to play the prompt TTS when a new question appears. iOS may
  // block autoplay outside a gesture → the «Прослушать» button is the reliable path.
  useEffect(() => {
    if (!started || !cur) return;
    let cancelled = false;
    api.practicePromptAudio(cur.prompt_ru).then(({ audio_url }) => {
      if (cancelled) return;
      const a = promptAudio.current;
      if (a) { a.src = audio_url; a.play().catch(() => {}); }
    }).catch(() => {});
    return () => { cancelled = true; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [started, pos, cur?.id]);

  const replayPrompt = () => {
    const a = promptAudio.current;
    if (a?.src) { a.currentTime = 0; a.play().catch(() => {}); }
  };

  const onMic = useCallback(async () => {
    if (!cur) return;
    setErr("");
    if (!rec.recording) { setNotice(""); await rec.start(); return; }
    const clip = await rec.stop();
    if (!clip || clip.ms < 500) { setNotice("Не расслышал — нажми и говори чуть дольше."); return; }
    setBusy(true);
    try {
      const r = await api.practiceScore(cur.accept_phrase_ids, [...usedRef.current], clip.blob, clip.filename, clip.ms);
      if (!r.transcript?.trim()) { setNotice("Не расслышал — попробуй ещё раз."); return; }
      if (r.is_repeat) {
        setNotice("🔁 Это уже было — дай другой вариант.");
        return; // same prompt, no log, no advance
      }
      setLog((l) => [
        { prompt: cur.prompt_ru, heard: r.transcript, score: r.score, anchor: r.anchor, batch: cur.batch_title },
        ...l,
      ]);
      if (r.score >= 8) usedRef.current.add(r.phrase_id);
      setNotice("");
      setPos((p) => p + 1);
    } catch (e) {
      const msg = String(e);
      if (msg.includes("429") || msg.toLowerCase().includes("limit")) setNotice("Дневной лимит проверок исчерпан.");
      else setErr(msg);
    } finally {
      setBusy(false);
    }
  }, [cur, rec]);

  const stats = useMemo(() => {
    const n = log.length;
    const green = log.filter((a) => a.score >= 8).length;
    const avg = n ? log.reduce((s, a) => s + a.score, 0) / n : 0;
    return { n, green, red: n - green, avg };
  }, [log]);

  if (err) return <div className="screen pr-screen"><p className="error">{err}</p></div>;
  if (questions === null) return <div className="screen pr-screen"><p className="muted">Loading…</p></div>;

  return (
    <div className="screen pr-screen">
      <div className="screen-head">
        <span className="lesson-tag" style={{ color: "var(--map-green)" }}>Практика</span>
        <h1>Вживую</h1>
        <p className="app-sub" style={{ marginBottom: 0 }}>
          Слушай ситуацию — отвечай голосом фразой из своих активных навыков.
        </p>
      </div>

      {!rec.supported && (
        <div className="l3-warn" style={{ marginTop: 16 }}>
          <span className="l3-warn-ic"><IconHeadphones size={20} /></span>
          <p className="l3-warn-txt">Этот браузер не умеет записывать звук. Откройте в <b>Safari</b> или <b>Chrome</b>.</p>
        </div>
      )}

      {questions.length === 0 ? (
        <div className="pr-empty">
          <p className="pr-empty-t">Пока нечего практиковать</p>
          <p className="pr-empty-s">
            Открой любой бетч и нажми «Активировать бетч» — он сразу попадёт сюда для живой
            тренировки (а не только после полного прохождения). Активные и пройденные бетчи —
            это и есть твой материал для практики.
          </p>
          <button className="l3-cta" style={{ marginTop: 18 }} onClick={() => nav("/learn")}>
            <IconPlay size={18} /> В Обучение
          </button>
        </div>
      ) : !started ? (
        <div className="pr-start">
          <p className="pr-start-s">
            Бесконечная сессия: вопрос → голосовой ответ → балл. Зелёный ≥ 8, красный ниже.
            Повторишь ту же фразу — попрошу другой вариант.
          </p>
          <button className="l3-cta" onClick={() => setStarted(true)}>
            <IconPlay size={18} /> Начать тренировку
          </button>
        </div>
      ) : (
        <>
          {cur && (
            <div className="pr-prompt">
              <div className="pr-prompt-tag">{cur.batch_title} · {cur.zone}</div>
              <p className="pr-prompt-text">{cur.prompt_ru}</p>
              <button className="mp-pill" onClick={replayPrompt}>
                <IconPlay size={15} /> Прослушать
              </button>
            </div>
          )}

          {notice && <p className="muted small pr-notice">{notice}</p>}
          {rec.error && <p className="error" style={{ marginTop: 8 }}>{rec.error}</p>}

          <RecFab recording={rec.recording} busy={busy} onClick={onMic} />
          <p className="rec-label">
            {rec.recording ? "Идёт запись — нажми «стоп»" : busy ? "Проверяем…" : "Нажми и ответь"}
          </p>

          <button className="btn btn-tint btn-block" style={{ marginTop: 12 }} onClick={() => setStarted(false)}>
            Завершить
          </button>

          {log.length > 0 && (
            <div className="pr-log">
              {log.map((a, i) => (
                <div className="pr-row" key={i}>
                  <span className={`pr-score ${a.score >= 8 ? "ok" : "no"}`}>{a.score}</span>
                  <div className="pr-row-body">
                    <div className="pr-heard">{a.heard || "— тишина —"}</div>
                    <div className="pr-row-meta">{a.anchor} · {a.batch}</div>
                  </div>
                </div>
              ))}
            </div>
          )}

          <div className="pr-stats">
            <span>Ответов <b>{stats.n}</b></span>
            <span>Средний <b>{stats.avg.toFixed(1)}</b></span>
            <span className="pr-stat-ok">🟢 {stats.green}</span>
            <span className="pr-stat-no">🔴 {stats.red}</span>
          </div>
        </>
      )}

      <audio ref={promptAudio} playsInline preload="auto" />
    </div>
  );
}
