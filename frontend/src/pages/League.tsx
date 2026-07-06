import { useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { IconBack } from "../ui/icons";
import { useI18n } from "../i18n";
import { useAuth } from "../auth/AuthContext";
import {
  LEAGUE_QS, LeagueOption, leagueOf, saveLeagueResult,
} from "../lib/league";

// "Check your English league" — a 3-minute placement test. Every option is
// correct English; the learner picks what they'd MOST LIKELY say. The result
// frames the product promise: the gap between correct and native-league.
export default function League() {
  const nav = useNavigate();
  const { t } = useI18n();
  const { user } = useAuth();
  const [step, setStep] = useState(-1);            // -1 intro · 0..N-1 quiz · N result
  const [picks, setPicks] = useState<LeagueOption[]>([]);

  // Shuffle options once per mount so the native answer isn't positionally learnable.
  const shuffled = useMemo(
    () => LEAGUE_QS.map((q) => ({
      ...q,
      options: [...q.options].sort(() => Math.random() - 0.5),
    })),
    []
  );

  const total = shuffled.length;
  const done = step >= total;
  const score = picks.filter((p) => p.native).length;
  const tier = leagueOf(score);
  const missed = LEAGUE_QS
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

  return (
    <div className="screen league-screen">
      <button className="back-link" onClick={() => nav("/")}>
        <IconBack size={18} /> {t("common.back")}
      </button>

      {step === -1 && (
        <div className="league-intro">
          <h1 className="league-title">{t("league.title")}</h1>
          <p className="league-sub">{t("league.intro")}</p>
          <p className="league-note">{t("league.introNote", { n: total })}</p>
          <button className="btn-primary league-start" onClick={() => setStep(0)}>
            {t("league.start")}
          </button>
        </div>
      )}

      {step >= 0 && !done && (
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
          <p className="league-score">{t("league.score", { s: score, n: total })}</p>
          {missed.length > 0 && (
            <div className="league-missed">
              <p className="league-missed-lbl">{t("league.missedLbl")}</p>
              {missed.slice(0, 3).map((m) => (
                <p className="league-missed-phrase" key={m}>{m}</p>
              ))}
            </div>
          )}
          <button
            className="btn-primary league-start"
            onClick={() => nav(user?.plan === "free" ? "/subscribe" : "/")}
          >
            {t(missed.length > 0 ? "league.ctaUp" : "league.ctaKeep")}
          </button>
        </div>
      )}
    </div>
  );
}
