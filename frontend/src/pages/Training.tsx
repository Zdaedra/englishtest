import { useCallback, useEffect, useLayoutEffect, useMemo, useRef, useState } from "react";
import { useNavigate, useLocation } from "react-router-dom";
import { api, DeckCard, AnswerResult, SessionSummary } from "../api";
import { ModelPhrase } from "../ui/ModelPhrase";
import { useAuth } from "../auth/AuthContext";
import { useI18n } from "../i18n";
import { useTeach } from "../tutorial/teach";
import { useRecorder } from "../audio/useRecorder";
import { useSpeech } from "../audio/useSpeech";
import { nativeRecognize, nativeSttStop } from "../audio/nativeStt";
import { useHandsFree } from "../audio/useHandsFree";
import { speakCueAudio, cancelSpeak, unlockAudio, prefetchCueAudio } from "../lib/speak";
import { getProgress } from "../lib/progress";
import { haptic, isNative } from "../lib/session";
import { SECTION_BY_SLUG } from "../lib/sections";
import { BatchCover } from "../ui/Art";
import { IconPlay, IconMic } from "../ui/icons";

// Two-face card: the prompt, then the back. The back's content depends on plan —
// AI gets a mic (records → scored), non-AI gets the model phrase (эталон). Both
// self-assess with the «guessed / missed» buttons at the bottom.
type Face = "front" | "back";
const SESSION_LEN = 12;
const FETCH_LIMIT = 24;

// After this many COMPLETED reps (cumulative, per user) the card stops showing
// the gesture hint — they know it by now. Counted on answer-complete, never on
// tap, so the no-flip AI flow still retires the hint.
const HINT_REPS = 8;
const swipeKey = (uid?: number) => `ee-swipes-${uid ?? 0}`;
const getSwipes = (uid?: number) => {
  try { return Number(localStorage.getItem(swipeKey(uid))) || 0; } catch { return 0; }
};
const bumpSwipes = (uid?: number) => {
  const n = getSwipes(uid) + 1;
  try { localStorage.setItem(swipeKey(uid), String(n)); } catch { /* non-critical */ }
  return n;
};

const PILL: Record<string, string> = {
  "live-tone": "Disagreement", pitch: "Pitch", negotiation: "Negotiation",
  pressure: "Under Pressure", repair: "Repair", leadership: "Leadership",
  requests: "Requests", written: "Written", "small-talk": "Small Talk",
  charisma: "Charisma", flirt: "Attraction", intimacy: "Intimacy",
  "lead-presence": "Leadership", composure: "Composure", gravitas: "Gravitas",
  stage: "Stage",
};
const pillLabel = (c: DeckCard) =>
  PILL[c.section] || SECTION_BY_SLUG[c.section]?.en || c.batch_title || "Executive";

const prefersReduced = () =>
  typeof matchMedia !== "undefined" && matchMedia("(prefers-reduced-motion: reduce)").matches;

function newSessionId(): string {
  try { return crypto.randomUUID(); } catch { return `s-${Date.now()}-${Math.floor(Math.random() * 1e6)}`; }
}

function deckSources(): { active: number[]; maint: number[] } {
  const active: number[] = [];
  const maint: number[] = [];
  try {
    for (let i = 0; i < localStorage.length; i++) {
      const k = localStorage.key(i);
      if (!k || !k.startsWith("ee-progress-")) continue;
      const id = Number(k.slice("ee-progress-".length));
      if (Number.isNaN(id)) continue;
      const p = getProgress(id);
      if (!p.activated) continue;        // deck = activated set (active ⊆ on_path)
      (p.l3_passed ? maint : active).push(id);
    }
  } catch { /* ignore */ }
  return { active, maint };
}

// What the hands-free voice reads: the RU situation when generated (the learner
// hears the scene in Russian, then produces English), else the legacy stimulus.
function cueOf(c: DeckCard): [string, string] {
  return c.situation_ru
    ? [c.situation_ru, "ru"]
    : [c.stimulus || c.gloss_ru || c.anchor, c.stimulus_lang || "en"];
}

function Head({ title }: { title?: string }) {
  const { t } = useI18n();
  return (
    <div className="screen-head tr-head">
      <span className="tr-eyebrow">{t("practice.eyebrow")}</span>
      <h1>{title || t("practice.title")}</h1>
      <p className="app-sub" style={{ marginBottom: 0 }}>{t("practice.headSub")}</p>
    </div>
  );
}

