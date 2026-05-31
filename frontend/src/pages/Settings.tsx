import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "../api";
import { IconBack } from "../ui/icons";

const VOICES = ["alloy", "echo", "fable", "onyx", "nova", "shimmer"];

export default function Settings() {
  const nav = useNavigate();
  const [s, setS] = useState<any>(null);
  const [saved, setSaved] = useState(false);

  useEffect(() => { api.getSettings().then(setS); }, []);

  const set = (k: string, v: any) => { setS({ ...s, [k]: v }); setSaved(false); };
  const save = async () => { await api.putSettings(s); setSaved(true); };
  const num = (k: string, label: string, step = 0.5) => (
    <label className="field">
      <span className="field-label">{label}</span>
      <input type="number" step={step} value={s[k]} onChange={(e) => set(k, Number(e.target.value))} />
    </label>
  );

  return (
    <div className="screen">
      <button className="back-link" onClick={() => nav("/profile")}>
        <IconBack /> Profile
      </button>
      <div className="screen-head"><h1>Voice & playback</h1></div>

      {!s ? (
        <p className="muted">Loading…</p>
      ) : (
        <>
          <label className="field">
            <span className="field-label">Voice (EN)</span>
            <select value={s.tts_voice} onChange={(e) => set("tts_voice", e.target.value)}>
              {VOICES.map((v) => <option key={v}>{v}</option>)}
            </select>
          </label>
          <label className="field">
            <span className="field-label">Voice (RU stimulus)</span>
            <select value={s.tts_voice_ru} onChange={(e) => set("tts_voice_ru", e.target.value)}>
              {VOICES.map((v) => <option key={v}>{v}</option>)}
            </select>
          </label>
          <label className="field">
            <span className="field-label">TTS model</span>
            <select value={s.tts_model} onChange={(e) => set("tts_model", e.target.value)}>
              <option value="tts-1">tts-1 (fast / cheap)</option>
              <option value="tts-1-hd">tts-1-hd (quality)</option>
            </select>
          </label>
          {num("tts_speed", "Speed", 0.05)}
          {num("recall_gap_stimulus", "Think pause (sec)")}
          {num("recall_gap_after", "Pause after answer (sec)")}
          {num("listening_gap", "Listening pause (sec)")}
          {num("listening_repeats", "Listening repeats", 1)}
          <label className="field">
            <span className="field-label">Default order</span>
            <select value={s.default_order_mode} onChange={(e) => set("default_order_mode", e.target.value)}>
              <option value="ordered">In order</option>
              <option value="zone_random">Random within zone</option>
              <option value="full_random">Full random</option>
            </select>
          </label>
          <div className="row">
            <button className="btn btn-primary" onClick={save}>Save</button>
            {saved && <span className="saved">✓ saved</span>}
          </div>
        </>
      )}
    </div>
  );
}
