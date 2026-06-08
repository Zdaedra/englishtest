import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api, DeckCard, AnswerResult, SessionSummary, Coach } from "../api";
import { useAuth } from "../auth/AuthContext";
import { useRecorder } from "../audio/useRecorder";
import { useSpeech } from "../audio/useSpeech";
import { getProgress, isEngaged } from "../lib/progress";
import { SECTION_BY_SLUG } from "../lib/sections";
import { BatchCover } from "../ui/Art";
import { IconPlay, IconMic, IconChevron, IconClose, IconProfile, IconSwipeHand, IconTap, IconLock } from "../ui/icons";

type Face = "front" | "reveal" | "voice" | "result";
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
  return (
    <div className="screen-head tr-head">
      <span className="tr-eyebrow">Практика</span>
      <h1>{title || "Тренировка"}</h1>
      <p className="app-sub" style={{ marginBottom: 0 }}>
        Ты в разговоре. Кто-то это сказал — что ответишь?
      </p>
    </div>
  );
}

export default function Training() {
  const nav = useNavigate();
  const { user } = useAuth();
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
  const affL = useRef<HTMLDivElement>(null);
  const affR = useRef<HTMLDivElement>(null);
  const drag = useRef({ down: false, startX: 0, dx: 0 });

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
    if (face !== "result" || !result) return;
    if (user?.plan === "ai") {
      setCoach(null); setCoachState("loading");
      api.coach(result.phrase_id, result.transcript, result.score)
        .then((r) => { if ("locked" in r) setCoachState("locked"); else { setCoach(r); setCoachState("done"); } })
        .catch(() => setCoachState("idle"));
    } else {
      setCoachState("locked");
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [face, result]);

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

  const resetTransform = () => {
    const el = cardElRef.current;
    if (el) { el.style.transition = "transform .28s cubic-bezier(.22,1,.36,1)"; el.style.transform = "translateX(0) rotate(0)"; }
  };
  const setAff = (dx: number) => {
    if (affR.current) affR.current.style.opacity = String(Math.min(1, Math.max(0, dx / 110)));
    if (affL.current) affL.current.style.opacity = String(Math.min(1, Math.max(0, -dx / 110)));
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
  const onDontKnow = () => {
    if (!card || face !== "front") return;
    countSwipe();
    api.trainSwipe(sessionId, card.phrase_id, "left", Date.now() - shownAtRef.current).catch(() => {});
    resetTransform(); setAff(0); flip("reveal");
  };
  const onKnow = () => {
    if (!card || face !== "front") return;
    countSwipe();
    resetTransform(); setAff(0); flip("voice");
  };

  const interactive = face === "front" && !!card;
  const onDown = (e: React.PointerEvent) => {
    if (!interactive) return;
    drag.current = { down: true, startX: e.clientX, dx: 0 };
    try { cardElRef.current?.setPointerCapture(e.pointerId); } catch { /* non-fatal */ }
  };
  const onMove = (e: React.PointerEvent) => {
    if (!drag.current.down) return;
    const dx = e.clientX - drag.current.startX;
    drag.current.dx = dx;
    const el = cardElRef.current;
    if (el) { el.style.transition = "none"; el.style.transform = `translateX(${dx}px) rotate(${dx * 0.035}deg)`; }
    setAff(dx);
  };
  const onUp = () => {
    if (!drag.current.down) return;
    const dx = drag.current.dx;
    drag.current.down = false;
    const w = cardElRef.current?.offsetWidth ?? 320;
    if (dx > w * 0.3) onKnow();
    else if (dx < -w * 0.3) onDontKnow();
    else { resetTransform(); setAff(0); }
  };

  const handleScoreErr = (e: unknown) => {
    const msg = String(e);
    if (msg.includes("429") || msg.toLowerCase().includes("limit"))
      setNotice("Дневной лимит проверок исчерпан — свайпай влево, чтобы повторять.");
    else setErr(msg);
  };

  // The mic (spoken answer) is an Executive AI feature. Without it the voice face
  // shows a locked mic + the model answer for self-check.
  const canVoice = !!user?.entitlements?.voice_answer;

  // Voice answer (AI only): on-device Web Speech first (0 tokens), MediaRecorder +
  // server STT as fallback when speech is unsupported or errors.
  const onMic = useCallback(async () => {
    if (!canVoice) { nav("/profile"); return; }  // locked mic -> upsell
    if (!card || busy) return;
    setNotice(""); setErr("");
    const useSpeechNow = speech.supported && !recFallback;
    if (useSpeechNow) {
      if (speech.listening) { speech.stop(); return; }
      let t = "";
      try { t = await speech.start("en-US"); }
      catch { setRecFallback(true); setNotice("Распознавание недоступно — нажми и запишу аудио."); return; }
      if (!t.trim()) { setNotice("Не расслышал — нажми и повтори."); return; }
      setBusy(true);
      try { const r = await api.trainAnswerText(sessionId, card.phrase_id, t); setResult(r); setFace("result"); }
      catch (e) { handleScoreErr(e); }
      finally { setBusy(false); }
      return;
    }
    if (!rec.recording) { await rec.start(); return; }
    const clip = await rec.stop();
    if (!clip || clip.ms < 400) { setNotice("Не расслышал — нажми и скажи чуть дольше."); return; }
    setBusy(true);
    try { const r = await api.trainAnswer(sessionId, card.phrase_id, clip.blob, clip.filename, clip.ms); setResult(r); setFace("result"); }
    catch (e) { handleScoreErr(e); }
    finally { setBusy(false); }
  }, [canVoice, nav, card, busy, rec, speech, recFallback, sessionId]);

  // The "×" on the voice face: move straight on to the next card (stops any
  // recording first). The only control on that face.
  const skipVoice = () => {
    if (!card) return;
    if (rec.recording) { void rec.stop(); }
    api.trainSwipe(sessionId, card.phrase_id, "right", Date.now() - shownAtRef.current).catch(() => {});
    advance(true, "right");
  };

  const restart = () => {
    shownRef.current = 0; knownRef.current = 0;
    setSummary(null); setPos(0); setSessionId(newSessionId());
    setFace("front"); setResult(null); setBusy(false);
    loadDeck();
  };

  if (phase === "error") return <div className="screen tr-screen"><p className="error">{err}</p></div>;
  if (phase === "loading") return <div className="screen tr-screen"><p className="muted" style={{ marginTop: 28 }}>Готовим колоду…</p></div>;

  if (phase === "empty") {
    return (
      <div className="screen tr-screen">
        <Head />
        <div className="pr-empty">
          <p className="pr-empty-t">Пока нечего тренировать</p>
          <p className="pr-empty-s">
            Активируй любой навык в Библиотеке — его проверочные реплики сразу попадут
            сюда в колоду для тренировки.
          </p>
          <button className="l3-cta" style={{ marginTop: 18 }} onClick={() => nav("/learn")}>
            <IconPlay size={18} /> В Обучение
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
          <p className="tr-sum-label">узнано в этом подходе</p>
          {summary.avg_score != null && (
            <p className="tr-sum-avg">Средний балл голосом · <b>{summary.avg_score}</b></p>
          )}
          {summary.weakest && summary.strongest && summary.weakest.batch_id !== summary.strongest.batch_id && (
            <div className="tr-sum-rows">
              <div className="tr-sum-row"><span className="tr-sum-tag no">Слабее</span>{summary.weakest.batch_title}</div>
              <div className="tr-sum-row"><span className="tr-sum-tag ok">Сильнее</span>{summary.strongest.batch_title}</div>
            </div>
          )}
          <button className="l3-cta" onClick={restart}><IconPlay size={18} /> Ещё подход</button>
          <button className="btn-ghost" onClick={() => nav("/learn")}>В Обучение</button>
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
            onPointerDown={onDown}
            onPointerMove={onMove}
            onPointerUp={onUp}
            onPointerCancel={onUp}
            onClick={() => { if (face === "reveal") advance(false, "left"); }}
            style={{ touchAction: "none" }}
          >
            <div className="tr-card-inner" ref={innerRef}>
              <div className="tr-face">
                {face === "front" && (
                  <>
                    <div className="tr-photo">
                      <BatchCover seed={card.slug || String(card.batch_id)} coverUrl={card.cover_url} className="tr-photo-img" />
                      <div className="tr-photo-fade" />
                      <div className="tr-pill">{pillLabel(card)}</div>
                      <div className="tr-situ"><IconProfile size={13} /> {situLabel(card)}</div>
                    </div>
                    <div className="tr-aff left" ref={affL}>не&nbsp;знаю</div>
                    <div className="tr-aff right" ref={affR}>знаю</div>
                    <div className="tr-body">
                      <p className="tr-stim">{card.stimulus || card.gloss_ru || card.anchor}</p>
                    </div>
                    <div className="tr-foot">
                      {!experienced && (
                        <>
                          <div className="tr-foot-row">
                            <button className="tr-sh no" onClick={onDontKnow}>←&nbsp;Не&nbsp;знаю</button>
                            <span className="tr-gesture" aria-hidden><IconSwipeHand size={30} /></span>
                            <button className="tr-sh go" onClick={onKnow}>Знаю&nbsp;ответ&nbsp;→</button>
                          </div>
                          <div className="tr-foot-cue">Свайпни, чтобы ответить</div>
                        </>
                      )}
                      <div className="tr-dots">
                        {Array.from({ length: SESSION_LEN }).map((_, i) => (
                          <span key={i} className={i < shownRef.current ? "on" : ""} />
                        ))}
                      </div>
                    </div>
                  </>
                )}

                {face === "reveal" && (
                  <div className="tr-reveal" role="button">
                    <span className="tr-rv-ghost" aria-hidden>{(card.anchor || "").toUpperCase()}</span>
                    <span className="tr-rv-label">Возможный ответ</span>
                    <p className="tr-rv-phrase">{card.phrase_en}</p>
                    <div className="tr-rv-foot">
                      {!experienced && (
                        <>
                          <span className="tr-rv-tap" aria-hidden><IconTap size={20} /></span>
                          <span className="tr-rv-cue">Нажми, чтобы продолжить</span>
                        </>
                      )}
                      <div className="tr-dots">
                        {Array.from({ length: SESSION_LEN }).map((_, i) => (
                          <span key={i} className={i < shownRef.current ? "on" : ""} />
                        ))}
                      </div>
                    </div>
                  </div>
                )}

                {face === "voice" && (
                  <div className="tr-back-voice">
                    <div className="tr-voice-top">
                      <span className="tr-back-label">Тебе сказали</span>
                      <p className="tr-voice-stim">{card.stimulus || card.gloss_ru || card.anchor}</p>
                    </div>
                    {canVoice ? (
                      <>
                        <div className="tr-voice-mid">
                          <button className={`tr-mic big${micActive ? " on" : ""}`} onClick={onMic} disabled={busy}
                            aria-label={micActive ? "Стоп" : "Сказать"}>
                            {busy ? <span className="tr-mic-dots">…</span> : rec.recording ? <span className="tr-mic-stop" /> : <IconMic size={46} />}
                          </button>
                          {(speech.listening || rec.recording || busy || !experienced) && (
                            <p className="tr-mic-label">
                              {speech.listening ? "Слушаю…" : rec.recording ? "Идёт запись — нажми «стоп»" : busy ? "Проверяем…" : "Нажми и скажи свою фразу"}
                            </p>
                          )}
                        </div>
                        <div className="tr-voice-foot">
                          <button className="tr-cancel" onClick={skipVoice} aria-label="Дальше"><IconClose size={20} /></button>
                        </div>
                      </>
                    ) : (
                      <>
                        <div className="tr-voice-mid">
                          <button className="tr-mic big locked" onClick={() => nav("/profile")}
                            aria-label="Голосовой ответ — в Executive AI">
                            <IconMic size={46} />
                            <span className="tr-mic-badge" aria-hidden><IconLock size={15} /></span>
                          </button>
                          {!experienced && (
                            <p className="tr-mic-label">Сначала проверь себя — потом сверь с эталоном</p>
                          )}
                        </div>
                        <div className="tr-voice-self">
                          {!experienced && <span className="tr-back-label">Как можно ответить</span>}
                          <p className="tr-answer">{card.phrase_en}</p>
                        </div>
                        <button className="tr-upsell" onClick={() => nav("/profile")}>
                          <span className="tr-upsell-label">✦ Ответить голосом и получить разбор</span>
                          <span className="tr-upsell-sub">Микрофон доступен в Executive AI →</span>
                        </button>
                        <div className="tr-voice-foot">
                          <button className="tr-cancel" onClick={skipVoice} aria-label="Дальше"><IconClose size={20} /></button>
                        </div>
                      </>
                    )}
                  </div>
                )}

                {face === "result" && result && (
                  <div className="tr-back-pad">
                    <div className={`verdict-pct ${pctClass === "ok" ? "ok" : pctClass === "no" ? "no" : ""}`}>
                      {pct}<span style={{ fontSize: 22, fontWeight: 700 }}>%</span>
                    </div>
                    <div className="tr-pips">{[0, 1, 2, 3, 4].map((i) => <span key={i} className={i < Math.round(result.score / 2) ? "on" : ""} />)}</div>
                    {result.feedback && <p className="tr-feedback">{result.feedback}</p>}
                    {coachState === "loading" && <p className="tr-coach-load">AI-коуч разбирает…</p>}
                    {coachState === "done" && coach && (
                      <div className="tr-coach">
                        <span className="tr-coach-label">✦ AI-коуч</span>
                        {coach.feedback && <p className="tr-coach-fb">{coach.feedback}</p>}
                        {coach.better && <p className="tr-coach-better"><span>Сильнее</span>{coach.better}</p>}
                        {coach.tone && <span className="tr-coach-tone">{coach.tone}</span>}
                      </div>
                    )}
                    {coachState === "locked" && (
                      <button className="tr-upsell" onClick={() => nav("/profile")}>
                        <span className="tr-upsell-label">✦ Разбор от AI-коуча</span>
                        <span className="tr-upsell-sub">Доступно в Executive AI →</span>
                      </button>
                    )}
                    <span className="tr-back-label">Эталон</span>
                    <p className="tr-answer">{result.correct_phrase}</p>
                    {result.transcript && <p className="tr-heard">Услышал: {result.transcript}</p>}
                    <button className="tr-next" onClick={() => advance(pct >= 80, "right")}>Дальше <IconChevron size={18} /></button>
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
