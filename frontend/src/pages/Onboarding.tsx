import { useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api, BatchDetail } from "../api";
import { setProfile, SCENARIOS } from "../lib/profile";
import { useMnemoAudio } from "../audio/useMnemoAudio";
import { IconBack, IconCheck, IconPlay, IconPause } from "../ui/icons";
import { useI18n } from "../i18n";

// Two beats, on purpose. (1) One question — what does the learner need English
// for? The chosen scenarios ARE the strategy (they reorder the path). (2) A 60-sec
// LIVE taste of the method on a real story before the app: hear it, tap a word,
// watch the phrase surface — "это и есть метод". Both skippable.
export default function Onboarding() {
  const nav = useNavigate();
  const { t } = useI18n();
  const [step, setStep] = useState<"pick" | "taste">("pick");
  const [scenarios, setScenarios] = useState<string[]>([]);

  // --- taste step state ---
  const [demo, setDemo] = useState<BatchDetail | null>(null);
  const [revealed, setRevealed] = useState<Set<string>>(new Set());
  const mnemo = useMnemoAudio(demo?.id);

  const toggle = (key: string) =>
    setScenarios((prev) => {
      if (prev.includes(key)) return prev.filter((k) => k !== key);
      if (prev.length >= 2) return prev; // cap at 2 — keep the start focused
      return [...prev, key];
    });

  const finish = () => {
    setProfile({ scenarios, onboardedAt: new Date().toISOString() });
    setStep("taste"); // one live taste of the method, then into the app
  };

  const done = () => nav("/learn", { replace: true });

  // Load the free showcase batch for the taste — guaranteed playable for a brand
  // new free account (its audio is pre-generated). Falls straight through to the
  // app if anything is missing, so onboarding never dead-ends.
  useEffect(() => {
    if (step !== "taste" || demo) return;
    api.listBatches()
      .then((list) => {
        const pick = list.find((b) => b.is_free)
          || list.find((b) => !b.locked)
          || [...list].sort((a, b) => b.created_at.localeCompare(a.created_at))[0];
        if (!pick) { done(); return; }
        return api.getBatch(pick.id).then(setDemo);
      })
      .catch(() => done());
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [step, demo]);

  const spans = useMemo(
    () => (demo ? [...demo.mnemo.spans].sort((a, b) => a.start - b.start) : []),
    [demo]
  );
  const phraseById = useMemo(
    () => new Map((demo?.phrases ?? []).map((p) => [p.id, p] as const)),
    [demo]
  );

  // ── Step 1: the one question ─────────────────────────────────────────
  if (step === "pick") {
    return (
      <div className="screen quest">
        <button className="back-link" onClick={() => nav("/", { replace: true })}>
          <IconBack /> {t("ob1.later")}
        </button>

        <div className="quest-step">
          <h1 className="quest-q">{t("ob1.q")}</h1>
          <p className="app-sub">{t("ob1.sub")}</p>
          <div className="quest-opts">
            {SCENARIOS.map((o) => {
              const sel = scenarios.includes(o.key);
              return (
                <button
                  key={o.key}
                  className={`quest-opt${sel ? " sel" : ""}`}
                  aria-pressed={sel}
                  onClick={() => toggle(o.key)}
                >
                  <span className="qo-body">
                    <span className="qo-label">{t(`scenario.${o.key}`)}</span>
                  </span>
                  {sel && <span className="qo-check"><IconCheck size={14} /></span>}
                </button>
              );
            })}
          </div>
        </div>

        <button
          className="btn btn-primary btn-block quest-cta"
          disabled={scenarios.length < 1}
          onClick={finish}
        >
          {t("ob1.cta")}
        </button>
      </div>
    );
  }

  // ── Step 2: the live taste ───────────────────────────────────────────
  // Render the story with tappable anchor spans + karaoke highlight (same
  // mechanism as Lesson 1, trimmed to a single guided beat).
  const story = demo?.mnemo.story_ru ?? "";
  const pieces: JSX.Element[] = [];
  let cursor = 0;
  spans.forEach((sp, i) => {
    if (sp.start > cursor) pieces.push(<span key={`t${i}`}>{story.slice(cursor, sp.start)}</span>);
    const ph = phraseById.get(sp.phrase_id);
    const open = revealed.has(sp.anchor_id);
    pieces.push(
      <span key={sp.anchor_id} className="anchor-wrap">
        <button
          className={`anchor${mnemo.activeAnchor === sp.anchor_id ? " on" : ""}`}
          onClick={() => setRevealed((prev) => {
            const n = new Set(prev);
            n.has(sp.anchor_id) ? n.delete(sp.anchor_id) : n.add(sp.anchor_id);
            return n;
          })}
        >
          {story.slice(sp.start, sp.end)}
        </button>
        {open && ph && <span className="reveal">{ph.phrase_en}</span>}
      </span>
    );
    cursor = sp.end;
  });
  if (cursor < story.length) pieces.push(<span key="tail">{story.slice(cursor)}</span>);

  return (
    <div className="screen quest ob-taste">
      <div className="quest-step">
        <span className="ob-taste-kicker">{t("ob2.kicker")}</span>
        <h1 className="quest-q">{t("ob2.title")}</h1>
        <p className="app-sub">{t("ob2.sub")}</p>

        {!demo ? (
          <p className="faint" style={{ marginTop: 24 }}>{t("common.loading")}</p>
        ) : (
          <>
            <div className="mnemo-play" style={{ marginTop: 18 }}>
              <button
                className={`mp-pill${mnemo.layout === "full" ? " on" : ""}`}
                disabled={mnemo.loading !== null}
                onClick={() => mnemo.play("full")}
              >
                {mnemo.layout === "full" && mnemo.playing ? <IconPause size={16} /> : <IconPlay size={16} />}
                {mnemo.loading === "full" ? "…" : t("ob2.play")}
              </button>
            </div>
            <p className="ob-taste-story">{pieces}</p>
            <p className="ob-taste-outro">{t("ob2.outro")}</p>
            <audio {...mnemo.bind} />
          </>
        )}
      </div>

      <button className="btn btn-primary btn-block quest-cta" onClick={done}>
        {t("ob2.cta")}
      </button>
      <button className="ob-skip" onClick={done}>{t("ob2.skip")}</button>
    </div>
  );
}
