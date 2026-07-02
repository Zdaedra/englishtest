import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { api, CallUpgrade } from "../api";
import { IconBack } from "../ui/icons";
import { useI18n } from "../i18n";
import { useAuth } from "../auth/AuthContext";

// Call Analyzer (AI plan): paste notes / a rough transcript of a real meeting,
// get up to 5 native-league phrasing upgrades — then send them to the import
// flow to become trainable phrases. The bridge from the app to the user's job.
export default function Analyzer() {
  const nav = useNavigate();
  const { t } = useI18n();
  const { user } = useAuth();
  const isAI = user?.plan === "ai";
  const [text, setText] = useState("");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");
  const [upgrades, setUpgrades] = useState<CallUpgrade[] | null>(null);

  const run = async () => {
    if (!isAI) { nav("/subscribe"); return; }
    setErr(""); setBusy(true); setUpgrades(null);
    try {
      const r = await api.analyzeCall(text);
      setUpgrades(r.upgrades);
      if (r.via !== "llm") setErr(t("analyzer.unavailable"));
    } catch (e) {
      const msg = String(e);
      setErr(msg.includes("429") ? t("practice.limitReached")
        : msg.includes("400") ? t("analyzer.tooShort") : msg);
    } finally { setBusy(false); }
  };

  // Hand the upgrades to the import parser as "N. Anchor → phrase" lines — the
  // shape it already reads — so they become a private trainable batch.
  const toImport = () => {
    if (!upgrades?.length) return;
    const lines = upgrades.map((u, i) => {
      const anchor = (u.native.match(/[A-Za-z']{4,}/) || ["Phrase"])[0];
      return `${i + 1}. ${anchor} → ${u.native}`;
    });
    nav("/import", { state: { raw: `${t("analyzer.batchTitle")}\n${lines.join("\n")}` } });
  };

  return (
    <div className="screen">
      <button className="back-link" onClick={() => nav(-1)}>
        <IconBack size={18} /> {t("common.back")}
      </button>
      <div className="screen-head">
        <h1>{t("analyzer.title")}</h1>
        <p className="app-sub" style={{ marginBottom: 0 }}>{t("analyzer.sub")}</p>
      </div>

      <textarea
        className="paste"
        rows={8}
        placeholder={t("analyzer.placeholder")}
        value={text}
        onChange={(e) => setText(e.target.value)}
      />
      <button className="btn-primary" onClick={run} disabled={busy || text.trim().length < 40}>
        {busy ? "…" : isAI ? t("analyzer.run") : t("analyzer.runLocked")}
      </button>
      {err && <p className="form-err" role="alert">{err}</p>}

      {upgrades && upgrades.length === 0 && !err && (
        <p className="muted" style={{ marginTop: 16 }}>{t("analyzer.nothing")}</p>
      )}
      {upgrades && upgrades.length > 0 && (
        <div className="an-results">
          {upgrades.map((u, i) => (
            <div className="an-card" key={i}>
              {u.original && <p className="an-original">«{u.original}»</p>}
              <p className="an-native">{u.native}</p>
              {u.note && <p className="an-note">{u.note}</p>}
            </div>
          ))}
          <button className="btn-primary" onClick={toImport}>{t("analyzer.train")}</button>
        </div>
      )}
    </div>
  );
}
