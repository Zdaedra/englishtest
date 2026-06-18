import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api, DeckCard, AnswerResult, SessionSummary, Coach } from "../api";
import { useAuth } from "../auth/AuthContext";
import { useI18n } from "../i18n";
import { useRecorder } from "../audio/useRecorder";
import { useSpeech } from "../audio/useSpeech";
import { getProgress, isEngaged } from "../lib/progress";
import { haptic } from "../lib/session";
import { SECTION_BY_SLUG } from "../lib/sections";
import { BatchCover } from "../ui/Art";
import { IconPlay, IconMic, IconProfile } from "../ui/icons";

// Two-face card: the prompt, then the back. The back's content depends on plan —
// AI gets a mic (records → scored), non-AI gets the model phrase (эталон). Both
// self-assess with the «guessed / missed» buttons at the bottom.
type Face = "front" | "back";
const SESSION_LEN = 12;
const FETCH_LIMIT = 24;

// Once the learner has done this many swipes (cumulative, per user), the card
// stops showing the "how to use" helper text — they know the gesture by now.
const EXPERIENCED_AT = 20;
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

// Situation context per section — instant framing ("where am I"). A reasonable
// default until a per-phrase scene is curated.
const SITU: Record<string, string> = {
  "live-tone": "One-on-one", pitch: "Investor pitch", negotiation: "Negotiation table",
  pressure: "Hot-seat Q&A", repair: "Making amends", leadership: "Team meeting",
  requests: "Quick ask", written: "Message thread", "small-talk": "Casual meeting",
  charisma: "Working the room", flirt: "On a date", intimacy: "Close conversation",
  "lead-presence": "Leading the room", composure: "Under provocation",
  gravitas: "Crisis war-room", stage: "On stage",
};
const situLabel = (c: DeckCard) => SITU[c.section] || "Conversation";

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
      if (!isEngaged(p)) continue;
      (p.l3_passed ? maint : active).push(id);
    }
  } catch { /* ignore */ }
  return { active, maint };
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
  const { user } = useAuth();
  const { t } = useI18n();
  const uid = user?.id;
  const rec = useRecorder();
  const speech = useSpeech();

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
  const [experienced, setExperienced] = useState(() => getSwipes(uid) >= EXPERIENCED_AT);
  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState<AnswerResult | null>(null);
  const [recFallback, setRecFallback] = useState(false);
  const [summary, setSummary] = useState<SessionSummary | null>(null);
  const [coach, setCoach] = useState<Coach | null>(null);
  const [coachState, setCoachState] = useState<"idle" | "loading" | "locked" | "done">("idle");

  const cardElRef = useRef<HTMLDivElement>(null);
  const innerRef = useRef<HTMLDivElement>(null);

  const sources = useMemo(deckSources, []);
  const card = queue && pos < queue.length ? queue[pos] : null;

  const loadDeck = useCallback(() => {
    const { active, maint } = sources;
    const batchIds = active.length ? active : maint;
    const maintenanceIds = active.length ? maint : [];
    if (!batchIds.length) { setPhase("empty"); setQueue([]); return; }
    setPhase("loading");
    api.getDeck(batchIds, { maintenanceIds, limit: FETCH_LIMIT })
      .then((d) => { setQueue(d); setPhase(d.length ? "deck" : "empty"); shownAtRef.current = Date.now(); })
      .catch((e) => { setErr(String(e)); setPhase("error"); });
  }, [sources]);

  useEffect(() => { loadDeck(); }, [loadDeck]);
  useEffect(() => { shownAtRef.current = Date.now(); }, [pos]);

  // AI Coach (paid) — fetch a coaching breakdown once a voice answer is scored.
  useEffect(() => {
    if (!result || user?.plan !== "ai") return;
    setCoach(null); setCoachState("loading");
    api.coach(result.phrase_id, result.transcript, result.score)
      .then((r) => { if ("locked" in r) setCoachState("locked"); else { setCoach(r); setCoachState("done"); } })
      .catch(() => setCoachState("idle"));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [result]);

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
      setCoach(null); setCoachState("idle");
      const el = cardElRef.current;
      if (el) { el.style.transition = ""; el.style.transform = ""; }
      if (shownRef.current >= SESSION_LEN || pos + 1 >= (queue?.length ?? 0)) finishSession();
      else setPos((p) => p + 1);
    });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [pos, queue, finishSession]);

  const countSwipe = () => { if (bumpSwipes(uid) >= EXPERIENCED_AT) setExperienced(true); };

  // Front → back: a single tap flips the card. No pre-assessment — the learner
  // judges themselves with the buttons on the back.
  const flipToBack = () => {
    if (!card || face !== "front") return;
    haptic("light");
    countSwipe();
    flip("back");
  };

  // Self-assessment on the back. «guessed» leaves right, «missed» leaves left;
  // both record the swipe and advance to the next card.
  const judge = (known: boolean) => {
    if (!card) return;
    haptic("medium");
    if (rec.recording) { void rec.stop(); }
    api.trainSwipe(sessionId, card.phrase_id, known ? "right" : "left", Date.now() - shownAtRef.current).catch(() => {});
    advance(known, known ? "right" : "left");
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

  // Voice answer (AI only): on-device Web Speech first (0 tokens), MediaRecorder +
  // server STT as fallback when speech is unsupported or errors.
  const onMic = useCallback(async () => {
    if (!canVoice) { nav("/subscribe"); return; }  // locked mic -> upsell
    if (!card || busy) return;
    setNotice(""); setErr("");
    const useSpeechNow = speech.supported && !recFallback;
    if (useSpeechNow) {
      if (speech.listening) { speech.stop(); return; }
      let tr = "";
      try { tr = await speech.start("en-US"); }
      catch { setRecFallback(true); setNotice(t("practice.micUnavailable")); return; }
      if (!tr.trim()) { setNotice(t("practice.micNoHear")); return; }
      setBusy(true);
      try { const r = await api.trainAnswerText(sessionId, card.phrase_id, tr); setResult(r); }
      catch (e) { handleScoreErr(e); }
      finally { setBusy(false); }
      return;
    }
    if (!rec.recording) { await rec.start(); return; }
    const clip = await rec.stop();
    if (!clip || clip.ms < 400) { setNotice(t("practice.micLonger")); return; }
    setBusy(true);
    try { const r = await api.trainAnswer(sessionId, card.phrase_id, clip.blob, clip.filename, clip.ms); setResult(r); }
    catch (e) { handleScoreErr(e); }
    finally { setBusy(false); }
  }, [canVoice, nav, card, busy, rec, speech, recFallback, sessionId, t]);

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
  const micActive = rec.recording || speech.listening;

  return (
    <div className="screen tr-screen">
      <Head title={card?.batch_title} />

      <div className="tr-deck">
        {ghosts.map((g, i) => (
          <div className="tr-card ghost" key={`g-${g.phrase_id}`} style={{ "--gi": ghosts.length - i } as React.CSSProperties} aria-hidden />
        ))}
        {card && (
          <div
            className="tr-card"
            ref={cardElRef}
            key={card.phrase_id}
            role={face === "front" ? "button" : undefined}
            tabIndex={face === "front" ? 0 : -1}
            aria-label={face === "front" ? t("practice.tapToAnswer") : undefined}
            onClick={() => { if (face === "front") flipToBack(); }}
            onKeyDown={(e) => {
              if (face === "front" && (e.key === "Enter" || e.key === " ")) {
                e.preventDefault();
                flipToBack();
              }
            }}
          >
            <div className="tr-card-inner" ref={innerRef}>
              <div className="tr-face">
                {face === "front" ? (
                  <>
                    <div className="tr-photo">
                      <BatchCover seed={card.slug || String(card.batch_id)} coverUrl={card.cover_url} className="tr-photo-img" />
                      <div className="tr-photo-fade" />
                      <div className="tr-pill">{pillLabel(card)}</div>
                      <div className="tr-situ"><IconProfile size={13} /> {situLabel(card)}</div>
                    </div>
                    <div className="tr-body">
                      <p className="tr-stim">{card.stimulus || card.gloss_ru || card.anchor}</p>
                    </div>
                    <div className="tr-foot">
                      {!experienced && <div className="tr-foot-cue">{t("practice.tapToAnswer")}</div>}
                      <div className="tr-dots">
                        {Array.from({ length: SESSION_LEN }).map((_, i) => (
                          <span key={i} className={i < shownRef.current ? "on" : ""} />
                        ))}
                      </div>
                    </div>
                  </>
                ) : (
                  <div className="tr-back2">
                    <div className="tr-back2-mid">
                      {canVoice ? (
                        result ? (
                          // AI · after the spoken answer is scored — compact verdict only.
                          <div className="tr-score">
                            <div className={`verdict-pct ${pctClass === "ok" ? "ok" : pctClass === "no" ? "no" : ""}`}>
                              {pct}<span style={{ fontSize: 22, fontWeight: 700 }}>%</span>
                            </div>
                            <p className="tr-answer">{result.correct_phrase}</p>
                            {coachState === "loading" && <p className="tr-coach-load">…</p>}
                            {coachState === "done" && coach?.feedback && <p className="tr-coach-fb">{coach.feedback}</p>}
                            {result.transcript && <p className="tr-heard">{t("practice.heard", { t: result.transcript })}</p>}
                          </div>
                        ) : (
                          // AI · the mic is the whole face. Press → speak the phrase.
                          <>
                            <button className={`tr-mic big${micActive ? " on" : ""}`} onClick={onMic} disabled={busy}
                              aria-label={t("rec.recordAria")}>
                              {busy ? <span className="tr-mic-dots">…</span> : rec.recording ? <span className="tr-mic-stop" /> : <IconMic size={46} />}
                            </button>
                            {(speech.listening || rec.recording || busy) && (
                              <p className="tr-mic-label">
                                {speech.listening ? t("practice.micListening") : rec.recording ? t("practice.micRecording") : t("practice.micChecking")}
                              </p>
                            )}
                          </>
                        )
                      ) : (
                        // Non-AI · just the model phrase (эталон) to self-check against.
                        <p className="tr-answer big">{card.phrase_en}</p>
                      )}
                    </div>
                    <div className="tr-judge">
                      <button className="tr-judge-btn no" onClick={() => judge(false)}>{t("practice.missed")}</button>
                      <button className="tr-judge-btn yes" onClick={() => judge(true)}>{t("practice.guessed")}</button>
                    </div>
                  </div>
                )}
              </div>
            </div>
          </div>
        )}
      </div>

      {notice && <p className="muted small center" style={{ marginTop: 12 }}>{notice}</p>}
      {rec.error && <p className="error center" style={{ marginTop: 8 }}>{rec.error}</p>}
    </div>
  );
}
