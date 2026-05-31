import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "../api";
import { IconBack } from "../ui/icons";

const PLACEHOLDER = `Восхождение — лестница несогласия
Curious (1-3)
1. Understand → Help me understand the thinking there.
2. Walk → Walk me through how you got to that number.
3. Read → I read the situation differently.
Мнемо-текст: Ты хочешь UNDERSTAND гору, поэтому WALK к тропе и READ карту.`;

export default function ImportBatch() {
  const nav = useNavigate();
  const [raw, setRaw] = useState("");
  const [useLlm, setUseLlm] = useState(false);
  const [preview, setPreview] = useState<any>(null);
  const [warnings, setWarnings] = useState<string[]>([]);
  const [parser, setParser] = useState("");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");

  const doParse = async () => {
    setErr(""); setBusy(true);
    try {
      const r = await api.parse(raw, useLlm);
      setPreview(r.batch); setWarnings(r.warnings); setParser(r.parser);
    } catch (e) { setErr(String(e)); } finally { setBusy(false); }
  };

  const editPhrase = (i: number, field: string, val: string) => {
    const p = { ...preview };
    p.phrases[i] = { ...p.phrases[i], [field]: val };
    setPreview(p);
  };

  const doCommit = async () => {
    setErr(""); setBusy(true);
    try {
      const r = await api.commit(preview);
      nav(`/batch/${r.id}`);
    } catch (e) { setErr(String(e)); } finally { setBusy(false); }
  };

  return (
    <div className="screen">
      <button className="back-link" onClick={() => nav("/profile")}>
        <IconBack /> Profile
      </button>
      <div className="screen-head">
        <h1>Import a batch</h1>
        <p className="app-sub" style={{ marginBottom: 0 }}>
          Paste raw text. The parser reads “N. Keyword → phrase” lines and a “Мнемо-текст:” block.
        </p>
      </div>

      <textarea
        className="paste"
        rows={10}
        placeholder={PLACEHOLDER}
        value={raw}
        onChange={(e) => setRaw(e.target.value)}
      />
      <label className="check" style={{ margin: "12px 0" }}>
        <input type="checkbox" checked={useLlm} onChange={(e) => setUseLlm(e.target.checked)} />
        Use LLM (for non-standard text)
      </label>
      <div className="row">
        <button className="btn btn-primary" onClick={doParse} disabled={busy || !raw.trim()}>
          Parse
        </button>
      </div>
      {err && <p className="error">{err}</p>}

      {preview && (
        <div className="preview">
          <p className="section-label">Preview · parser: {parser}</p>
          {warnings.length > 0 && (
            <ul className="warn">{warnings.map((w, i) => <li key={i}>⚠ {w}</li>)}</ul>
          )}
          <label className="field">
            <span className="field-label">Title</span>
            <input value={preview.title} onChange={(e) => setPreview({ ...preview, title: e.target.value })} />
          </label>
          <table className="phrases">
            <thead>
              <tr><th>#</th><th>Anchor</th><th>Phrase (EN)</th><th>Gloss (RU)</th><th>Zone</th></tr>
            </thead>
            <tbody>
              {preview.phrases.map((p: any, i: number) => (
                <tr key={i}>
                  <td>{p.order_index}</td>
                  <td><input value={p.anchor} onChange={(e) => editPhrase(i, "anchor", e.target.value)} /></td>
                  <td><input value={p.phrase_en} onChange={(e) => editPhrase(i, "phrase_en", e.target.value)} /></td>
                  <td><input value={p.gloss_ru} onChange={(e) => editPhrase(i, "gloss_ru", e.target.value)} /></td>
                  <td className="muted small">{p.zone || "—"}</td>
                </tr>
              ))}
            </tbody>
          </table>
          <p className="section-label" style={{ marginTop: 18 }}>
            Mnemonic · {preview.mnemo.spans.length} anchors
          </p>
          <textarea
            className="paste"
            rows={3}
            value={preview.mnemo.story_ru}
            onChange={(e) => setPreview({ ...preview, mnemo: { ...preview.mnemo, story_ru: e.target.value } })}
          />
          <div className="row">
            <button className="btn btn-primary" onClick={doCommit} disabled={busy}>Save batch</button>
          </div>
        </div>
      )}
    </div>
  );
}
