import { useEffect, useMemo, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api, BattleItem, BattlePick } from "../api";
import { useAuth } from "../auth/AuthContext";
import { useI18n } from "../i18n";
import { useSpeech } from "../audio/useSpeech";
import { nativeRecognize, nativeSttAvailable, nativeSttStop } from "../audio/nativeStt";
import { syncWidget } from "../lib/widget";
import { IconMic, IconPlay, IconLock } from "../ui/icons";

// Live mode («Live»): the user is IN a live conversation and needs the right
// trained line NOW. Everything is built for speed:
// - the corpus (their study set) is cached in localStorage → typing gives
//   instant, fully-OFFLINE keyword results (also the degradation path);
// - AI plan: dictate the moment in a glass recording panel with explicit
//   states (Listening → Thinking → results), and one fast LLM call picks the
//   best line on top of the local search.
const CACHE_KEY = (uid: number) => `ee-battle-corpus:${uid}`;
const TOP_N = 6;

const norm = (s: string) => (s || "").toLowerCase().replace(/ё/g, "е");
const toks = (q: string) =>
  norm(q).split(/[^a-zа-я0-9']+/i).filter((t) => t.length >= 2);

const SRS_BOOST: Record<string, number> = { automatic: 1.5, familiar: 1.2, shaky: 0.8 };
const LEARNED = new Set(["familiar", "automatic"]);

function rank(it: BattleItem, tt: string[]): number {
  let s = 0;
  for (const t of tt) {
    if (norm(it.anchor).includes(t)) s += 3;
    if (norm(it.phrase_en).includes(t)) s += 2;
    if (norm(it.gloss_ru).includes(t)) s += 2;
    if (norm(it.situation_ru).includes(t)) s += 1;
    if (norm(it.batch_title).includes(t)) s += 0.5;
  }
  if (s === 0) return 0;                      // must actually match the query
  s += SRS_BOOST[it.srs_status] ?? 0;         // trained lines float up
  if (it.attempts > 0) s += 0.3;
  return s;
}

function loadCache(uid: number): BattleItem[] {
  try {
    const raw = localStorage.getItem(CACHE_KEY(uid));
    const arr = raw ? JSON.parse(raw) : null;
    return Array.isArray(arr) ? arr : [];
  } catch { return []; }
}

// idle → listening (recording panel up) → thinking (AI picking) → idle.
type MicState = "idle" | "listening" | "thinking";

export default function Battle() {
  const nav = useNavigate();
  const { t } = useI18n();
  const { user } = useAuth();
  const uid = user?.id ?? 0;
  const isAI = user?.plan === "ai";
  const speech = useSpeech();

  const [corpus, setCorpus] = useState<BattleItem[]>(() => loadCache(uid));
  const [loaded, setLoaded] = useState(false);     // fresh server copy arrived
  const [q, setQ] = useState("");
  const [open, setOpen] = useState<number | null>(null);   // expanded phrase_id
  const [mic, setMic] = useState<MicState>("idle");
  const [heard, setHeard] = useState("");          // native partial/final transcript
  const [ai, setAi] = useState<BattlePick[] | null>(null);
  const [aiNote, setAiNote] = useState("");        // fallback/limit/empty note
  const nativeStt = useRef(false);
  const cancelled = useRef(false);

  // Cache-first, then refresh: the screen must be usable the instant it opens
  // (and fully offline — the refresh just quietly fails).
  useEffect(() => {
    let on = true;
    api.battleCorpus()
      .then((items) => {
        if (!on) return;
        setCorpus(items);
        setLoaded(true);
        try { localStorage.setItem(CACHE_KEY(uid), JSON.stringify(items)); } catch { /* full */ }
        void syncWidget(items);   // fresh corpus in hand → refresh the lock-screen widget
      })
      .catch(() => { if (on) setLoaded(true); });
    return () => { on = false; };
  }, [uid]);

  const results = useMemo(() => {
    const tt = toks(q);
    if (!tt.length) {
      // Idle screen = your strongest lines, ready to fire.
      return corpus.filter((it) => LEARNED.has(it.srs_status)).slice(0, TOP_N);
    }
    return corpus
      .map((it) => [rank(it, tt), it] as const)
      .filter(([s]) => s > 0)
      .sort((a, b) => b[0] - a[0])
      .slice(0, TOP_N)
      .map(([, it]) => it);
  }, [corpus, q]);
  const idle = toks(q).length === 0;

  const play = (pid: number, e?: React.MouseEvent) => {
    e?.stopPropagation();
    api.phraseAudio(pid)
      .then((r) => { new Audio(r.audio_url).play().catch(() => { /* locked */ }); })
      .catch(() => { /* offline — text is already on screen */ });
  };

  // Stop the recognizer — this resolves the pending nativeRecognize/speech.start
  // promise in startVoice, which then flows on to the AI step (or cancel).
  const stopRecognition = () => {
    if (nativeStt.current) nativeSttStop().catch(() => { /* noop */ });
    else speech.stop();
  };

  const runSuggest = async (text: string) => {
    setQ(text);
    setMic("thinking");
    try {
      const r = await api.battleSuggest(text);
      if (r.via === "llm") setAi(r.picks);
      else if (r.via === "fallback") setAiNote(t("battle.aiUnavailable"));
      // via === "empty" → the cold-start block below already explains
    } catch (e) {
      setAiNote(String(e).includes("429") ? t("practice.limitReached")
        : t("battle.aiUnavailable"));
    } finally { setMic("idle"); setHeard(""); }
  };

  const startVoice = async () => {
    if (!isAI) { nav("/subscribe"); return; }
    if (mic !== "idle") return;
    cancelled.current = false;
    setAi(null); setAiNote(""); setHeard("");
    setMic("listening");
    let text = "";
    try {
      nativeStt.current = await nativeSttAvailable();
      if (nativeStt.current) text = await nativeRecognize("ru-RU", setHeard);
      else if (speech.supported) text = await speech.start("ru-RU");
      else { setMic("idle"); setAiNote(t("battle.micUnsupported")); return; }
    } catch { /* denied / no-speech → user can just type */ }
    if (cancelled.current) { setMic("idle"); setHeard(""); return; }
    text = (text || "").trim();
    if (!text) { setMic("idle"); setHeard(""); setAiNote(t("battle.recEmpty")); return; }
    await runSuggest(text);
  };

  const finishVoice = () => stopRecognition();   // "Done": stop → transcript → AI
  const cancelVoice = () => {                     // discard: close panel, no AI call
    cancelled.current = true;
    stopRecognition();
    setMic("idle");
    setHeard("");
  };

  // Live words while recording: Web Speech feeds `interim`, native feeds `heard`.
  const liveText = speech.interim || heard;

  const card = (it: { phrase_id: number; batch_id: number; anchor: string;
                      phrase_en: string; gloss_ru: string; srs_status: string },
                extra?: { note?: string; best?: boolean; situation?: string }) => (
    <div
      key={`${extra?.best ? "b" : "r"}${it.phrase_id}`}
      className={`bm-card${extra?.best ? " best" : ""}`}
      onClick={() => setOpen(open === it.phrase_id ? null : it.phrase_id)}
    >
      <div className="bm-top">
        <span className="bm-anchor">{it.anchor}</span>
        {LEARNED.has(it.srs_status) && <span className="bm-badge">{t("battle.learned")}</span>}
        <button className="bm-play" aria-label="Play" onClick={(e) => play(it.phrase_id, e)}>
          <IconPlay size={16} />
        </button>
      </div>
      <div className="bm-phrase">{it.phrase_en}</div>
      {it.gloss_ru && <div className="bm-gloss">{it.gloss_ru}</div>}
      {extra?.note && <div className="bm-note">{extra.note}</div>}
      {open === it.phrase_id && (
        <div className="bm-more" onClick={(e) => e.stopPropagation()}>
          {extra?.situation && <p className="bm-situ">{extra.situation}</p>}
          <button className="bm-open" onClick={() => nav(`/batch/${it.batch_id}`)}>
            {t("battle.openBatch")}
          </button>
        </div>
      )}
    </div>
  );

  const situOf = (pid: number) => corpus.find((c) => c.phrase_id === pid)?.situation_ru;
  const empty = loaded && corpus.length === 0;

  return (
    <div className="screen bm-screen">
      <div className="screen-head">
        <h1>{t("battle.title")}</h1>
        <p className="app-sub" style={{ marginBottom: 0 }}>{t("battle.sub")}</p>
      </div>

      <div className="bm-row">
        <input
          className="bm-input"
          type="search"
          enterKeyHint="search"
          placeholder={t("battle.placeholder")}
          value={q}
          onChange={(e) => { setQ(e.target.value); setAi(null); setAiNote(""); }}
        />
        <button
          className={`bm-mic${mic !== "idle" ? " on" : ""}${isAI ? "" : " locked"}`}
          aria-label={isAI ? t("battle.micHint") : t("battle.micLocked")}
          onClick={startVoice}
        >
          {isAI ? <IconMic size={26} /> : <IconLock size={22} />}
        </button>
      </div>
      {!isAI && <p className="bm-hint" onClick={() => nav("/subscribe")}>{t("battle.micLocked")}</p>}
      {isAI && mic === "idle" && !ai && !aiNote && <p className="bm-hint">{t("battle.micHint")}</p>}
      {aiNote && <p className="bm-hint warn">{aiNote}</p>}

      {empty ? (
        <div className="bm-empty">
          <p>{t("battle.empty")}</p>
          <button className="btn-primary" onClick={() => nav("/")}>{t("battle.toLibrary")}</button>
        </div>
      ) : (
        <>
          {ai && ai.length > 0 && (
            <>
              <div className="bm-sect">{t("battle.aiBest")}</div>
              {card(ai[0], { note: ai[0].note, best: true, situation: situOf(ai[0].phrase_id) })}
              {ai.length > 1 && <div className="bm-sect">{t("battle.aiAlts")}</div>}
              {ai.slice(1).map((p) => card(p, { note: p.note, situation: situOf(p.phrase_id) }))}
            </>
          )}
          <div className="bm-sect">
            {idle ? t("battle.ready") : t("battle.matches")}
          </div>
          {results.length === 0 && (
            <p className="bm-hint">{idle ? t("battle.readyEmpty") : t("battle.noResults")}</p>
          )}
          {results.map((it) => card(it, { situation: it.situation_ru }))}
        </>
      )}

      {/* Recording panel — the same card glass, centered, with explicit states.
          Tap the backdrop or "Cancel" to discard; "Done" stops and sends. */}
      {mic !== "idle" && (
        <div className="bm-rec-overlay" onClick={cancelVoice}>
          <div className="bm-rec-panel" onClick={(e) => e.stopPropagation()}>
            {mic === "listening" ? (
              <>
                <div className="bm-rec-orb" aria-hidden="true"><IconMic size={34} /></div>
                <div className="bm-rec-title">{t("battle.listening")}</div>
                <div className={`bm-rec-transcript${liveText ? "" : " placeholder"}`}>
                  {liveText || t("battle.recHint")}
                </div>
                <button className="bm-rec-done" onClick={finishVoice}>{t("battle.recDone")}</button>
                <button className="bm-rec-cancel" onClick={cancelVoice}>{t("battle.recCancel")}</button>
              </>
            ) : (
              <>
                <div className="bm-rec-spinner" aria-hidden="true" />
                <div className="bm-rec-title">{t("battle.aiThinking")}</div>
                {(q || heard) && <div className="bm-rec-transcript quiet">«{q || heard}»</div>}
              </>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
