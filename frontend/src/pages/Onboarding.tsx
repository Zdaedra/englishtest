import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { setProfile, SCENARIOS } from "../lib/profile";
import { IconBack, IconCheck } from "../ui/icons";

// One question, on purpose: what does the learner actually need English for?
// The chosen scenarios are the whole strategy — they reorder the path so the
// sections that matter for those tasks lead. No level test, no self-rating: the
// drills adapt difficulty on their own as the learner goes.
export default function Onboarding() {
  const nav = useNavigate();
  const [scenarios, setScenarios] = useState<string[]>([]);

  const toggle = (key: string) =>
    setScenarios((prev) => {
      if (prev.includes(key)) return prev.filter((k) => k !== key);
      if (prev.length >= 2) return prev; // cap at 2 — keep the start focused
      return [...prev, key];
    });

  const finish = () => {
    setProfile({ scenarios, onboardedAt: new Date().toISOString() });
    nav("/learn", { replace: true });
  };

  return (
    <div className="screen quest">
      <button className="back-link" onClick={() => nav("/", { replace: true })}>
        <IconBack /> Позже
      </button>

      <div className="quest-step">
        <h1 className="quest-q">Где английский нужен сильнее всего?</h1>
        <p className="app-sub">
          Выбери 1–2 — с них и соберём траекторию. Уровень подстроится сам по ходу.
        </p>
        <div className="quest-opts">
          {SCENARIOS.map((o) => {
            const sel = scenarios.includes(o.key);
            return (
              <button
                key={o.key}
                className={`quest-opt${sel ? " sel" : ""}`}
                onClick={() => toggle(o.key)}
              >
                <span className="qo-body">
                  <span className="qo-label">{o.label}</span>
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
        Построить траекторию
      </button>
    </div>
  );
}
