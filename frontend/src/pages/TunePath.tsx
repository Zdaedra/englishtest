import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { getStrategy, setStrategy } from "../lib/profile";
import { FOCUSES, NEEDS, Intensity } from "../lib/strategy";
import { IconBack, IconCheck } from "../ui/icons";

const INTENSITIES: { key: Intensity; label: string; hint: string }[] = [
  { key: "narrow", label: "Узкий фокус", hint: "Почти всё — про выбранное" },
  { key: "balanced", label: "Сбалансированно", hint: "Фокус + подмешиваем соседнее" },
  { key: "explore", label: "Исследовать", hint: "Шире, разные направления" },
];

export default function TunePath() {
  const nav = useNavigate();
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
      if (prev.length >= 2) return prev; // cap at 2
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
    nav("/learn", { replace: true });
  };

  return (
    <div className="screen tune">
      <button className="back-link" onClick={() => nav(-1)}>
        <IconBack size={18} /> Назад
      </button>

      <div className="screen-head">
        <h1 className="app-title">Настроить траекторию</h1>
        <p className="app-sub">Под что собрать спринт — меняй когда угодно, путь перестроится.</p>
      </div>

      <p className="section-label">Что предстоит?</p>
      <div className="quest-opts">
        {NEEDS.map((n) => {
          const sel = need === n.key;
          return (
            <button key={n.key} className={`quest-opt${sel ? " sel" : ""}`} onClick={() => pickNeed(n)}>
              <span className="qo-body"><span className="qo-label">{n.label}</span></span>
              {sel && <span className="qo-check"><IconCheck size={14} /></span>}
            </button>
          );
        })}
      </div>

      <p className="section-label" style={{ marginTop: 22 }}>Главный фокус</p>
      <div className="quest-opts">
        {FOCUSES.map((f) => {
          const sel = main === f.key;
          return (
            <button key={f.key} className={`quest-opt${sel ? " sel" : ""}`} onClick={() => pickMain(f.key)}>
              <span className="qo-body"><span className="qo-label">{f.ru}</span></span>
              {sel && <span className="qo-check"><IconCheck size={14} /></span>}
            </button>
          );
        })}
      </div>

      <p className="section-label" style={{ marginTop: 22 }}>Дополнительно (0–2)</p>
      <div className="quest-opts">
        {FOCUSES.filter((f) => f.key !== main).map((f) => {
          const sel = secondary.includes(f.key);
          return (
            <button key={f.key} className={`quest-opt${sel ? " sel" : ""}`} onClick={() => toggleSecondary(f.key)}>
              <span className="qo-body"><span className="qo-label">{f.ru}</span></span>
              {sel && <span className="qo-check"><IconCheck size={14} /></span>}
            </button>
          );
        })}
      </div>

      <p className="section-label" style={{ marginTop: 22 }}>Интенсивность</p>
      <div className="quest-opts">
        {INTENSITIES.map((it) => {
          const sel = intensity === it.key;
          return (
            <button key={it.key} className={`quest-opt${sel ? " sel" : ""}`} onClick={() => setIntensity(it.key)}>
              <span className="qo-body">
                <span className="qo-label">{it.label}</span>
                <span className="qo-hint">{it.hint}</span>
              </span>
              {sel && <span className="qo-check"><IconCheck size={14} /></span>}
            </button>
          );
        })}
      </div>

      <p className="section-label" style={{ marginTop: 22 }}>Размер спринта</p>
      <div className="tune-sizes">
        {[3, 5, 7].map((n) => (
          <button
            key={n}
            className={`tune-size${sprintSize === n ? " sel" : ""}`}
            onClick={() => setSprintSize(n)}
          >
            {n}
          </button>
        ))}
      </div>

      <button className="btn btn-primary btn-block quest-cta" onClick={save}>
        Перестроить путь
      </button>
    </div>
  );
}
