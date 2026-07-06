import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { getStrategy, setStrategy, paceFromLeague, getPlanMode, setPlanMode, manualIds } from "../lib/profile";
import { getLeagueResult } from "../lib/league";
import { tg } from "../i18n";
import { clearAllPathRanks } from "../lib/progress";
import { FOCUSES, NEEDS, Intensity } from "../lib/strategy";
import { IconBack, IconCheck } from "../ui/icons";
import { useI18n } from "../i18n";

const INTENSITIES: { key: Intensity }[] = [
  { key: "narrow" }, { key: "balanced" }, { key: "explore" },
];

export default function TunePath() {
  const nav = useNavigate();
  const { t } = useI18n();
  const init = getStrategy();
  const [main, setMain] = useState(init.main);
  const [secondary, setSecondary] = useState<string[]>(init.secondary);
  const [intensity, setIntensity] = useState<Intensity>(init.intensity);
  const [sprintSize, setSprintSize] = useState<number>(init.sprintSize);
  const [need, setNeed] = useState<string | undefined>(init.need);

  const pickMain = (key: string) => {
    setMain(key);
    setSecondary((prev) => prev.filter((k) => k !== key));
  };
  const toggleSecondary = (key: string) =>
    setSecondary((prev) => {
      if (prev.includes(key)) return prev.filter((k) => k !== key);
      if (prev.length >= 3) return prev; // cap at 3 (main + 3 = 4 goals)
      return [...prev, key];
    });
  const pickNeed = (n: { key: string; focus: string }) => {
    if (need === n.key) {
      setNeed(undefined);
      return;
    }
    // A current need really changes the weights: it becomes the main focus.
    setNeed(n.key);
    setMain(n.focus);
    setSecondary((prev) => prev.filter((k) => k !== n.focus));
  };

  const save = () => {
    setStrategy({ main, secondary, intensity, sprintSize, need });
    // A new focus mix re-apportions the plan — drop stale manual drag order.
    clearAllPathRanks();
    nav("/learn", { replace: true });
  };

  return (
    <div className="screen tune">
      <button className="back-link" onClick={() => nav("/learn")}>
        <IconBack size={18} /> {t("common.back")}
      </button>

      <div className="screen-head">
        <h1 className="app-title">{t("tune.title")}</h1>
        <p className="app-sub">{t("tune.sub")}</p>
      </div>

      <p className="section-label">{t("tune.planMode")}</p>
      <div className="tune-modes">
        {(["auto", "manual"] as const).map((m) => (
          <button
            key={m}
            className={`tune-size tune-mode${getPlanMode() === m ? " sel" : ""}`}
            aria-pressed={getPlanMode() === m}
            onClick={() => setPlanMode(m)}
          >
            {t(m === "auto" ? "plan.modeAuto" : "plan.modeManual")}
            <span className="tune-mode-sub">
              {m === "auto" ? t("tune.modeAutoDesc") : t("tune.modeManualDesc", { n: manualIds().length })}
            </span>
          </button>
        ))}
      </div>
      <p className="tune-league-note">{t("tune.archiveNote")}</p>

      <p className="section-label">{t("tune.whatsUp")}</p>
      <div className="quest-opts">
        {NEEDS.map((n) => {
          const sel = need === n.key;
          return (
            <button key={n.key} className={`quest-opt${sel ? " sel" : ""}`} aria-pressed={sel} onClick={() => pickNeed(n)}>
              <span className="qo-body"><span className="qo-label">{t(`need.${n.key}`)}</span></span>
              {sel && <span className="qo-check"><IconCheck size={14} /></span>}
            </button>
          );
        })}
      </div>

      <p className="section-label" style={{ marginTop: 22 }}>{t("tune.mainFocus")}</p>
      <div className="quest-opts">
        {FOCUSES.map((f) => {
          const sel = main === f.key;
          return (
            <button key={f.key} className={`quest-opt${sel ? " sel" : ""}`} aria-pressed={sel} onClick={() => pickMain(f.key)}>
              <span className="qo-body"><span className="qo-label">{t(`focus.${f.key}`)}</span></span>
              {sel && <span className="qo-check"><IconCheck size={14} /></span>}
            </button>
          );
        })}
      </div>

      <p className="section-label" style={{ marginTop: 22 }}>{t("tune.secondary")}</p>
      <div className="quest-opts">
        {FOCUSES.filter((f) => f.key !== main).map((f) => {
          const sel = secondary.includes(f.key);
          return (
            <button key={f.key} className={`quest-opt${sel ? " sel" : ""}`} aria-pressed={sel} onClick={() => toggleSecondary(f.key)}>
              <span className="qo-body"><span className="qo-label">{t(`focus.${f.key}`)}</span></span>
              {sel && <span className="qo-check"><IconCheck size={14} /></span>}
            </button>
          );
        })}
      </div>

      <p className="section-label" style={{ marginTop: 22 }}>{t("tune.intensity")}</p>
      <div className="quest-opts">
        {INTENSITIES.map((it) => {
          const sel = intensity === it.key;
          return (
            <button key={it.key} className={`quest-opt${sel ? " sel" : ""}`} aria-pressed={sel} onClick={() => setIntensity(it.key)}>
              <span className="qo-body">
                <span className="qo-label">{t(`tune.${it.key}`)}</span>
                <span className="qo-hint">{t(`tune.${it.key}Hint`)}</span>
              </span>
              {sel && <span className="qo-check"><IconCheck size={14} /></span>}
            </button>
          );
        })}
      </div>

      <p className="section-label" style={{ marginTop: 22 }}>{t("tune.sprintSize")}</p>
      {paceFromLeague() && (
        <p className="tune-league-note">
          {t("tune.leagueNote", { tier: tg(`league.name.${getLeagueResult()!.tier}`) })}
        </p>
      )}
      <div className="tune-sizes">
        {[3, 5, 7].map((n) => (
          <button
            key={n}
            className={`tune-size${sprintSize === n ? " sel" : ""}`}
            aria-pressed={sprintSize === n}
            onClick={() => setSprintSize(n)}
          >
            {n}
          </button>
        ))}
      </div>

      <button className="btn btn-primary btn-block quest-cta" onClick={save}>
        {t("tune.rebuild")}
      </button>
    </div>
  );
}
