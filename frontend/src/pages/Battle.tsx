import { useEffect, useMemo, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api, BattleItem, BattlePick } from "../api";
import { useAuth } from "../auth/AuthContext";
import { useI18n } from "../i18n";
import { useSpeech } from "../audio/useSpeech";
import { nativeRecognize, nativeSttAvailable, nativeSttStop } from "../audio/nativeStt";
import { isNative } from "../lib/session";
import { syncWidget } from "../lib/widget";
import { IconMic, IconPlay } from "../ui/icons";

// Live mode: the user is IN a live conversation and needs the right line NOW.
// ONE card, the practice-card idiom verbatim: the liquid-glass mic ON the card,
// you dictate the moment, and the best line UNFOLDS ON THE SAME CARD; tapping
// the card expands it with the other picks. No popup, no extra chrome.
// Non-AI plan: the mic's place holds a text input instead — the same card
// unfolds the best local keyword match for free.
//
// Two scopes (segmented toggle): "learned" = advise from what you trained;
// "all" = the whole catalog. Cost is bounded either way (routers/battle.py):
// only the mic spends an LLM call, typing is a free offline filter, and "all"
// is keyword-prefiltered server-side to a flat prompt size.
const CACHE_KEY = (uid: number, scope: string) => `ee-battle-corpus:${uid}:${scope}`;
const SCOPE_KEY = (uid: number) => `ee-battle-scope:${uid}`;
const TOP_N = 8;

type Scope = "learned" | "all";

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

function loadCache(uid: number, scope: string): BattleItem[] {
  try {
    const raw = localStorage.getItem(CACHE_KEY(uid, scope));
    const arr = raw ? JSON.parse(raw) : null;
    return Array.isArray(arr) ? arr : [];
  } catch { return []; }
}

// idle → listening (mic ON, live transcript fills the card) → thinking → idle
// (with the result unfolded on the card).
type MicState = "idle" | "listening" | "thinking";

