import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import {
  api, AnchorScore, BatchDetail as Batch, Phrase, PhraseScore, SequenceScore,
} from "../api";
import { anchorSegments, useMnemoAudio } from "../audio/useMnemoAudio";
import { useRecorder } from "../audio/useRecorder";
import { usePlayer } from "../player/PlayerContext";
import { getProgress, setProgress } from "../lib/progress";
import { RecFab, band } from "../ui/RecFab";
import {
  IconBack, IconCheck, IconChevron, IconHeadphones, IconMenu, IconPlay, IconShield, IconWave,
} from "../ui/icons";
import { useI18n } from "../i18n";
import { haptic } from "../lib/session";

// The final exam is three sequential stages. Each word must be produced ≥ ROUNDS
// times within a stage, and the stage's mean score must reach PASS_AVG (= 80%) to
// unlock the next. All three passed → the batch is closed (l3_passed).
const ROUNDS = 2;
const PASS_AVG = 8; // out of 10 → 80%

type StageNum = 1 | 2 | 3;
type Stop = { anchor_id: string; start: number; end: number };

export default function Lesson3() {
  const { id } = useParams();
  const nav = useNavigate();
  const { t, tx } = useI18n();
  const player = usePlayer();
  const rec = useRecorder();

  const [batch, setBatch] = useState<Batch | null>(null);
  const [err, setErr] = useState("");
  const [notice, setNotice] = useState("");
  const [busy, setBusy] = useState(false);

  const [stage, setStage] = useState<StageNum>(1);
  const [running, setRunning] = useState(false);
  const [verdict, setVerdict] = useState<{ pass: boolean; pct: number } | null>(null);
  const [allDone, setAllDone] = useState(false);

  // Source of truth for the current stage's mean (refs survive audio callbacks).
  const stageRef = useRef<StageNum>(1);
  const scoresRef = useRef<number[]>([]);
  useEffect(() => { stageRef.current = stage; }, [stage]);

  // --- Stage 1: full retell ----------------------------------------------
  const [retellResult, setRetellResult] = useState<SequenceScore | null>(null);
  const [retellRound, setRetellRound] = useState(1);

  // --- Stage 2: story stops at each anchor, say its phrase ----------------
  const stopsRef = useRef<Stop[]>([]);
  const pendingRef = useRef(0); // index of the next stop within the current pass
  const roundRef = useRef(1);   // which full pass over the story (1..ROUNDS)
  const [stopTotal, setStopTotal] = useState(0);
  const [stopRound, setStopRound] = useState(1);
  const [answered, setAnswered] = useState(0);
  const [stopAnchor, setStopAnchor] = useState<string | null>(null);
  const [stopResult, setStopResult] = useState<PhraseScore | null>(null);
  const [replaySignal, setReplaySignal] = useState(0);

  // --- Stage 3: phrase → name the anchor ----------------------------------
  const order3Ref = useRef<Phrase[]>([]);
  const lastPlayedRef = useRef(-1);
  const [pos, setPos] = useState(0);
  const [anchorResult, setAnchorResult] = useState<AnchorScore | null>(null);

  // Pause at each stop end during stage 2; raise the prompt for that anchor.
  const onTick = useCallback((time: number, audio: HTMLAudioElement) => {
    if (stageRef.current !== 2) return;
    const stops = stopsRef.current;
    const i = pendingRef.current;
    if (i >= stops.length) return;
    if (time >= stops[i].end) {
      pendingRef.current = i + 1;
      audio.pause();
      setStopAnchor(stops[i].anchor_id);
    }
  }, []);

  // Story finished a pass: replay for round 2, otherwise grade the stage.
  const onStoryEnded = useCallback(() => {
    if (stageRef.current !== 2) return;
    if (roundRef.current < ROUNDS) {
      roundRef.current += 1;
      pendingRef.current = 0;
      setStopRound(roundRef.current);
      setReplaySignal((n) => n + 1);
      return;
    }
    const s = scoresRef.current;
    const avg = s.length ? s.reduce((a, b) => a + b, 0) / s.length : 0;
    setRunning(false);
    setStopAnchor(null);
    setVerdict({ pass: avg >= PASS_AVG, pct: Math.round(avg * 10) });
  }, []);

  const mnemo = useMnemoAudio(id ? Number(id) : undefined, onTick, onStoryEnded);

  // Round-2 replay (kept out of onStoryEnded so it can reach `mnemo`).
  useEffect(() => {
    if (replaySignal === 0) return;
    mnemo.seek(0);
    mnemo.resume();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [replaySignal]);

  useEffect(() => {
    if (!id) return;
    api.getBatch(Number(id)).then((b) => {
      setBatch(b);
      player.prefetchPhrases(b.phrases.map((p) => p.id));
    }).catch((e) => setErr(String(e)));
    mnemo.prefetch("full");
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [id]);

  // Resume the exam at the first not-yet-passed stage.
  useEffect(() => {
    if (!batch) return;
    const p = getProgress(batch.id);
    if (p.l3_passed) setAllDone(true);
    else if (p.l3_s2) setStage(3);
    else if (p.l3_s1) setStage(2);
    else setStage(1);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [batch]);

  // anchor_id → the phrase that sits on it (prompt label + scoring target).
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

  // Auto-play the English phrase when a fresh stage-3 prompt appears.
  useEffect(() => {
    if (stage !== 3 || !running || anchorResult) return;
    const cur = order3Ref.current[pos];
    if (!cur || lastPlayedRef.current === pos) return;
    lastPlayedRef.current = pos;
    player.playPhrase(cur.id);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [stage, running, pos, anchorResult]);

  const handleError = (e: unknown) => {
    const msg = String(e);
    if (msg.includes("429") || msg.toLowerCase().includes("limit")) {
      setNotice(t("rec.limit"));
    } else {
      setErr(msg);
    }
  };

  const finishStage = useCallback(() => {
    const s = scoresRef.current;
    const avg = s.length ? s.reduce((a, b) => a + b, 0) / s.length : 0;
    setRunning(false);
    setVerdict({ pass: avg >= PASS_AVG, pct: Math.round(avg * 10) });
  }, []);

  // ---- Stage 1 handlers --------------------------------------------------
  const startStage1 = useCallback(() => {
    setErr(""); setNotice(""); setRetellResult(null);
    scoresRef.current = [];
    setRetellRound(1);
    setRunning(true);
  }, []);

  const onMicRetell = useCallback(async () => {
    if (!batch) return;
    setErr("");
    if (!rec.recording) { setRetellResult(null); await rec.start(); return; }
    const clip = await rec.stop();
    if (!clip || clip.ms < 600) {
      setNotice(t("rec.mishearRetell"));
      return;
    }
    setBusy(true);
    try {
      const r = await api.scoreSequence(batch.id, clip.blob, clip.filename, clip.ms);
      scoresRef.current.push(r.score);
      setRetellResult(r);
    } catch (e) {
      handleError(e);
    } finally {
      setBusy(false);
    }
  }, [batch, rec]);

  const nextRetell = useCallback(() => {
    setRetellResult(null); setNotice("");
    if (scoresRef.current.length >= ROUNDS) finishStage();
    else setRetellRound((n) => n + 1);
  }, [finishStage]);

  // ---- Stage 2 handlers --------------------------------------------------
  const startStage2 = useCallback(async () => {
    setErr(""); setNotice(""); setStopResult(null); setStopAnchor(null);
    scoresRef.current = [];
    pendingRef.current = 0; roundRef.current = 1;
    setStopRound(1); setAnswered(0);
    setRunning(true);
    if (mnemo.layout === "full" && mnemo.planRef.current.length) {
      stopsRef.current = anchorSegments(mnemo.planRef.current);
      setStopTotal(stopsRef.current.length);
      mnemo.seek(0); mnemo.resume();
    } else {
      await mnemo.play("full");
      stopsRef.current = anchorSegments(mnemo.planRef.current);
      setStopTotal(stopsRef.current.length);
    }
  }, [mnemo]);

  const stopPhrase = stopAnchor ? phraseByAnchor.get(stopAnchor) ?? null : null;

  const onMicStop = useCallback(async () => {
    if (!stopPhrase) return;
    setErr("");
    if (!rec.recording) { setStopResult(null); await rec.start(); return; }
    const clip = await rec.stop();
    if (!clip || clip.ms < 600) {
      setNotice(t("rec.mishearLonger"));
      return;
    }
    setBusy(true);
    try {
      const r = await api.scorePhrase(stopPhrase.id, clip.blob, clip.filename, clip.ms);
      if (!r.transcript?.trim()) { setNotice(t("rec.mishearRetry")); return; }
      scoresRef.current.push(r.score);
      setAnswered((n) => n + 1);
      setStopResult(r);
    } catch (e) {
      handleError(e);
    } finally {
      setBusy(false);
    }
  }, [stopPhrase, rec]);

  const continueStops = useCallback(() => {
    setStopResult(null); setStopAnchor(null); setNotice("");
    mnemo.resume();
  }, [mnemo]);

  const skipStop = useCallback(() => {
    scoresRef.current.push(0); // a skipped anchor counts as 0
    setAnswered((n) => n + 1);
    setStopResult(null); setStopAnchor(null); setNotice("");
    mnemo.resume();
  }, [mnemo]);

  // ---- Stage 3 handlers --------------------------------------------------
  const startStage3 = useCallback(() => {
    setErr(""); setNotice(""); setAnchorResult(null);
    scoresRef.current = [];
    lastPlayedRef.current = -1;
    const sorted = [...(batch?.phrases ?? [])].sort((a, b) => a.order_index - b.order_index);
    order3Ref.current = [...sorted, ...sorted]; // each phrase ROUNDS times
    setPos(0);
    setRunning(true);
  }, [batch]);

  const cur3 = order3Ref.current[pos] ?? null;

  const onMicAnchor = useCallback(async () => {
    const c = order3Ref.current[pos];
    if (!c) return;
    setErr("");
    if (!rec.recording) { setAnchorResult(null); await rec.start(); return; }
    const clip = await rec.stop();
    if (!clip || clip.ms < 400) {
      setNotice(t("rec.mishearAnchor"));
      return;
    }
    setBusy(true);
    try {
      const r = await api.scoreAnchor(c.id, clip.blob, clip.filename, clip.ms);
      if (!r.transcript?.trim()) { setNotice(t("rec.mishearRetry")); return; }
      scoresRef.current.push(r.score);
      setAnchorResult(r);
    } catch (e) {
      handleError(e);
    } finally {
      setBusy(false);
    }
  }, [pos, rec]);

  const nextAnchor = useCallback(() => {
    setNotice("");
    if (pos + 1 >= order3Ref.current.length) { finishStage(); return; }
    setAnchorResult(null);
    setPos((p) => p + 1);
  }, [pos, finishStage]);

  // ---- Verdict transitions ----------------------------------------------
  const onVerdictForward = useCallback(() => {
    if (!batch) return;
    const s = stageRef.current;
    setVerdict(null);
    scoresRef.current = [];
    if (s === 1) { setProgress(batch.id, { l3_s1: true }); setStage(2); }
    else if (s === 2) { setProgress(batch.id, { l3_s2: true }); setStage(3); }
    else { setProgress(batch.id, { l3_passed: true }); setAllDone(true); }
  }, [batch]);

  const onVerdictRetake = useCallback(() => {
    setVerdict(null); setNotice("");
    scoresRef.current = [];
    setRunning(false); // back to the stage's intro card
  }, []);

  if (err) return <div className="screen"><p className="error">{err}</p></div>;
  if (!batch) return <div className="screen"><p className="muted">{t("common.loading")}</p></div>;

  const sub = allDone
    ? t("l3.subDone")
    : stage === 1 ? t("l3.sub1")
    : stage === 2 ? t("l3.sub2")
    : t("l3.sub3");

  return (
    <div className="screen l3-screen">
      <div className="l3-header">
        <button className="l3-iconbtn" onClick={() => nav(`/batch/${batch.id}`)} aria-label={t("common.back")}>
          <IconBack size={20} />
        </button>
        <button className="l3-iconbtn" onClick={() => nav(`/batch/${batch.id}`)} aria-label={t("l3.menuAria")}>
          <IconMenu size={20} />
        </button>
      </div>

      <div className="l3-hero">
        <div className="l3-hero-text">
          <span className="l3-tag">{t("lesson.tag", { n: 3 })}</span>
          <h1 className="l3-title">{t("bh.l3.title")}</h1>
          <p className="l3-sub">{sub}</p>
        </div>
        <Art3D />
      </div>

      <ExamTrack stage={stage} allDone={allDone} />

      {!rec.supported && (
        <div className="l3-warn">
          <span className="l3-warn-ic"><IconShield size={20} /></span>
          <p className="l3-warn-txt">
            {tx("rec.browserNoAudioRich", { safari: <b>Safari</b>, chrome: <b>Chrome</b> })}
          </p>
          <IconChevron size={18} />
        </div>
      )}
      {rec.error && <p className="error" style={{ marginTop: 12 }}>{rec.error}</p>}
      {notice && <p className="muted small" style={{ marginTop: 12 }}>{notice}</p>}

      {allDone ? (
        <DoneScreen onDone={() => nav(`/batch/${batch.id}`)} />
      ) : verdict ? (
        <VerdictCard stage={stage} verdict={verdict}
          onForward={onVerdictForward} onRetake={onVerdictRetake} />
      ) : stage === 1 ? (
        !running ? (
          <StageIntro
            n={1} title={t("l3.s1.title")}
            body={t("l3.s1.body")}
            onStart={startStage1}
          />
        ) : retellResult ? (
          <RetellResultCard
            result={retellResult} round={retellRound}
            onNext={nextRetell}
          />
        ) : (
          <>
            <div className="train-counter">{t("l3.retellCounter", { n: retellRound, total: ROUNDS })}</div>
            <p className="train-prompt sm" style={{ marginTop: 14 }}>{t("l3.retellPrompt")}</p>
            <p className="train-hint">
              {rec.recording
                ? t("l3.retellRecording")
                : t("l3.retellIdle", { n: batch.mnemo.spans.length })}
            </p>
            <RecFab recording={rec.recording} busy={busy} onClick={onMicRetell} />
            <p className="rec-label">
              {rec.recording ? t("rec.recordingStop") : busy ? t("rec.checking") : t("rec.tapAndSpeak")}
            </p>
          </>
        )
      ) : stage === 2 ? (
        !running ? (
          <StageIntro
            n={2} title={t("l3.s2.title")}
            body={t("l3.s2.body")}
            onStart={startStage2}
          />
        ) : stopAnchor && stopPhrase ? (
          <>
            <div className="train-counter">
              {t("l3.passCounter", { r: stopRound, rounds: ROUNDS, a: answered, total: stopTotal * ROUNDS })}
            </div>
            <p className="section-label center" style={{ marginTop: 4 }}>{t("l3.whichPhrase")}</p>
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
                  {rec.recording ? t("rec.recordingStop") : busy ? t("rec.checking") : t("rec.tapAndSpeak")}
                </p>
                <button className="btn btn-tint btn-block" style={{ marginTop: 14 }} onClick={skipStop}>
                  {t("common.skip")}
                </button>
              </>
            )}
          </>
        ) : (
          <div className="listening-note">
            <span className="pulse-dot" />
            <p className="train-hint" style={{ margin: 0 }}>
              {t("l3.listening", { a: answered, total: stopTotal * ROUNDS })}
            </p>
          </div>
        )
      ) : (
        // stage === 3
        !running ? (
          <StageIntro
            n={3} title={t("l3.s3.title")}
            body={t("l3.s3.body")}
            onStart={startStage3}
          />
        ) : cur3 ? (
          anchorResult ? (
            <AnchorResultCard result={anchorResult} onNext={nextAnchor} />
          ) : (
            <>
              <div className="train-counter">{pos + 1} / {order3Ref.current.length}</div>
              <p className="section-label center" style={{ marginTop: 4 }}>{t("l3.whichAnchor")}</p>
              <p className="train-prompt sm">{cur3.phrase_en}</p>
              <div className="mnemo-play" style={{ marginTop: 8 }}>
                <button className="mp-pill" onClick={() => player.playPhrase(cur3.id)}>
                  <IconPlay size={16} /> {t("l3.repeatPhrase")}
                </button>
              </div>
              <RecFab recording={rec.recording} busy={busy} onClick={onMicAnchor} />
              <p className="rec-label">
                {rec.recording ? t("rec.recordingStop") : busy ? t("rec.checking") : t("l3.sayAnchor")}
              </p>
            </>
          )
        ) : null
      )}

      <audio {...mnemo.bind} />
    </div>
  );
}

// Soft-3D matte-plastic speech bubble + pencil (green). Generated once via
// gpt-image-1, transparent PNG, optimized to ~160 KB / 480px (retina-crisp at
// its ~150px display size). Lives in /public/art so the app serves it at root.
function Art3D() {
  return (
    <div className="l3-art" aria-hidden="true">
      <img src="/art/lesson3-hero.png" alt="" width={480} height={407} />
    </div>
  );
}

// Decorative voice waveform at the foot of the task card — low-opacity green.
function WaveDeco() {
  const bars = [7, 13, 22, 11, 28, 17, 32, 15, 24, 10, 30, 19, 13, 26, 9, 21, 15, 32, 11, 18,
    24, 12, 28, 9, 19, 15, 26, 11, 22, 13];
  return (
    <svg className="l3-task-wave" viewBox="0 0 300 40" preserveAspectRatio="none" aria-hidden="true">
      <defs>
        <linearGradient id="l3wave" x1="0" y1="0" x2="1" y2="0">
          <stop offset="0" stopColor="#1C8C63" stopOpacity="0.04" />
          <stop offset="0.5" stopColor="#1C8C63" stopOpacity="0.34" />
          <stop offset="1" stopColor="#1C8C63" stopOpacity="0.04" />
        </linearGradient>
      </defs>
      {bars.map((h, i) => (
        <rect key={i} x={i * 10 + 2} y={20 - h / 2} width="4" height={h} rx="2" fill="url(#l3wave)" />
      ))}
    </svg>
  );
}

function ExamTrack({ stage, allDone }: { stage: StageNum; allDone: boolean }) {
  const { t } = useI18n();
  const titles = [t("l3.track.retell"), t("l3.track.mnemo"), t("l3.track.anchor")];
  const state = (n: StageNum) =>
    allDone || stage > n ? "done" : stage === n ? "on" : "";
  const Step = ({ n }: { n: StageNum }) => {
    const st = state(n);
    return (
      <div className={`l3-step ${st}`}>
        <span className="l3-step-circle">
          {st === "done" ? <IconCheck size={18} /> : n}
          {st === "on" && <span className="l3-step-play"><IconPlay size={9} /></span>}
        </span>
        <span className="l3-step-label">{titles[n - 1]}</span>
      </div>
    );
  };
  return (
    <div className="l3-track">
      <Step n={1} />
      <span className="l3-track-line" />
      <Step n={2} />
      <span className="l3-track-line" />
      <Step n={3} />
    </div>
  );
}

function StageIntro({
  n, title, body, onStart,
}: { n: number; title: string; body: string; onStart: () => void }) {
  const { t } = useI18n();
  return (
    <>
      <div className="l3-task">
        <div className="l3-task-head">
          <span className="l3-task-ic"><IconWave size={16} /></span>
          <span className="l3-task-label">{t("l3.stageLabel", { n, title })}</span>
        </div>
        <p className="l3-task-body">{body}</p>
        <WaveDeco />
      </div>
      <button className="l3-cta" onClick={onStart}>
        <IconPlay size={18} /> {t("l3.startStage", { n })}
      </button>
      <p className="l3-hint">
        <IconHeadphones size={15} /> {t("common.headphones")}
      </p>
    </>
  );
}

function VerdictCard({
  stage, verdict, onForward, onRetake,
}: {
  stage: StageNum;
  verdict: { pass: boolean; pct: number };
  onForward: () => void;
  onRetake: () => void;
}) {
  const { t } = useI18n();
  useEffect(() => { haptic(verdict.pass ? "success" : "error"); }, [verdict.pass]);
  return (
    <div className="result-card">
      <div className={`verdict-pct ${verdict.pass ? "ok" : "no"}`}>
        {verdict.pct}<span className="score-out">%</span>
      </div>
      <div className="center" style={{ marginBottom: 14 }}>
        <span className={`pass-pill ${verdict.pass ? "ok" : "no"}`}>
          {verdict.pass
            ? <><IconCheck size={15} /> {t("l3.stagePassed", { n: stage })}</>
            : t("l3.need80")}
        </span>
      </div>
      {verdict.pass ? (
        <button className="btn btn-primary train-cta" onClick={onForward}>
          {stage === 3 ? t("l3.finish") : t("common.next")}
        </button>
      ) : (
        <button className="btn btn-primary train-cta" onClick={onRetake}>{t("l3.retake")}</button>
      )}
    </div>
  );
}

function DoneScreen({ onDone }: { onDone: () => void }) {
  const { t } = useI18n();
  return (
    <div className="result-card" style={{ textAlign: "center" }}>
      <div className="score-badge hi" style={{ paddingTop: 0, alignItems: "center" }}>
        <IconCheck size={40} />
      </div>
      <p className="train-prompt sm" style={{ marginTop: 4 }}>{t("l3.batchClosed")}</p>
      <p className="train-hint">{t("l3.doneBody")}</p>
      <button className="btn btn-primary train-cta" onClick={onDone}>{t("common.done")}</button>
    </div>
  );
}

function RetellResultCard({
  result, round, onNext,
}: { result: SequenceScore; round: number; onNext: () => void }) {
  const { t } = useI18n();
  const last = round >= ROUNDS;
  return (
    <div className="result-card">
      <div className={`score-badge ${band(result.score)}`}>
        {result.score}<span className="score-out">/10</span>
      </div>
      {result.missed_anchors.length > 0 && (
        <div className="result-row">
          <div className="result-k">{t("res.missedAnchors")}</div>
          <div className="miss-chips">
            {result.missed_anchors.map((a, i) => <span className="miss-chip" key={i}>{a}</span>)}
          </div>
        </div>
      )}
      <div className="result-row">
        <div className="result-k">{t("res.order")}</div>
        <div className="result-v">{result.order_ok ? t("res.orderOk") : t("res.orderBroken")}</div>
      </div>
      <div className="result-row">
        <div className="result-k">{t("res.weHeard")}</div>
        <div className="result-v heard">{result.transcript || t("res.silence")}</div>
      </div>
      <button className="btn btn-primary train-cta" onClick={onNext}>
        {last ? t("l3.summarize") : t("l3.moreRetell")}
      </button>
    </div>
  );
}

function StopResult({
  result, onNext, onPlayCorrect,
}: { result: PhraseScore; onNext: () => void; onPlayCorrect: () => void }) {
  const { t } = useI18n();
  return (
    <div className="result-card">
      <div className={`score-badge ${band(result.score)}`}>
        {result.score}<span className="score-out">/10</span>
      </div>
      <div className="result-row">
        <div className="result-k">{t("res.correctPhrase")}</div>
        <div className="result-v">
          {result.correct_phrase}
          <button className="inline-play" onClick={onPlayCorrect} aria-label={t("res.playAria")}>
            <IconPlay size={15} />
          </button>
        </div>
      </div>
      <div className="result-row">
        <div className="result-k">{t("res.weHeard")}</div>
        <div className="result-v heard">{result.transcript || t("res.silence")}</div>
      </div>
      <button className="btn btn-primary train-cta" onClick={onNext}>{t("common.next")}</button>
    </div>
  );
}

function AnchorResultCard({
  result, onNext,
}: { result: AnchorScore; onNext: () => void }) {
  const { t } = useI18n();
  return (
    <div className="result-card">
      <div className={`score-badge ${band(result.score)}`}>
        {result.score}<span className="score-out">/10</span>
      </div>
      <div className="result-row">
        <div className="result-k">{t("res.correctAnchor")}</div>
        <div className="result-v">{result.correct_anchor}</div>
      </div>
      <div className="result-row">
        <div className="result-k">{t("res.weHeard")}</div>
        <div className="result-v heard">{result.transcript || t("res.silence")}</div>
      </div>
      <button className="btn btn-primary train-cta" onClick={onNext}>{t("common.next")}</button>
    </div>
  );
}
