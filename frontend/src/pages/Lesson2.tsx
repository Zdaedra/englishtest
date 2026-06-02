import { useCallback, useEffect, useMemo, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { api, BatchDetail as Batch, PhraseScore, RotationItem } from "../api";
import { useMnemoAudio } from "../audio/useMnemoAudio";
import { useRecorder } from "../audio/useRecorder";
import { usePlayer } from "../player/PlayerContext";
import { groupByZone } from "../lib/zones";
import { ZoneHead } from "../ui/Zone";
import { RecFab, band } from "../ui/RecFab";
import { IconBack, IconChevron, IconPause, IconPlay } from "../ui/icons";

export default function Lesson2() {
  const { id } = useParams();
  const nav = useNavigate();
  const player = usePlayer();
  const mnemo = useMnemoAudio(id ? Number(id) : undefined);
  const rec = useRecorder();

  const [batch, setBatch] = useState<Batch | null>(null);
  const [err, setErr] = useState("");
  const [revealed, setRevealed] = useState<Set<number>>(new Set());
  const [notice, setNotice] = useState("");

  // Test B drill state.
  const [rotation, setRotation] = useState<RotationItem[]>([]);
  const [pos, setPos] = useState(0);
  const [result, setResult] = useState<PhraseScore | null>(null);
  const [busy, setBusy] = useState(false);
  const [drillStarted, setDrillStarted] = useState(false);

  useEffect(() => {
    if (!id) return;
    api.getBatch(Number(id)).then((b) => {
      setBatch(b);
      player.prefetchPhrases(b.phrases.map((p) => p.id));
    }).catch((e) => setErr(String(e)));
    mnemo.prefetch("full");
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [id]);

  const loadRotation = useCallback(async (bid: number) => {
    try {
      const r = await api.getRotation(bid);
      setRotation(r);
      setPos(0);
    } catch (e) {
      setErr(String(e));
    }
  }, []);

  useEffect(() => {
    if (batch) void loadRotation(batch.id);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [batch]);

  // anchor_id → phrase_id, so the story playback lights up the matching phrase card.
  const phraseIdByAnchor = useMemo(() => {
    const m = new Map<string, number>();
    batch?.mnemo.spans.forEach((s) => m.set(s.anchor_id, s.phrase_id));
    return m;
  }, [batch]);
  const activePhraseId =
    mnemo.activeAnchor ? phraseIdByAnchor.get(mnemo.activeAnchor) ?? null : null;

  const current = rotation[pos] || null;

  const startDrill = useCallback(() => {
    setNotice("");
    setResult(null);
    setDrillStarted(true);
  }, []);

  const handleError = (e: unknown) => {
    const msg = String(e);
    if (msg.includes("429") || msg.toLowerCase().includes("limit")) {
      setNotice("Дневной лимит проверок исчерпан — продолжайте без оценки, сверяясь с фразами.");
    } else {
      setErr(msg);
    }
  };

  const togglePhrase = (pid: number) =>
    setRevealed((prev) => {
      const n = new Set(prev);
      n.has(pid) ? n.delete(pid) : n.add(pid);
      return n;
    });

  // One tap toggles record → stop+score. iOS needs the mic request inside the gesture.
  const onMic = useCallback(async () => {
    if (!batch || !current) return;
    setErr("");
    if (!rec.recording) {
      setResult(null);
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
      const r = await api.scorePhrase(current.phrase_id, clip.blob, clip.filename, clip.ms);
      if (!r.transcript?.trim()) {
        setNotice("Не расслышал — попробуй ещё раз.");
        return;
      }
      setResult(r);
    } catch (e) {
      handleError(e);
    } finally {
      setBusy(false);
    }
  }, [batch, current, rec]);

  const nextPhrase = useCallback(() => {
    setResult(null);
    setNotice("");
    if (!batch) return;
    if (pos + 1 >= rotation.length) void loadRotation(batch.id); // re-weight & loop
    else setPos((p) => p + 1);
  }, [batch, pos, rotation.length, loadRotation]);

  if (err) return <div className="screen"><p className="error">{err}</p></div>;
  if (!batch) return <div className="screen"><p className="muted">Loading…</p></div>;

  const groups = groupByZone(batch);

  // Soft progress readout (the gate itself lives on the ladder, mean ≥ 6).
  const attempted = rotation.filter((r) => r.attempts > 0).length;
  const scored = rotation.filter((r) => r.avg_score != null);
  const mean = scored.length
    ? scored.reduce((s, r) => s + (r.avg_score as number), 0) / scored.length
    : 0;

  return (
    <div className="screen">
      <button className="back-link" onClick={() => nav(`/batch/${batch.id}`)}>
        <IconBack /> {batch.title}
      </button>

      <div className="screen-head">
        <span className="lesson-tag">Урок 2</span>
        <h1>Фразы</h1>
        <p className="app-sub" style={{ marginBottom: 0 }}>
          Свяжи каждый якорь с фразой. Мнемоника всегда под рукой — переслушай, и карточки подсветятся.
        </p>
      </div>

      <p className="section-label" style={{ marginTop: 18 }}>1 · Мнемоника под рукой</p>
      <div className="mnemo-play">
        <button
          className={`mp-pill${mnemo.layout === "full" ? " on" : ""}`}
          disabled={mnemo.loading !== null}
          onClick={() => mnemo.play("full")}
        >
          {mnemo.layout === "full" && mnemo.playing ? <IconPause size={16} /> : <IconPlay size={16} />}
          {mnemo.loading === "full" ? "…" : "Переслушать историю"}
        </button>
      </div>

      <p className="section-label" style={{ marginTop: 22 }}>2 · Якорь → фраза</p>
      <div className="zone-stack">
        {groups.map((g) => (
          <div className="zone-group" key={g.key}>
            <ZoneHead title={g.title} level={g.level} total={g.total} count={g.items.length} />
            {g.items.map(({ p, n }) => (
              <div key={p.id} className={`phrase-card${activePhraseId === p.id ? " lit" : ""}`}>
                <div className="pc-body" onClick={() => togglePhrase(p.id)}>
                  <div className="pc-anchor">
                    <span className="pc-num">{n}</span>{p.anchor}
                  </div>
                  <div className="pc-phrase">{p.phrase_en}</div>
                  {revealed.has(p.id) && p.gloss_ru && (
                    <div className="pc-gloss">{p.gloss_ru}</div>
                  )}
                </div>
                <button className="pc-play" onClick={() => player.playPhrase(p.id)}>
                  <IconPlay size={18} />
                </button>
              </div>
            ))}
          </div>
        ))}
      </div>

      <p className="section-label" style={{ marginTop: 24 }}>3 · Слушай все фразы</p>
      <p className="train-hint" style={{ marginTop: 4 }}>
        Запусти плеер — все фразы вперемешку, по кругу. Слушай и повторяй вслух.
      </p>
      <button
        className="btn btn-primary btn-block"
        style={{ marginTop: 12 }}
        onClick={() => {
          player.playBatch(batch, { mode: "listening", order: "full_random" });
          nav("/play");
        }}
      >
        <IconPlay size={16} /> Слушать вперемешку
      </button>

      <p className="section-label" style={{ marginTop: 24 }}>
        4 · Проверь фразы{attempted > 0 ? ` · средний ${mean.toFixed(1)}` : ""}
      </p>

      {!rec.supported && (
        <p className="error" style={{ marginTop: 12 }}>
          Этот браузер не умеет записывать звук. Откройте приложение в Safari/Chrome.
        </p>
      )}
      {rec.error && <p className="error" style={{ marginTop: 12 }}>{rec.error}</p>}
      {notice && <p className="muted small" style={{ marginTop: 12 }}>{notice}</p>}

      {!current ? (
        <p className="muted" style={{ marginTop: 16 }}>Нет фраз для тренировки.</p>
      ) : !drillStarted ? (
        <>
          <p className="train-hint" style={{ marginTop: 4 }}>
            Покажу якорь — назови фразу вслух по памяти, ИИ оценит и подскажет.
            Не вспомнил — нажми «Подсказать фразу».
          </p>
          <button className="btn btn-primary btn-block" style={{ marginTop: 12 }} onClick={startDrill}>
            Начать проверку
          </button>
        </>
      ) : result ? (
        <DrillResult
          result={result}
          onNext={nextPhrase}
          onPlayCorrect={() => player.playPhrase(result.phrase_id)}
        />
      ) : (
        <>
          {rotation.length > 0 && <div className="train-counter">{pos + 1} / {rotation.length}</div>}
          <p className="train-prompt">{current.anchor}</p>
          <div className="mnemo-play" style={{ marginTop: 14 }}>
            <button className="mp-pill" onClick={() => player.playPhrase(current.phrase_id)}>
              <IconPlay size={16} /> Подсказать фразу
            </button>
          </div>
          <RecFab recording={rec.recording} busy={busy} onClick={onMic} />
          <p className="rec-label">
            {rec.recording ? "Идёт запись — нажми «стоп»" : busy ? "Проверяем…" : "Нажми и говори"}
          </p>
        </>
      )}

      <button className="btn btn-primary btn-block" style={{ marginTop: 24 }}
        onClick={() => nav(`/batch/${batch.id}/lesson/3`)}>
        Дальше к тестам <IconChevron size={16} />
      </button>

      <audio {...mnemo.bind} />
    </div>
  );
}

function DrillResult({
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