export default function Training() {
  const nav = useNavigate();
  const loc = useLocation();
  // Review mode (opened from the home "to refresh" card): a pure due-only session
  // drawing from every engaged batch, not just the current sprint.
  const review = !!(loc.state as { review?: boolean } | null)?.review;
  // Confidence-check mode (from the Learning "calibration gap" card): drill only
  // phrases swiped "known" but not produced aloud, across every engaged batch.
  const gap = !!(loc.state as { gap?: boolean } | null)?.gap;
  const { user } = useAuth();
  const { t } = useI18n();
  const uid = user?.id;
  const rec = useRecorder();
  const speech = useSpeech();
  const hf = useHandsFree();
  // Hands-free (Pimsleur-style) loop: speak the cue → record → score → advance,
  // all on one mic stream opened by the toggle tap (iOS needs a gesture once).
  const [handsFree, setHandsFree] = useState(false);
  const [hfStage, setHfStage] = useState<"cue" | "listen" | "score" | "">("");
  const hfRunningRef = useRef<number | null>(null);

  const [queue, setQueue] = useState<DeckCard[] | null>(null);
  const [pos, setPos] = useState(0);
  const [phase, setPhase] = useState<"loading" | "empty" | "deck" | "summary" | "error">("loading");
  const [err, setErr] = useState("");
  const [notice, setNotice] = useState("");

  const [sessionId, setSessionId] = useState(newSessionId);
  const shownRef = useRef(0);
  const knownRef = useRef(0);
  const shownAtRef = useRef(Date.now());

  const [face, setFace] = useState<Face>("front");
  const [experienced, setExperienced] = useState(() => getSwipes(uid) >= HINT_REPS);
  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState<AnswerResult | null>(null);
  const [recFallback, setRecFallback] = useState(false);
  const [nativeListening, setNativeListening] = useState(false);
  // Contextual method hints (fire-once): the meaning-scoring reframe at the first
  // score, and the spaced-repetition reassurance when a refresh session first opens.
  const { tip } = useTeach();
  useEffect(() => { if (result && typeof result.score === "number") tip("meaning"); }, [result, tip]);
  useEffect(() => { if (review) tip("spacing"); }, [review, tip]);
  const [summary, setSummary] = useState<SessionSummary | null>(null);

  // Voice→AI consent (Apple §5.1.2(i) + GDPR): a one-time gate before the first
  // recording, since the clip + transcript go to OpenAI/Anthropic. Local flag gates
  // the UI; the server gets an append-only audit record.
  const [showVoiceConsent, setShowVoiceConsent] = useState(false);
  const voiceConsentKey = uid != null ? `ee-voice-consent-${uid}` : null;
  const hasVoiceConsent = () => {
    try { return !!voiceConsentKey && localStorage.getItem(voiceConsentKey) === "1"; }
    catch { return false; }
  };
  const acceptVoiceConsent = () => {
    try { if (voiceConsentKey) localStorage.setItem(voiceConsentKey, "1"); } catch { /* private */ }
    api.recordConsent("voice_ai").catch(() => {});   // server audit (best-effort)
    setShowVoiceConsent(false);
  };

  const cardElRef = useRef<HTMLDivElement>(null);
  const innerRef = useRef<HTMLDivElement>(null);
  const bodyRef = useRef<HTMLDivElement>(null);
  const fitRef = useRef<HTMLDivElement>(null);

  const sources = useMemo(deckSources, []);
  const card = queue && pos < queue.length ? queue[pos] : null;

  const loadDeck = useCallback(() => {
    const { active, maint } = sources;
    // Review / confidence-check: draw from EVERY engaged batch (active + completed).
    const wide = review || gap;
    const batchIds = wide ? [...new Set([...active, ...maint])] : (active.length ? active : maint);
    const maintenanceIds = wide ? [] : (active.length ? maint : []);
    if (!batchIds.length) { setPhase("empty"); setQueue([]); return; }
    setPhase("loading");
    api.getDeck(batchIds, { maintenanceIds, limit: FETCH_LIMIT, dueOnly: review, gapOnly: gap })
      .then((d) => { setQueue(d); setPhase(d.length ? "deck" : "empty"); shownAtRef.current = Date.now(); })
      .catch((e) => { setErr(String(e)); setPhase("error"); });
  }, [sources, review, gap]);

  useEffect(() => { loadDeck(); }, [loadDeck]);
  useEffect(() => { shownAtRef.current = Date.now(); }, [pos]);

  // AI Coach fetch is DISABLED — the redesigned result shows only score + native
  // phrase (product call 2026-06-21), so the coaching breakdown was no longer
  // rendered and the per-answer api.coach() call was pure wasted LLM spend.
  // To restore: re-add the effect below and render coach/coachState in the result.
  //   useEffect(() => {
  //     if (!result || user?.plan !== "ai") return;
  //     setCoach(null); setCoachState("loading");
  //     api.coach(result.phrase_id, result.transcript, result.score)
  //       .then((r) => { if ("locked" in r) setCoachState("locked"); else { setCoach(r); setCoachState("done"); } })
  //       .catch(() => setCoachState("idle"));
  //   }, [result]);

  // Edge-flip with content swap — no backface-visibility (which iOS Safari leaves
  // mirrored "inside-out"). Rotate to 90° (edge), swap content, rotate back from -90°.
  // Edge-flip with content swap, timer-driven (not Animation.finished, which can
  // stall in a backgrounded/headless tab). Cancel prior anims so repeated flips
  // on the same card don't stack and stick at 90°.
  const flip = (to: Face) => {
    const el = innerRef.current;
    if (!el || prefersReduced()) { setFace(to); return; }
    el.getAnimations().forEach((a) => a.cancel());
    el.animate([{ transform: "rotateY(0deg)" }, { transform: "rotateY(90deg)" }],
      { duration: 150, easing: "cubic-bezier(.4,0,.2,1)", fill: "forwards" });
    window.setTimeout(() => {
      setFace(to);
      el.animate([{ transform: "rotateY(-90deg)" }, { transform: "rotateY(0deg)" }],
        { duration: 200, easing: "cubic-bezier(.22,1,.36,1)", fill: "forwards" });
      window.setTimeout(() => { if (innerRef.current) innerRef.current.style.transform = ""; }, 210);
    }, 150);
  };

  const leaveCard = (dir: "left" | "right", after: () => void) => {
    const el = cardElRef.current;
    if (!el || prefersReduced()) { after(); return; }
    el.getAnimations().forEach((a) => a.cancel());
    const x = dir === "right" ? 1 : -1;
    el.style.transition = "none";
    el.animate(
      [{ transform: el.style.transform || "none", opacity: 1 },
       { transform: `translateX(${x * 140}%) rotate(${x * 14}deg)`, opacity: 0 }],
      { duration: 280, easing: "cubic-bezier(.22,1,.36,1)", fill: "forwards" }
    );
    // Timer-driven so the advance never depends on Animation.finished resolving.
    window.setTimeout(after, 280);
  };

  const finishSession = useCallback(() => {
    setPhase("loading");
    api.trainSummary(sessionId)
      .then((s) => { setSummary(s); setPhase("summary"); })
      .catch((e) => { setErr(String(e)); setPhase("error"); });
  }, [sessionId]);

  const advance = useCallback((known: boolean, dir: "left" | "right") => {
    leaveCard(dir, () => {
      shownRef.current += 1;
      if (known) knownRef.current += 1;
      setFace("front"); setResult(null); setBusy(false); setNotice("");
      const el = cardElRef.current;
      if (el) { el.style.transition = ""; el.style.transform = ""; }
      if (shownRef.current >= SESSION_LEN || pos + 1 >= (queue?.length ?? 0)) finishSession();
      else setPos((p) => p + 1);
    });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [pos, queue, finishSession]);

  // Count a COMPLETED rep (answer scored in AI, or judged in non-AI) — retires the
  // gesture hint. Never called on tap/flip, so the no-flip AI flow still counts.
  const completeRep = () => { if (bumpSwipes(uid) >= HINT_REPS) setExperienced(true); };

  // Front → back: a single tap flips the card (non-AI only). Self-rating happens
  // with the buttons on the back.
  const flipToBack = () => {
    if (!card || face !== "front") return;
    haptic("light");
    flip("back");
  };

  // Self-assessment on the back. «guessed» leaves right, «missed» leaves left;
  // both record the swipe and advance to the next card.
  const judge = (known: boolean) => {
    if (!card) return;
    haptic("medium");
    if (rec.recording) { void rec.stop(); }
    completeRep();
    api.trainSwipe(sessionId, card.phrase_id, known ? "right" : "left", Date.now() - shownAtRef.current).catch(() => {});
    advance(known, known ? "right" : "left");
  };

  // AI advance: the % IS the verdict — derive known from the score (no manual
  // self-rating, which would pollute the SRS signal) and move on. Swipe direction
  // is purely cosmetic (the card flies the way the finger went); known stays score-based.
  const aiNext = (dir: "left" | "right" = "right") => {
    if (!card || !result) return;
    haptic("medium");
    const known = result.score >= 6;
    api.trainSwipe(sessionId, card.phrase_id, known ? "right" : "left", Date.now() - shownAtRef.current).catch(() => {});
    advance(known, dir);
  };

  // Swipe-to-advance for the AI result frame (replaces the «Дальше» button).
  // Either direction advances — the % is already the verdict. Non-AI keeps buttons.
  const drag = useRef({ x0: 0, active: false, dx: 0 });
  const canSwipe = () => !!card && canVoice && !!result;
  const onCardDown = (e: React.PointerEvent) => {
    if (!canSwipe()) return;
    drag.current = { x0: e.clientX, active: true, dx: 0 };
    if (cardElRef.current) cardElRef.current.style.transition = "none";
  };
  const onCardMove = (e: React.PointerEvent) => {
    const d = drag.current;
    if (!d.active) return;
    d.dx = e.clientX - d.x0;
    if (cardElRef.current) cardElRef.current.style.transform = `translateX(${d.dx}px) rotate(${d.dx * 0.04}deg)`;
  };
  const onCardUp = () => {
    const d = drag.current;
    if (!d.active) return;
    d.active = false;
    const el = cardElRef.current;
    if (Math.abs(d.dx) < 70) {                          // not far enough → snap back
      if (el) { el.style.transition = "transform .22s cubic-bezier(.22,1,.36,1)"; el.style.transform = ""; }
      return;
    }
    aiNext(d.dx > 0 ? "right" : "left");
  };

  const handleScoreErr = (e: unknown) => {
    const msg = String(e);
    if (msg.includes("429") || msg.toLowerCase().includes("limit"))
      setNotice(t("practice.limitReached"));
    else setErr(msg);
  };

  // The mic is gated PER CARD: the backend allows it on the free showcase batch
  // for everyone, and on every batch for the ai plan. Falls back to the plan
  // entitlement if the deck predates the ai_allowed flag.
  const canVoice = card?.ai_allowed ?? !!user?.entitlements?.voice_answer;

  // Voice answer (AI only). STT ladder, cheapest first: web Web-Speech (web, 0 tokens)
  // → native on-device SFSpeechRecognizer (native iOS, free/private) → MediaRecorder +
  // server STT (fallback). The phrase answer is English-only, so on-device is safe here;
  // the mixed RU+EN sequence exam is a separate flow and stays on the server.
  const onMic = useCallback(async () => {
    if (!canVoice) { nav("/subscribe"); return; }  // locked mic -> upsell
    if (!hasVoiceConsent()) { setShowVoiceConsent(true); return; }  // consent before voice→AI
    if (!card || busy) return;
    setNotice(""); setErr("");
    // Web: webkitSpeechRecognition transcribes free via Apple's service.
    const useSpeechNow = speech.supported && !recFallback && !isNative();
    if (useSpeechNow) {
      if (speech.listening) { speech.stop(); return; }
      let tr = "";
      try { tr = await speech.start("en-US"); }
      catch { setRecFallback(true); setNotice(t("practice.micUnavailable")); return; }
      if (!tr.trim()) { setNotice(t("practice.micNoHear")); return; }
      setBusy(true);
      try { const r = await api.trainAnswerText(sessionId, card.phrase_id, tr); setResult(r); completeRep(); }
      catch (e) { handleScoreErr(e); }
      finally { setBusy(false); }
      return;
    }
    // Native iOS: on-device recognition (audio never leaves the phone, no server STT).
    // One-shot like the web path; on failure flip recFallback so the rest of the
    // session uses the server path instead of wasting taps.
    if (isNative() && !recFallback) {
      if (nativeListening) { await nativeSttStop(); return; }  // tap-to-stop
      setNativeListening(true);
      let tr = "";
      try { tr = await nativeRecognize("en-US"); }
      catch { setNativeListening(false); setRecFallback(true); setNotice(t("practice.micUnavailable")); return; }
      setNativeListening(false);
      if (!tr.trim()) { setNotice(t("practice.micNoHear")); return; }
      setBusy(true);
      try { const r = await api.trainAnswerText(sessionId, card.phrase_id, tr); setResult(r); completeRep(); }
      catch (e) { handleScoreErr(e); }
      finally { setBusy(false); }
      return;
    }
    if (!rec.recording) { await rec.start(); return; }
    const clip = await rec.stop();
    if (!clip || clip.ms < 400) { setNotice(t("practice.micLonger")); return; }
    setBusy(true);
    try { const r = await api.trainAnswer(sessionId, card.phrase_id, clip.blob, clip.filename, clip.ms); setResult(r); completeRep(); }
    catch (e) { handleScoreErr(e); }
    finally { setBusy(false); }
  }, [canVoice, nav, card, busy, rec, speech, recFallback, nativeListening, sessionId, t]);

  // --- Hands-free auto-loop --------------------------------------------------
  const toggleHandsFree = async () => {
    if (handsFree) { setHandsFree(false); setHfStage(""); hf.close(); cancelSpeak(); return; }
    if (!canVoice) { nav("/subscribe"); return; }        // mic is a paid feature
    if (!hasVoiceConsent()) { setShowVoiceConsent(true); return; }  // consent before voice→AI
    haptic("medium");
    // iOS unlocks audio + speechSynthesis only inside a user gesture — warm both
    // here, synchronously, before the await breaks out of the tap context.
    unlockAudio();
    if (card) { const [cu, cl] = cueOf(card); prefetchCueAudio(cu, cl); }
    try { window.speechSynthesis?.speak(new SpeechSynthesisUtterance("")); } catch { /* noop */ }
    const ok = await hf.open();                           // gesture → grants the mic
    if (!ok) { setNotice(t("practice.micUnavailable")); return; }
    setHandsFree(true);
  };

  // Drive one card automatically while hands-free is on: cue → record → score →
  // advance, looping into the next card (which re-runs this effect).
  useEffect(() => {
    if (!handsFree || phase !== "deck" || !card) return;
    if (hfRunningRef.current === card.phrase_id) return;  // already running this card
    hfRunningRef.current = card.phrase_id;
    let cancelled = false;
    const delay = (ms: number) => new Promise((r) => window.setTimeout(r, ms));
    const run = async () => {
      setResult(null); setNotice(""); setFace("front");
      setHfStage("cue");
      { const [cu, cl] = cueOf(card); await speakCueAudio(cu, cl); }
      if (cancelled) return;
      flip("back");
      await delay(380);
      if (cancelled) return;
      setHfStage("listen");                               // ← your turn to speak
      let clip = await hf.record(6500);
      if (cancelled) return;
      if (!clip || clip.ms < 400) {                       // missed the window → one more chance
        setNotice(t("practice.micNoHear"));
        setHfStage("listen");
        clip = await hf.record(6500);
        if (cancelled) return;
      }
      if (!clip || clip.ms < 400) {                       // still nothing → skip as missed
        setNotice("");
        api.trainSwipe(sessionId, card.phrase_id, "left", clip?.ms ?? 0).catch(() => {});
        advance(false, "left");
        return;
      }
      setNotice("");
      setHfStage("score"); setBusy(true);
      // One card's transient failure must not kill the whole loop: retry once,
      // then skip the card (no swipe recorded) and keep going. Only a rate/budget
      // 429 stops the mode — the quota won't come back mid-session.
      for (let attempt = 0; attempt < 2; attempt++) {
        try {
          const r = await api.trainAnswer(sessionId, card.phrase_id, clip.blob, clip.filename, clip.ms);
          if (cancelled) return;
          setResult(r); setBusy(false); setHfStage("");
          completeRep();                                   // retires the swipe hint over time
          // No auto-advance: the learner reads the verdict, then swipes to the next card.
          return;
        } catch (e) {
          if (cancelled) return;
          const msg = String(e);
          if (msg.includes("429") || msg.toLowerCase().includes("limit")) {
            setBusy(false); setHfStage(""); handleScoreErr(e);
            setHandsFree(false); hf.close();               // out of quota — stop honestly
            return;
          }
          if (attempt === 0) { await delay(1200); continue; }
          setBusy(false); setHfStage("");
          setNotice(t("practice.hfSkip"));                 // transient — skip, loop lives
          advance(false, "left");
        }
      }
    };
    run();
    return () => { cancelled = true; cancelSpeak(); hf.stopNow(); };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [handsFree, card?.phrase_id, phase]);

  // While hands-free runs, warm the NEXT card's cue so its playback is instant
  // (hides the first-synth latency the learner complained about).
  useEffect(() => {
    if (!handsFree || !card) return;
    const nxt = queue?.[pos + 1];
    if (nxt) { const [cu, cl] = cueOf(nxt); prefetchCueAudio(cu, cl); }
  }, [handsFree, card?.phrase_id, pos, queue]);

  // Auto-fit the situation/task so a long card never collides with the mic:
  // shrink --fit (font multiplier) in small steps until the text block clears
  // the reserved mic zone, or we hit a readable floor (0.8). The card front is
  // RU-content of unbounded length, so this guarantees no overlap on every card.
  useLayoutEffect(() => {
    const body = bodyRef.current, fit = fitRef.current;
    if (!body || !fit) return;
    const run = () => {
      fit.style.setProperty("--fit", "1");
      const cs = getComputedStyle(body);
      const avail = body.clientHeight - parseFloat(cs.paddingTop || "0") - parseFloat(cs.paddingBottom || "0");
      if (avail <= 0) return;
      let scale = 1;
      // 5 steps max (1.0 → 0.8); reflow-measured each time so fixed parts count.
      while (fit.scrollHeight > avail && scale > 0.8) {
        scale = Math.max(0.8, Math.round((scale - 0.04) * 1000) / 1000);
        fit.style.setProperty("--fit", String(scale));
      }
    };
    run();
    // Re-measure once webfonts settle (metrics shift) and on viewport changes.
    if (document.fonts && document.fonts.ready) document.fonts.ready.then(run).catch(() => {});
    window.addEventListener("resize", run);
    return () => window.removeEventListener("resize", run);
  }, [card?.phrase_id, face, result, handsFree, canVoice]);

  // Release the mic stream when leaving the screen.
  // eslint-disable-next-line react-hooks/exhaustive-deps
  useEffect(() => () => { hf.close(); cancelSpeak(); }, []);

  const restart = () => {
    shownRef.current = 0; knownRef.current = 0;
    setSummary(null); setPos(0); setSessionId(newSessionId());
    setFace("front"); setResult(null); setBusy(false);
    loadDeck();
  };

  if (phase === "error") return <div className="screen tr-screen"><p className="error">{err}</p></div>;
  if (phase === "loading") return <div className="screen tr-screen"><p className="muted" style={{ marginTop: 28 }}>{t("practice.loading")}</p></div>;

  if (phase === "empty") {
    return (
      <div className="screen tr-screen">
        <Head />
        <div className="pr-empty">
          <p className="pr-empty-t">{t("practice.emptyTitle")}</p>
          <p className="pr-empty-s">{t("practice.emptyText")}</p>
          <button className="l3-cta" style={{ marginTop: 18 }} onClick={() => nav("/learn")}>
            <IconPlay size={18} /> {t("practice.toLearn")}
          </button>
        </div>
      </div>
    );
  }

  if (phase === "summary" && summary) {
    return (
      <div className="screen tr-screen">
        <Head />
        <div className="tr-summary">
          <p className="tr-sum-k">{summary.cards_known}<span>/{summary.cards_total}</span></p>
          <p className="tr-sum-label">{t("practice.sumKnown")}</p>
          {summary.avg_score != null && (
            <p className="tr-sum-avg">{t("practice.sumAvg")} · <b>{summary.avg_score}</b></p>
          )}
          {summary.weakest && summary.strongest && summary.weakest.batch_id !== summary.strongest.batch_id && (
            <div className="tr-sum-rows">
              <div className="tr-sum-row"><span className="tr-sum-tag no">{t("practice.weaker")}</span>{summary.weakest.batch_title}</div>
              <div className="tr-sum-row"><span className="tr-sum-tag ok">{t("practice.stronger")}</span>{summary.strongest.batch_title}</div>
            </div>
          )}
          <button className="l3-cta" onClick={restart}><IconPlay size={18} /> {t("practice.again")}</button>
          <button className="btn-ghost" onClick={() => nav("/learn")}>{t("practice.toLearn")}</button>
        </div>
      </div>
    );
  }

  const pct = result ? Math.round(result.score * 10) : 0;
  const pctClass = pct >= 80 ? "ok" : pct >= 50 ? "mid" : "no";
  const ghosts = queue ? queue.slice(pos + 1, pos + 3) : [];
  const micActive = rec.recording || speech.listening || nativeListening;

  return (
    <div className="screen tr-screen">
      <div className="tr-deck">
        {ghosts.map((g, i) => (
          <div className="tr-card ghost" key={`g-${g.phrase_id}`} style={{ "--gi": ghosts.length - i } as React.CSSProperties} aria-hidden />
        ))}
        {card && (
          <div
            className="tr-card"
            data-tour="card"
            ref={cardElRef}
            key={card.phrase_id}
            // Only non-AI flips on tap. AI answers inline via the mic; hands-free is auto.
            role={!canVoice && !handsFree && face === "front" ? "button" : undefined}
            tabIndex={!canVoice && !handsFree && face === "front" ? 0 : -1}
            aria-label={!canVoice && face === "front" ? t("practice.hintTapFlip") : undefined}
            onClick={() => { if (!handsFree && !canVoice && face === "front") flipToBack(); }}
            onKeyDown={(e) => {
              if (!handsFree && !canVoice && face === "front" && (e.key === "Enter" || e.key === " ")) {
                e.preventDefault();
                flipToBack();
              }
            }}
            onPointerDown={onCardDown}
            onPointerMove={onCardMove}
            onPointerUp={onCardUp}
            onPointerCancel={onCardUp}
          >
            <div className="tr-card-inner" ref={innerRef}>
              <div className="tr-face">
                {face === "front" ? (
                  <>
                    <div className="tr-photo">
                      <BatchCover seed={card.slug || String(card.batch_id)} coverUrl={card.cover_url} className="tr-photo-img" />
                      <div className="tr-photo-fade" />
                      <div className="tr-pill">{pillLabel(card)}</div>
                    </div>
                    {/* Stimulus — hidden once the AI result takes over the card. */}
                    {!(canVoice && !handsFree && result) && (
                      <div className="tr-body" ref={bodyRef}>
                        <div className="tr-fit" ref={fitRef}>
                          <span className="tr-stim-label">{t("practice.situationLabel")}</span>
                          {card.situation_ru ? (
                            <>
                              <p className="tr-situation">{card.situation_ru}</p>
                              {card.task_ru && (
                                <p className="tr-task"><span className="tr-task-lbl">{t("practice.taskLabel")}</span>{card.task_ru}</p>
                              )}
                            </>
                          ) : (
                            <p className="tr-stim">{card.stimulus || card.gloss_ru || card.anchor}</p>
                          )}
                        </div>
                      </div>
                    )}

                    {/* AI mode answers INLINE on the front — no flip. Result = score + model phrase only. */}
                    {canVoice && !handsFree && (
                      result ? (
                        <div className="tr-result tr-result-front">
                          <div className={`verdict-pct ${pctClass === "ok" ? "ok" : pctClass === "no" ? "no" : ""}`}>
                            {pct}<span style={{ fontSize: 22, fontWeight: 700 }}>%</span>
                          </div>
                          <ModelPhrase label={t("practice.modelLabel")} model={result.correct_phrase} said={result.transcript} />
                          {!experienced && <p className="tr-hint tr-hint-swipe">{t("practice.hintSwipeNext")}</p>}
                        </div>
                      ) : (
                        <div className="tr-mic-zone">
                          <button className={`tr-mic-glass${micActive ? " on" : ""}`} data-tour="mic" onClick={onMic} disabled={busy}
                            aria-label={t("rec.recordAria")}>
                            {busy ? <span className="tr-mic-dots">…</span> : rec.recording ? <span className="tr-mic-stop" /> : <IconMic size={28} />}
                          </button>
                          {/* Live partial transcript — instant "it hears me" feedback. */}
                          {speech.listening && speech.interim && (
                            <p className="tr-mic-live" aria-live="polite">{speech.interim}</p>
                          )}
                          {(speech.listening || nativeListening || rec.recording || busy) ? (
                            <p className="tr-mic-label">
                              {(speech.listening || nativeListening) ? t("practice.micListening") : rec.recording ? t("practice.micRecording") : t("practice.micChecking")}
                            </p>
                          ) : !experienced ? (
                            <p className="tr-hint">{t("practice.hintTapMic")}</p>
                          ) : null}
                        </div>
                      )
                    )}

                    {/* Non-AI: a one-time hint to tap-flip. */}
                    {!canVoice && !handsFree && !experienced && (
                      <p className="tr-hint front">{t("practice.hintTapFlip")}</p>
                    )}
                  </>
                ) : (
                  <div className="tr-back2">
                    <button className="tr-back-prompt" onClick={() => { if (!handsFree) flip("front"); }}
                      aria-label={t("practice.flipBack")}>
                      <span className="tr-back-prompt-text">{card.stimulus || card.gloss_ru || card.anchor}</span>
                      {!handsFree && <span className="tr-back-prompt-hint">↩ {t("practice.flipBack")}</span>}
                    </button>
                    <div className="tr-back2-mid">
                      {handsFree ? (
                        result ? (
                          <div className="tr-result">
                            <div className={`verdict-pct ${pctClass === "ok" ? "ok" : pctClass === "no" ? "no" : ""}`}>
                              {pct}<span style={{ fontSize: 22, fontWeight: 700 }}>%</span>
                            </div>
                            <ModelPhrase label={t("practice.modelLabel")} model={result.correct_phrase} said={result.transcript} />
                            {!experienced && <p className="tr-hint tr-hint-swipe">{t("practice.hintSwipeNext")}</p>}
                          </div>
                        ) : (
                          <div className="tr-hf-live">
                            <div className={`tr-mic-glass${hfStage === "listen" ? " on" : ""}${hfStage === "cue" ? " dim" : ""}`} aria-hidden>
                              {hfStage === "score" ? <span className="tr-mic-dots">…</span> : <IconMic size={28} />}
                            </div>
                            <p className={`tr-hf-label${hfStage === "listen" ? " go" : ""}`}>
                              {hfStage === "cue" ? t("practice.hfCue")
                                : hfStage === "score" ? t("practice.micChecking")
                                : t("practice.hfListen")}
                            </p>
                          </div>
                        )
                      ) : (
                        // Non-AI · the model phrase to self-check against.
                        <p className="tr-answer big">
                          <span className="tr-result-lbl">{t("practice.modelLabel")}</span>{card.phrase_en}
                        </p>
                      )}
                    </div>
                    {!handsFree && !canVoice && (
                      <div className="tr-judge">
                        <button className="tr-judge-btn no" onClick={() => judge(false)}>{t("practice.missed")}</button>
                        <button className="tr-judge-btn yes" onClick={() => judge(true)}>{t("practice.guessed")}</button>
                      </div>
                    )}
                  </div>
                )}
              </div>
            </div>
          </div>
        )}
      </div>

      {/* Conversation-mode toggle lives BELOW the card now — frees the top so the
          card can be tall and uncramped (no page header on the practice screen). */}
      {canVoice && (
        <div className="tr-hf-bar">
          <button className={`tr-hf-toggle${handsFree ? " on" : ""}`} data-tour="handsfree" onClick={toggleHandsFree}>
            <IconMic size={15} />
            {handsFree ? t("practice.hfStop") : t("practice.hfStart")}
          </button>
        </div>
      )}

      {notice && <p className="muted small center" style={{ marginTop: 12 }}>{notice}</p>}
      {rec.error && <p className="error center" style={{ marginTop: 8 }}>{rec.error}</p>}

      {showVoiceConsent && (
        <div className="ava-modal" role="dialog" aria-modal="true">
          <div className="ava-sheet">
            <p className="ava-title">{t("voice.consentTitle")}</p>
            <p className="muted small" style={{ textAlign: "center", margin: 0, lineHeight: 1.5 }}>{t("voice.consentText")}</p>
            <div className="ava-actions">
              <button className="btn-ghost" onClick={() => setShowVoiceConsent(false)}>{t("common.cancel")}</button>
              <button className="btn" onClick={acceptVoiceConsent}>{t("voice.consentAccept")}</button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