export default function Battle() {
  const nav = useNavigate();
  const { t } = useI18n();
  const { user } = useAuth();
  const uid = user?.id ?? 0;
  const isAI = user?.plan === "ai";
  const speech = useSpeech();

  const [scope, setScope] = useState<Scope>(() => {
    try { return localStorage.getItem(SCOPE_KEY(uid)) === "all" ? "all" : "learned"; }
    catch { return "learned"; }
  });
  const [corpus, setCorpus] = useState<BattleItem[]>(() => loadCache(uid, scope));
  const [loaded, setLoaded] = useState(false);
  const [search, setSearch] = useState("");   // ONE query: non-AI card input + arsenal
  const [open, setOpen] = useState<number | null>(null);   // expanded arsenal row
  const [expanded, setExpanded] = useState(false);          // card unfolded to alts
  const [mic, setMic] = useState<MicState>("idle");
  const [heard, setHeard] = useState("");     // native partial/final transcript
  const [moment, setMoment] = useState("");   // the dictated moment
  const [ai, setAi] = useState<BattlePick[] | null>(null);
  const [note, setNote] = useState("");       // fallback / limit / no-hear
  const nativeStt = useRef(false);

  useEffect(() => { try { localStorage.setItem(SCOPE_KEY(uid), scope); } catch { /* private */ } }, [scope, uid]);

  // Cache-first, then refresh — usable the instant it opens, and fully offline.
  // Refetch when the scope flips; the widget only ever mirrors the LEARNED set.
  useEffect(() => {
    let on = true;
    setCorpus(loadCache(uid, scope));
    api.battleCorpus(scope)
      .then((items) => {
        if (!on) return;
        setCorpus(items);
        setLoaded(true);
        try { localStorage.setItem(CACHE_KEY(uid, scope), JSON.stringify(items)); } catch { /* full */ }
        if (scope === "learned") void syncWidget(items);
      })
      .catch(() => { if (on) setLoaded(true); });
    return () => { on = false; };
  }, [uid, scope]);

  const searchToks = toks(search);
  const results = useMemo(() => {
    if (!searchToks.length) {
      const base = scope === "learned"
        ? corpus.filter((it) => LEARNED.has(it.srs_status))
        : corpus;
      return base.slice(0, TOP_N);
    }
    return corpus
      .map((it) => [rank(it, searchToks), it] as const)
      .filter(([s]) => s > 0)
      .sort((a, b) => b[0] - a[0])
      .slice(0, 12)
      .map(([, it]) => it);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [corpus, search, scope]);

  const play = (pid: number, e?: React.MouseEvent) => {
    e?.stopPropagation();
    api.phraseAudio(pid)
      .then((r) => { new Audio(r.audio_url).play().catch(() => { /* locked */ }); })
      .catch(() => { /* offline — text is already on screen */ });
  };

  const runSuggest = async (text: string) => {
    setMoment(text);
    setMic("thinking");
    try {
      const r = await api.battleSuggest(text, scope);
      if (r.via === "llm" && r.picks.length) setAi(r.picks);
      else if (r.via === "llm") setNote(t("battle.noResults"));
      else if (r.via === "fallback") setNote(t("battle.aiUnavailable"));
      else setNote(scope === "all" ? t("battle.aiUnavailable") : t("battle.readyEmpty"));
    } catch (e) {
      setNote(String(e).includes("429") ? t("practice.limitReached")
        : t("battle.aiUnavailable"));
    } finally { setMic("idle"); setHeard(""); }
  };

  const startVoice = async () => {
    if (mic !== "idle") return;
    setAi(null); setNote(""); setHeard(""); setMoment(""); setExpanded(false);
    setMic("listening");
    let text = "";
    try {
      nativeStt.current = await nativeSttAvailable();
      if (nativeStt.current) text = await nativeRecognize("ru-RU", setHeard);
      // Web Speech ONLY in a real browser: inside the native WKWebView the
      // webkit recognizer is a zombie (never fires results, stop() is a no-op)
      // — exactly the frozen-mic bug. Native uses the plugin path or nothing.
      else if (!isNative() && speech.supported) text = await speech.start("ru-RU");
      else { setMic("idle"); setNote(t("battle.micUnsupported")); return; }
    } catch (e) {
      // native-stt-unavailable/denied → honest "unsupported"; web no-speech → recEmpty
      setMic("idle"); setHeard("");
      setNote(String(e).includes("native-stt") ? t("battle.micUnsupported") : t("battle.recEmpty"));
      return;
    }
    text = (text || "").trim();
    if (!text) { setMic("idle"); setHeard(""); setNote(t("battle.recEmpty")); return; }
    await runSuggest(text);
  };

  // Same gesture as the practice card: tap to talk, tap again to finish.
  const micTap = () => {
    if (mic === "listening") {
      if (nativeStt.current) nativeSttStop().catch(() => { /* noop */ });
      else speech.stop();
    } else if (mic === "idle") void startVoice();
  };

  const liveText = speech.interim || heard;

  // What the card unfolds: the AI pick (voice) or the top local match (typed).
  const showAi = mic === "idle" && !!ai && ai.length > 0;
  const typedBest = !isAI && searchToks.length > 0 ? results[0] : undefined;
  const best: (BattlePick | BattleItem) | undefined = showAi ? ai![0] : typedBest;
  const alts: (BattlePick | BattleItem)[] =
    showAi ? ai!.slice(1) : typedBest ? results.slice(1, 4) : [];
  const cardTap = () => { if (best && alts.length) setExpanded((x) => !x); };

  return (
    <div className="screen bm-screen">
      <div className="screen-head">
        <h1>{t("battle.title")}</h1>
        <p className="app-sub" style={{ marginBottom: 0 }}>{t("battle.sub")}</p>
      </div>

      {/* Scope: advise from what you trained, or from the whole course. */}
      <div className="seg seg-wide lv-scope" role="tablist" aria-label={t("battle.ready")}>
        <button role="tab" aria-selected={scope === "learned"} className={scope === "learned" ? "on" : ""}
          onClick={() => { setScope("learned"); setAi(null); setNote(""); setExpanded(false); }}>
          {t("battle.scopeLearned")}
        </button>
        <button role="tab" aria-selected={scope === "all"} className={scope === "all" ? "on" : ""}
          onClick={() => { setScope("all"); setAi(null); setNote(""); setExpanded(false); }}>
          {t("battle.scopeAll")}
        </button>
      </div>

      {/* THE card — one surface, the practice-card idiom. */}
      <div className={`lv-card${mic !== "idle" ? " live" : ""}`} onClick={cardTap}>
        <div className="lv-body">
          {mic === "listening" ? (
            <p className={`lv-live${liveText ? "" : " ph"}`}>{liveText || t("battle.recHint")}</p>
          ) : mic === "thinking" ? (
            <p className="lv-momentq">«{moment}»</p>
          ) : best ? (
            <>
              {showAi && moment && <p className="lv-momentq">«{moment}»</p>}
              <p className="lv-best">{best.phrase_en}</p>
              <div className="lv-meta">
                <button className="bm-play" aria-label="Play" onClick={(e) => play(best.phrase_id, e)}>
                  <IconPlay size={16} />
                </button>
                {best.gloss_ru && <span className="lv-gloss">{best.gloss_ru}</span>}
              </div>
              {"note" in best && best.note && <div className="bm-note">{best.note}</div>}
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
          ) : (
            <p className="lv-prompt">
              {isAI ? t("battle.cardPrompt")
                : searchToks.length ? t("battle.noResults") : t("battle.typePrompt")}
            </p>
          )}
          {note && mic === "idle" && <p className="lv-warn">{note}</p>}
        </div>

        {isAI ? (
          <div className="lv-mic-zone" onClick={(e) => e.stopPropagation()}>
            <button
              className={`tr-mic-glass lv-mic${mic === "listening" ? " on" : ""}`}
              onClick={micTap}
              disabled={mic === "thinking"}
              aria-label={t("battle.micHint")}
            >
              {mic === "thinking" ? <span className="tr-mic-dots">…</span> : <IconMic size={28} />}
            </button>
            <p className="lv-mic-label">
              {mic === "listening" ? t("battle.tapStop")
                : mic === "thinking" ? t("battle.aiThinking")
                  : showAi ? t("battle.newMoment")
                    : t("battle.cardMicHint")}
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

      {/* Arsenal — the browsable phrases (scope-dependent), free local search. */}
      <div className="bm-sect lv-arsenal-h">{t("battle.ready")}</div>
      {isAI && (
        <input
          className="bm-input lv-search"
          type="search"
          enterKeyHint="search"
          placeholder={t("battle.placeholder")}
          value={search}
          onChange={(e) => setSearch(e.target.value)}
        />
      )}
      {results.length === 0 ? (
        <p className="bm-hint">
          {searchToks.length ? t("battle.noResults")
            : !loaded && !corpus.length ? t("battle.loadingCorpus")
              : scope === "learned" ? t("battle.readyEmpty") : t("battle.noResults")}
        </p>
      ) : results.map((it) => (
        <div
          key={it.phrase_id}
          className="bm-card"
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
          {open === it.phrase_id && (
            <div className="bm-more" onClick={(e) => e.stopPropagation()}>
              {it.situation_ru && <p className="bm-situ">{it.situation_ru}</p>}
              <button className="bm-open" onClick={() => nav(`/batch/${it.batch_id}`)}>
                {t("battle.openBatch")}
              </button>
            </div>
          )}
        </div>
      ))}
    </div>
  );
}
