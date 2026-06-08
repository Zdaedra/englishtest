import { useState } from "react";
import { api } from "../api";
import { setProgress } from "../lib/progress";

const SLIDES = [
  {
    title: "Executive English",
    body: "Это не про грамматику. Это про то, как тебя воспринимают в высокоставочных разговорах — питч, переговоры, давление, несогласие.",
  },
  {
    title: "Карточка — момент разговора",
    body: "Кто-то это сказал. Что ты ответишь? Свайпни вправо, если знаешь, влево — если нет. Или произнеси ответ голосом.",
  },
  {
    title: "Готов начать?",
    body: "Откроем тебе первый набор фраз — и сразу в практику.",
  },
];

export default function OnboardingFlow({ onDone }: { onDone: () => void }) {
  const [i, setI] = useState(0);
  const [busy, setBusy] = useState(false);
  const last = i === SLIDES.length - 1;

  const next = async () => {
    if (!last) { setI(i + 1); return; }
    setBusy(true);
    try {
      const batches = await api.listBatches().catch(() => []);
      if (batches.length) setProgress(batches[0].id, { activated: true });
    } catch { /* non-critical */ }
    onDone();
  };

  const s = SLIDES[i];
  return (
    <div className="ob-screen">
      <div className="ob-dots">
        {SLIDES.map((_, k) => <span key={k} className={k === i ? "on" : ""} />)}
      </div>
      <div className="ob-body">
        <h1 className="ob-title">{s.title}</h1>
        <p className="ob-text">{s.body}</p>
      </div>
      <div className="ob-foot">
        <button className="l3-cta" onClick={next} disabled={busy}>
          {busy ? "…" : last ? "Начать" : "Дальше"}
        </button>
        {!last && <button className="ob-skip" type="button" onClick={onDone}>Пропустить</button>}
      </div>
    </div>
  );
}
