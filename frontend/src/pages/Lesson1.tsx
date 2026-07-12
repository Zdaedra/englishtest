import { useCallback, useEffect, useMemo, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { api, BatchDetail as Batch, SequenceScore } from "../api";
import { useMnemoAudio, MnemoLayout } from "../audio/useMnemoAudio";
import { useRecorder } from "../audio/useRecorder";
import { usePlayer } from "../player/PlayerContext";
import { getProgress, setProgress } from "../lib/progress";
import { RecFab, band } from "../ui/RecFab";
import { IconBack, IconCheck, IconChevron, IconPause, IconPlay } from "../ui/icons";
import { useI18n } from "../i18n";

export default function Lesson1() {
  const { id } = useParams();
  const nav = useNavigate();
  const { t } = useI18n();
  const player = usePlayer();
  const mnemo = useMnemoAudio(id ? Number(id) : undefined);
  const rec = useRecorder();

  const [batch, setBatch] = useState<Batch | null>(null);
  const [err, setErr] = useState("");
  const [revealed, setRevealed] = useState<Set<string>>(new Set());
  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState<SequenceScore | null>(null);
  const [notice, setNotice] = useState("");

  useEffect(() => {
    if (!id) return;
    api.getBatch(Number(id)).then((b) => {
      setBatch(b);
      player.prefetchPhrases(b.phrases.map((p) => p.id));
    }).catch((e) => setErr(String(e)));
    mnemo.prefetch("full");
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [id]);

  const spans = useMemo(
    () => (batch ? [...batch.mnemo.spans].sort((a, b) => a.start - b.start) : []),
    [batch]
  );
  const phraseById = useMemo(() => {
    const m = new Map<number, Batch["phrases"][number]>();
    batch?.phrases.forEach((p) => m.set(p.id, p));
    return m;
  }, [batch]);

  const handleError = (e: unknown) => {
    const msg = String(e);
    if (msg.includes("429") || msg.toLowerCase().includes("limit")) {
      setNotice(t("rec.limit"));
    } else {
      setErr(msg);
    }
  };

  const playLayout = (l: MnemoLayout) => {
    if (batch) setProgress(batch.id, { l1_listened: true });
    setNotice("");
    void mnemo.play(l);
  };

  // One tap toggles record → stop+score (the soft retell). iOS needs the mic
  // request inside the user gesture.
  const onMic = useCallback(async () => {
    if (!batch) return;
    setErr("");
    if (!rec.recording) {
      setResult(null);
      await rec.start();
      return;
    }
    const clip = await rec.stop();
    if (!clip) return;
    setBusy(true);
    try {
      const r = await api.scoreSequence(batch.id, clip.blob, clip.filename, clip.ms);
      setResult(r);
      const best = Math.max(getProgress(batch.id).l1_best_seq ?? 0, r.score);
      setProgress(batch.id, { l1_retold: true, l1_best_seq: best });
    } catch (e) {
      handleError(e);
    } finally {
      setBusy(false);
    }
  }, [batch, rec]);

  if (err) return <div className="screen"><p className="error">{err}</p></div>;
  if (!batch) return <div className="screen"><p className="muted">{t("common.loading")}</p></div>;

  const story = batch.mnemo.story_ru;

  // Render the mnemonic sentence with tappable anchor spans + karaoke highlight.
  const pieces: JSX.Element[] = [];
  let cursor = 0;
  spans.forEach((sp, i) => {
    if (sp.start > cursor) pieces.push(<span key={`t${i}`}>{story.slice(cursor, sp.start)}</span>);
    const text = story.slice(sp.start, sp.end);
    const ph = phraseById.get(sp.phrase_id);
    const open = revealed.has(sp.anchor_id);
    pieces.push(
      <span key={sp.anchor_id} className="anchor-wrap">
        <button
          className={`anchor${mnemo.activeAnchor === sp.anchor_id ? " on" : ""}`}
          onClick={() =>
            setRevealed((prev) => {
              const n = new Set(prev);
              n.has(sp.anchor_id) ? n.delete(sp.anchor_id) : n.add(sp.anchor_id);
              return n;
            })
          }
        >
          {text}
        </button>
        {open && ph && <span className="reveal">{ph.phrase_en}</span>}
      </span>
    );
    cursor = sp.end;
  });
  if (cursor < story.length) pieces.push(<span key="tail">{story.slice(cursor)}</span>);

  const pill = (l: MnemoLayout, label: string) => (
    <button
      className={`mp-pill${mnemo.layout === l ? " on" : ""}`}
      disabled={mnemo.loading !== null}
      onClick={() => playLayout(l)}
    >
      {mnemo.layout === l && mnemo.playing ? <IconPause size={16} /> : <IconPlay size={16} />}
      {mnemo.loading === l ? "…" : label}
    </button>
  );

  return (
    <div className="screen">
      <button className="back-link" onClick={() => nav(`/batch/${batch.id}`)}>
        <IconBack /> {batch.title}
      </button>

      <div className="screen-head">
        <span className="lesson-tag">{t("lesson.tag", { n: 1 })}</span>
        <h1>{t("bh.l1.title")}</h1>
        <p className="app-sub" style={{ marginBottom: 0 }}>{t("l1.lead")}</p>
      </div>

      <p className="section-label" style={{ marginTop: 18 }}>{t("l1.step1")}</p>
      <div className="mnemo-play">
        {pill("full", t("l1.playFull"))}
        {pill("anchors", t("l1.playOrder"))}
      </div>

      <div className="card-block" style={{ marginTop: 12 }}>
        <div className="story">{pieces}</div>
      </div>

      <p className="section-label" style={{ marginTop: 22 }}>{t("l1.step2")}</p>
      <p className="train-hint" style={{ marginTop: 4 }}>
        {rec.recording ? t("l1.retellRecording") : t("l1.retellIdle")}
      </p>

      {!rec.supported && (
        <p className="error" style={{ marginTop: 12 }}>{t("rec.browserNoAudio")}</p>
      )}
      {rec.error && <p className="error" style={{ marginTop: 12 }}>{rec.error}</p>}
      {notice && <p className="muted small" style={{ marginTop: 12 }}>{notice}</p>}

      {result ? (
        <RetellResult result={result} onAgain={() => setResult(null)} />
      ) : (
        <>
          <RecFab recording={rec.recording} busy={busy} onClick={onMic} />
          <p className="rec-label">{rec.recording ? t("rec.stop") : busy ? t("rec.checking") : t("rec.record")}</p>
        </>
      )}

      <button className="btn btn-primary btn-block" style={{ marginTop: 24 }}
        onClick={() => nav(`/batch/${batch.id}/lesson/2`)}>
        {t("l1.next")} <IconChevron size={16} />
      </button>

      <audio {...mnemo.bind} />
    </div>
  );
}

function RetellResult({ result, onAgain }: { result: SequenceScore; onAgain: () => void }) {
  const { t } = useI18n();
  return (
    <div className="result-card">
      <div className={`score-badge ${band(result.score)}`}>
        {result.score}<span className="score-out">/10</span>
      </div>

      {result.passed && (
        <div className="center" style={{ marginBottom: 12 }}>
          <span className="pass-pill ok"><IconCheck size={15} /> {t("res.frameStrong")}</span>
        </div>
      )}

      {result.missed_anchors.length > 0 && (
        <div className="result-row">
          <div className="result-k">{t("res.forgotAnchors")}</div>
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

      <button className="btn btn-tint train-cta" onClick={onAgain}>{t("common.again")}</button>
    </div>
  );
}
