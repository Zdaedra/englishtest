import { useEffect, useLayoutEffect, useMemo, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api, BattleItem, BattlePick } from "../api";
import { useAuth } from "../auth/AuthContext";
import { useI18n } from "../i18n";
import { useRecorder, Recording } from "../audio/useRecorder";
import { syncWidget } from "../lib/widget";
import { IconMic } from "../ui/icons";

// Live mode: the user is IN a live conversation and needs the right line NOW.
// The screen is ONE card (the practice-card idiom verbatim) and nothing else:
// the liquid-glass mic ON the card, you dictate the moment, and the best line
// UNFOLDS ON THE SAME CARD; tapping the card expands it with the other picks.
// Non-AI plan: the mic's place holds a text input instead — the same card
// unfolds the best local keyword match for free.
//
// Voice path = MediaRecorder → /api/battle/suggest-voice (server STT + pick in
// one round trip). Field logs buried the on-device recognizer for live RU
// («Сибири», «Да кофе я не на», 2× empty) — the Whisper-class server model is
// the quality path, and the same recorder already works in the practice mic.
// Audio goes to the AI provider → gated behind the same voice_ai consent as
// the trainer.
//
// Two scopes (segmented toggle): "learned" = advise from what you trained;
// "all" = the whole catalog. Cost stays bounded (routers/battle.py): typing is
// a free offline filter; a mic tap costs stt+battle (~$0.002); "all" is
// keyword-prefiltered server-side; the monthly plan cap 429s past the ceiling.
const CACHE_KEY = (uid: number, scope: string) => `ee-battle-corpus:${uid}:${scope}`;
const SCOPE_KEY = (uid: number) => `ee-battle-scope:${uid}`;

type Scope = "learned" | "all";

