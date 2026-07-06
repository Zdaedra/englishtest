import { useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api, LeagueGrade } from "../api";
import { IconBack, IconMic } from "../ui/icons";
import { useI18n } from "../i18n";
import { useAuth } from "../auth/AuthContext";
import { useSpeech } from "../audio/useSpeech";
import { isNative } from "../lib/session";
import { nativeRecognize } from "../audio/nativeStt";
import {
  LEAGUE_QS, LeagueOption, LeagueTier, leagueOf, saveLeagueResult,
} from "../lib/league";

// "Check your English league" — the placement test. League 2.0: the learner
// answers every situation in their OWN English (voice or text) and the server
// grades all answers in one LLM pass against an explicit rubric (idiom /
// register / economy / move). The old pick-an-option quiz survives as the
// fallback mode when AI scoring is unavailable.
export default function League() {
  const nav = useNavigate();
  const { t } = useI18n();
  const { user } = useAuth();
  const speech = useSpeech();
  const [mode, setMode] = useState<"write" | "quiz">("write");
  const [step, setStep] = useState(-1);            // -1 intro · 0..N-1 · N result
  const [texts, setTexts] = useState<string[]>(() => LEAGUE_QS.map(() => ""));
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<"" | "limit" | "unavailable">("");
  const [grade, setGrade] = useState<{ tier: LeagueTier; avg: number; results: LeagueGrade[] } | null>(null);
  const [nativeListening, setNativeListening] = useState(false);
  const [picks, setPicks] = useState<LeagueOption[]>([]);

  // Quiz fallback: shuffle options once per mount so the native answer isn't
  // positionally learnable.
  const shuffled = useMemo(
    () => LEAGUE_QS.map((q) => ({
      ...q,
      options: [...q.options].sort(() => Math.random() - 0.5),
    })),
    []
  );

  const total = LEAGUE_QS.length;
  const done = step >= total;

  // ---- write mode ----

  const appendTranscript = (tr: string) => {
    if (!tr.trim()) return;
    setTexts((ts) => ts.map((v, i) =>
      i === step ? `${v}${v.trim() ? " " : ""}${tr.trim()}` : v));
  };

  const onMic = async () => {
    if (busy) return;
    if (isNative()) {
      if (nativeListening) return;
      setNativeListening(true);
      try { appendTranscript(await nativeRecognize("en-US")); }
      catch { /* mic denied/unavailable → keep typing */ }
      finally { setNativeListening(false); }
      return;
    }
    if (!speech.supported) return;
    if (speech.listening) { speech.stop(); return; }
    try { appendTranscript(await speech.start("en-US")); }
    catch { /* unsupported → keep typing */ }
  };

  const submit = async (answers: string[]) => {
    setBusy(true); setErr("");
    try {
      const r = await api.leagueScore(LEAGUE_QS.map((q, i) => ({
        id: q.id, situation: q.situation, text: answers[i] || "",
      })));
      const tier = r.tier as LeagueTier;
      const strong = r.results.filter((x) => x.score >= 8).length;
      saveLeagueResult({
        tier, score: strong, at: new Date().toISOString(),
        missed: r.results.filter((x) => x.score < 8).map((x) => x.better).filter(Boolean),
      });
      setGrade({ tier, avg: r.avg, results: r.results });
      setStep(total);
    } catch (e) {
      setErr(String(e).includes("429") ? "limit" : "unavailable");
    } finally { setBusy(false); }
  };

  const nextWrite = () => {
    if (step + 1 >= total) { submit(texts); return; }
    setStep(step + 1);
  };

  // ---- quiz fallback (the original flow, unchanged behaviour) ----

  const quizScore = picks.filter((p) => p.native).length;
  const quizTier = leagueOf(quizScore);
  const quizMissed = LEAGUE_QS
    .map((q, i) => ({ native: q.options.find((o) => o.native)!, hit: !!picks[i]?.native }))
    .filter((x) => !x.hit)
    .map((x) => x.native.text);

  const pick = (o: LeagueOption) => {
    const next = [...picks, o];
    setPicks(next);
    if (step + 1 >= total) {
      const s = next.filter((p) => p.native).length;
      saveLeagueResult({
        tier: leagueOf(s), score: s, at: new Date().toISOString(),
        missed: LEAGUE_QS
          .map((q, i) => ({ nat: q.options.find((oo) => oo.native)!.text, hit: !!next[i]?.native }))
          .filter((x) => !x.hit).map((x) => x.nat),
      });
    }
    setStep(step + 1);
  };

  const micOn = speech.listening || nativeListening;
  const micAvailable = isNative() || speech.supported;
  const tier = mode === "write" ? (grade?.tier ?? "functional") : quizTier;
  const weakCount = mode === "write"
    ? (grade?.results.filter((x) => x.score < 8).length ?? 0)
    : quizMissed.length;

  return (
    <div className="screen league-screen">
      <button className="back-link" onClick={() => nav("/")}>
        <IconBack size={18} /> {t("common.back")}
      </button>

      {step === -1 && (
        <div className="league-intro">
          <h1 className="league-title">{t("league.title")}</h1>
          <p className="league-sub">{mode === "write" ? t("league.intro2") : t("league.intro")}</p>
          <p className="league-note">{t("league.introNote", { n: total })}</p>
          {mode === "write" && <p className="league-note">{t("league.criteria")}</p>}
          <button className="btn-primary league-start" onClick={() => setStep(0)}>
            {t("league.start")}
          </button>
        </div>
      )}

      {step >= 0 && !done && mode === "write" && (
        <div className="league-q">
          <p className="league-count">{step + 1} / {total}</p>
          <p className="league-situation">{LEAGUE_QS[step].situation}</p>
          <p className="league-ask">{t("league.whatSay")}</p>
          <textarea
            className="paste lg-input"
            rows={3}
            placeholder={t("league.write.placeholder")}
            value={texts[step]}
            onChange={(e) => setTexts((ts) => ts.map((v, i) => i === step ? e.target.value : v))}
          />
          {speech.listening && speech.interim && (
            <p className="tr-mic-live" aria-live="polite">{speech.interim}</p>
          )}
          <div className="lg-actions">
            {micAvailable && (
              <button className={`tr-mic-glass lg-mic${micOn ? " on" : ""}`} onClick={onMic}
                disabled={busy} aria-label={t("rec.recordAria")}>
                <IconMic size={22} />
              </button>
            )}
            <button className="btn-primary lg-next" onClick={nextWrite} disabled={busy}>
              {busy ? t("league.grading")
                : step + 1 >= total ? t("league.finish") : t("league.next")}
            </button>
          </div>
          {err && (
            <div className="lg-err">
              <p className="form-err" role="alert">
                {t(err === "limit" ? "league.errLimit" : "league.errUnavailable")}
              </p>
              {err === "unavailable" && (
                <>
                  <button className="btn-primary lg-next" onClick={() => submit(texts)}>
                    {t("league.retry")}
                  </button>
                  <button className="lg-quiz-link" onClick={() => {
                    setMode("quiz"); setErr(""); setPicks([]); setStep(0);
                  }}>
                    {t("league.fallbackQuiz")}
                  </button>
                </>
              )}
            </div>
          )}
        </div>
      )}

      {step >= 0 && !done && mode === "quiz" && (
        <div className="league-q">
          <p className="league-count">{step + 1} / {total}</p>
          <p className="league-situation">{shuffled[step].situation}</p>
          <p className="league-ask">{t("league.whatSay")}</p>
          <div className="league-opts">
            {shuffled[step].options.map((o) => (
              <button key={o.text} className="league-opt" onClick={() => pick(o)}>
                {o.text}
              </button>
            ))}
          </div>
        </div>
      )}

      {done && (
        <div className="league-result">
          <p className="league-eyebrow">{t("league.resultEyebrow")}</p>
          <h1 className="league-tier">{t(`league.name.${tier}`)}</h1>
          <p className="league-tier-sub">{t(`league.desc.${tier}`)}</p>
          {mode === "write" && grade ? (
            <>
              <p className="league-score">{t("league.avgLine", { a: grade.avg })}</p>
              <div className="lg-break">
                {grade.results.map((r, i) => (
                  <div className="lg-row" key={r.id}>
                    <p className="lg-row-sit">{LEAGUE_QS[i].situation}</p>
                    <p className="lg-row-score">{r.score}/10</p>
                    {texts[i]?.trim() && <p className="lg-row-your">{texts[i]}</p>}
                    <p className="lg-row-better">{r.better}</p>
                    {r.note_ru && <p className="lg-row-note">{r.note_ru}</p>}
                  </div>
                ))}
              </div>
            </>
          ) : (
            <>
              <p className="league-score">{t("league.score", { s: quizScore, n: total })}</p>
              {quizMissed.length > 0 && (
                <div className="league-missed">
                  <p className="league-missed-lbl">{t("league.missedLbl")}</p>
                  {quizMissed.slice(0, 3).map((m) => (
                    <p className="league-missed-phrase" key={m}>{m}</p>
                  ))}
                </div>
              )}
            </>
          )}
          <button
            className="btn-primary league-start"
            onClick={() => nav(user?.plan === "free" ? "/subscribe" : "/")}
          >
            {t(weakCount > 0 ? "league.ctaUp" : "league.ctaKeep")}
          </button>
        </div>
      )}
    </div>
  );
}