const norm = (s: string) => (s || "").toLowerCase().replace(/ё/g, "е");
const toks = (q: string) =>
  norm(q).split(/[^a-zа-я0-9']+/i).filter((t) => t.length >= 2);

const SRS_BOOST: Record<string, number> = { automatic: 1.5, familiar: 1.2, shaky: 0.8 };

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

function loadCache(uid: number, scope: string): BattleItem[] {
  try {
    const raw = localStorage.getItem(CACHE_KEY(uid, scope));
    const arr = raw ? JSON.parse(raw) : null;
    return Array.isArray(arr) ? arr : [];
  } catch { return []; }
}

// idle → listening (recording) → thinking (STT + pick, one trip) → idle
// (with the result unfolded on the card).
type MicState = "idle" | "listening" | "thinking";

export default function Battle() {
  const nav = useNavigate();
  const { t } = useI18n();
  const { user } = useAuth();
  const uid = user?.id ?? 0;
  const isAI = user?.plan === "ai";
  const rec = useRecorder();

  const [scope, setScope] = useState<Scope>(() => {
    try { return localStorage.getItem(SCOPE_KEY(uid)) === "all" ? "all" : "learned"; }
    catch { return "learned"; }
  });
  const [corpus, setCorpus] = useState<BattleItem[]>(() => loadCache(uid, scope));
  const [search, setSearch] = useState("");   // non-AI card input (free local match)
  const [expanded, setExpanded] = useState(false);          // card unfolded to alts
  const [mic, setMic] = useState<MicState>("idle");
  const [moment, setMoment] = useState("");   // the dictated moment (server `heard`)
  const [ai, setAi] = useState<BattlePick[] | null>(null);
  const [note, setNote] = useState("");       // fallback / limit / no-hear
  const [intents, setIntents] = useState<string[]>([]);   // ranked moves, best first
  const [intentSel, setIntentSel] = useState("");          // the move the picks answer

  // Voice→AI consent (Apple §5.1.2(i) + GDPR): the clip goes to the STT
  // provider, so the first mic tap shows the same one-time gate as the trainer
  // (shared per-user flag — accepted in practice ⇒ no re-ask here).
  const [showVoiceConsent, setShowVoiceConsent] = useState(false);
  const voiceConsentKey = uid ? `ee-voice-consent-${uid}` : null;
  const hasVoiceConsent = () => {
    try { return !!voiceConsentKey && localStorage.getItem(voiceConsentKey) === "1"; }
    catch { return false; }
  };
  const acceptVoiceConsent = () => {
    try { if (voiceConsentKey) localStorage.setItem(voiceConsentKey, "1"); } catch { /* private */ }
    api.recordConsent("voice_ai").catch(() => {});   // server audit (best-effort)
    setShowVoiceConsent(false);
  };

  useEffect(() => { try { localStorage.setItem(SCOPE_KEY(uid), scope); } catch { /* private */ } }, [scope, uid]);

  // The moment field grows with its content — the WHOLE typed or dictated moment
  // must stay readable (it's what the picks answer). ~9 lines, then inner scroll.
  const momentRef = useRef<HTMLTextAreaElement | null>(null);
  useLayoutEffect(() => {
    const el = momentRef.current;
    if (!el) return;
    el.style.height = "auto";
    el.style.height = `${Math.min(el.scrollHeight + 2, 240)}px`;
  }, [moment]);

  // Cache-first, then refresh — usable the instant it opens, and fully offline.
  // Refetch when the scope flips; the widget only ever mirrors the LEARNED set.
  useEffect(() => {
    let on = true;
    setCorpus(loadCache(uid, scope));
    api.battleCorpus(scope)
      .then((items) => {
        if (!on) return;
        setCorpus(items);
        try { localStorage.setItem(CACHE_KEY(uid, scope), JSON.stringify(items)); } catch { /* full */ }
        if (scope === "learned") void syncWidget(items);
      })
      .catch(() => { /* offline — the cached copy already renders */ });
    return () => { on = false; };
  }, [uid, scope]);

  // Release the mic stream when leaving the screen mid-recording.
  // eslint-disable-next-line react-hooks/exhaustive-deps
  useEffect(() => () => { if (rec.recording) void rec.stop(); }, []);

  // Local matches for the typed (non-AI) path: best + up to 3 alternatives.
  const searchToks = toks(search);
  const results = useMemo(() => {
    if (!searchToks.length) return [] as BattleItem[];
    return corpus
      .map((it) => [rank(it, searchToks), it] as const)
      .filter(([s]) => s > 0)
      .sort((a, b) => b[0] - a[0])
      .slice(0, 4)
      .map(([, it]) => it);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [corpus, search]);

  const play = (pid: number, e?: React.MouseEvent) => {
    e?.stopPropagation();
    api.phraseAudio(pid)
      .then((r) => { new Audio(r.audio_url).play().catch(() => { /* locked */ }); })
      .catch(() => { /* offline — text is already on screen */ });
  };

  const runSuggestVoice = async (clip: Recording) => {
    console.log("[LV] suggest-voice →", scope, clip.ms, "ms,", clip.blob.size, "b");
    try {
      const r = await api.battleSuggestVoice(clip.blob, clip.filename, scope);
      console.log("[LV] suggest-voice ←", r.via, r.picks.length, r.intents, JSON.stringify(r.heard));
      setMoment(r.heard || "");
      setIntents(r.intents ?? []);
      setIntentSel((r.intents ?? [])[0] || "");
      if (r.via === "llm" && r.picks.length) setAi(r.picks);
      else if (r.via === "empty_stt") setNote(t("battle.recEmpty"));
      else if (r.via === "llm") setNote(t("battle.noResults"));
      else if (r.via === "fallback") setNote(t("battle.aiUnavailable"));
      else setNote(scope === "all" ? t("battle.aiUnavailable") : t("battle.empty"));
    } catch (e) {
      console.log("[LV] suggest-voice error:", String(e));
      setNote(String(e).includes("429") ? t("practice.limitReached")
        : t("battle.aiUnavailable"));
    } finally { setMic("idle"); }
  };

  // Typed moment (AI plan): you can't always speak in a meeting. Same card, same
  // AI pick as the mic — just the text /suggest endpoint (no STT, no audio, so no
  // voice consent needed and it's cheaper). Reuses the whole result rendering.
  const runSuggestText = async () => {
    const q = moment.trim();
    if (!q || mic !== "idle") return;
    console.log("[LV] suggest-text →", scope, JSON.stringify(q));
    setAi(null); setNote(""); setExpanded(false); setIntents([]); setIntentSel("");
    setMoment(q); setMic("thinking");           // the moment already lives in the field
    try {
      const r = await api.battleSuggest(q, scope);
      console.log("[LV] suggest-text ←", r.via, r.picks.length, r.intents);
      setIntents(r.intents ?? []);
      setIntentSel((r.intents ?? [])[0] || "");
      if (r.via === "llm" && r.picks.length) setAi(r.picks);
      else if (r.via === "llm") setNote(t("battle.noResults"));
      else if (r.via === "fallback") setNote(t("battle.aiUnavailable"));
      else setNote(scope === "all" ? t("battle.aiUnavailable") : t("battle.empty"));
    } catch (e) {
      console.log("[LV] suggest-text error:", String(e));
      setNote(String(e).includes("429") ? t("practice.limitReached") : t("battle.aiUnavailable"));
    } finally { setMic("idle"); }
  };

  // Same gesture as the practice card: tap to record, tap again to finish.
  // Every step reacts instantly and every wait is bounded — the card can
  // never freeze (the lesson of the on-device-recognizer saga).
  const micTap = async () => {
    console.log("[LV] micTap in state:", mic, "rec:", rec.recording);
    if (mic === "listening") {
      setMic("thinking");
      let clip: Recording | null = null;
      try {
        clip = await Promise.race([
          rec.stop(),
          new Promise<null>((res) => window.setTimeout(() => res(null), 4000)),
        ]);
      } catch { clip = null; }
      console.log("[LV] clip:", clip ? `${clip.ms}ms/${clip.blob.size}b` : "null");
      if (!clip || clip.ms < 400) { setMic("idle"); setNote(t("battle.recEmpty")); return; }
      await runSuggestVoice(clip);
      return;
    }
    if (mic !== "idle") return;
    if (!hasVoiceConsent()) { setShowVoiceConsent(true); return; }
    setAi(null); setNote(""); setMoment(""); setExpanded(false);
    setIntents([]); setIntentSel("");
    const ok = await rec.start();               // user gesture → mic permission
    if (!ok) { console.log("[LV] rec.start failed:", rec.error); setNote(t("battle.micUnsupported")); return; }
    console.log("[LV] recording");
    setMic("listening");
  };

  // One-tap move override: re-pick the SAME dictated moment under a different
  // conversational intent (text endpoint — no re-recording, one battle call).
  const pickIntent = async (k: string) => {
    if (mic !== "idle" || !moment || k === intentSel) return;
    setIntentSel(k); setNote(""); setExpanded(false); setMic("thinking");
    console.log("[LV] re-pick intent:", k);
    try {
      const r = await api.battleSuggest(moment, scope, k);
      console.log("[LV] re-pick ←", r.via, r.picks.length);
      if (r.via === "llm" && r.picks.length) setAi(r.picks);
      else {
        setAi(null);
        setNote(r.via === "fallback" ? t("battle.aiUnavailable") : t("battle.noResults"));
      }
    } catch (e) {
      console.log("[LV] re-pick error:", String(e));
      setAi(null);
      setNote(String(e).includes("429") ? t("practice.limitReached") : t("battle.aiUnavailable"));
    } finally { setMic("idle"); }
  };

  // What the card unfolds: the AI pick (voice) or the top local match (typed).
  const showAi = mic === "idle" && !!ai && ai.length > 0;
  const typedBest = !isAI && searchToks.length > 0 ? results[0] : undefined;
  const best: (BattlePick | BattleItem) | undefined = showAi ? ai![0] : typedBest;
  const alts: (BattlePick | BattleItem)[] =
    showAi ? ai!.slice(1) : typedBest ? results.slice(1) : [];
  const cardTap = () => { if (best && alts.length) setExpanded((x) => !x); };

  return (
    <div className="screen bm-screen">
      <div className="screen-head">
        <h1>{t("battle.title")}</h1>
        <p className="app-sub" style={{ marginBottom: 0 }}>{t("battle.sub")}</p>
      </div>

      {/* Scope: advise from what you trained, or from the whole course. */}
      <div className="seg seg-wide lv-scope" role="tablist" aria-label={t("battle.title")}>
        <button role="tab" aria-selected={scope === "learned"} className={scope === "learned" ? "on" : ""}
          onClick={() => { setScope("learned"); setAi(null); setNote(""); setExpanded(false); setIntents([]); setIntentSel(""); }}>
          {t("battle.scopeLearned")}
        </button>
        <button role="tab" aria-selected={scope === "all"} className={scope === "all" ? "on" : ""}
          onClick={() => { setScope("all"); setAi(null); setNote(""); setExpanded(false); setIntents([]); setIntentSel(""); }}>
          {t("battle.scopeAll")}
        </button>
      </div>

      {/* THE card — one surface, the practice-card idiom. Nothing below it. */}
      <div className={`lv-card${mic !== "idle" ? " live" : ""}`} onClick={cardTap}>
        <div className="lv-body">
          {/* AI · the moment lives in an editable field at the top: dictate it with
              the centered mic below, OR tap here to type it (you can't always speak
              out loud in a meeting). Dictation lands in this same field. */}
          {isAI && (
            <textarea
              ref={momentRef}
              className="lv-moment-field"
              rows={1}
              enterKeyHint="send"
              placeholder={t("battle.typeMoment")}
              value={moment}
              onChange={(e) => setMoment(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter" && !e.shiftKey) {
                  e.preventDefault();           // the moment is one message, not multiline prose
                  if (moment.trim()) {
                    e.currentTarget.blur();
                    void runSuggestText();
                  }
                }
              }}
              onClick={(e) => e.stopPropagation()}
              // iOS: a tap on a readOnly field focuses it WITHOUT a keyboard and the
              // field then looks dead once readOnly drops (the keyboard never returns
              // on the next tap). Never let it sit focused mid-flight — blur, so the
              // tap after the result is a fresh focus → keyboard opens.
              onFocus={(e) => { if (mic !== "idle") e.currentTarget.blur(); }}
              readOnly={mic !== "idle"}
              aria-label={t("battle.momentHint")}
            />
          )}

          {mic === "listening" ? (
            <p className="lv-live ph">{t("battle.recHint")}</p>
          ) : mic === "thinking" ? null : (
            <>
              {/* Ranked moves — tap another to re-pick for that intent. */}
              {intents.length > 0 && (
                <div className="lv-intents" onClick={(e) => e.stopPropagation()}>
                  {intents.map((k) => (
                    <button key={k} className={`lv-chip${k === intentSel ? " on" : ""}`}
                      onClick={() => void pickIntent(k)}>
                      {t(`intent.${k}`)}
                    </button>
                  ))}
                </div>
              )}
              {best ? (
                <>
                  {/* Just the line + its meaning — you're mid-conversation, nothing
                      to press, nothing to read besides what to say. */}
                  <p className="lv-best">{best.phrase_en}</p>
                  {best.gloss_ru && <span className="lv-gloss">{best.gloss_ru}</span>}
                  {alts.length > 0 && !expanded && <p className="lv-more">{t("battle.moreAlts")} ⌄</p>}
                  {expanded && (
                    <div className="lv-alts">
                      {alts.map((p) => (
                        <button key={p.phrase_id} className="lv-pick alt"
                          onClick={(e) => play(p.phrase_id, e)}>
                          <span className="lv-alt-phrase">{p.phrase_en}</span>
                          {p.gloss_ru && <span className="lv-alt-gloss">{p.gloss_ru}</span>}
                        </button>
                      ))}
                    </div>
                  )}
                </>
              ) : (!isAI) ? (
                <p className="lv-prompt">
                  {searchToks.length ? t("battle.noResults") : t("battle.typePrompt")}
                </p>
              ) : null}
              {note && <p className="lv-warn">{note}</p>}
            </>
          )}
        </div>

        {isAI ? (
          <div className="lv-mic-zone" onClick={(e) => e.stopPropagation()}>
            {/* Mic centered, like the practice card. Tap to dictate the moment; or
                tap the field above to type it. Both feed the same AI pick. */}
            <button
              className={`tr-mic-glass lv-mic${mic === "listening" ? " on" : ""}`}
              onClick={() => { void micTap(); }}
              disabled={mic === "thinking"}
              aria-label={t("battle.micHint")}
            >
              {mic === "thinking" ? <span className="tr-mic-dots">…</span> : <IconMic size={28} />}
            </button>
            <p className="lv-mic-label">
              {mic === "listening" ? t("battle.tapStop")
                : mic === "thinking" ? t("battle.aiThinking")
                  : showAi ? t("battle.newMoment")
                    : t("battle.momentHint")}
            </p>
          </div>
        ) : (
          <div className="lv-input-zone" onClick={(e) => e.stopPropagation()}>
            <input
              className="bm-input"
              type="search"
              enterKeyHint="search"
              placeholder={t("battle.placeholder")}
              value={search}
              onChange={(e) => { setSearch(e.target.value); setExpanded(false); }}
            />
            <p className="lv-lock" onClick={() => nav("/subscribe")}>{t("battle.micLocked")}</p>
          </div>
        )}
      </div>

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
