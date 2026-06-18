import { FormEvent, useState } from "react";
import { useAuth } from "../auth/AuthContext";
import { useI18n } from "../i18n";
import LangSwitcher from "../ui/LangSwitcher";

function humanize(s: string, t: (k: string, vars?: Record<string, string | number>) => string): string {
  try {
    const d = JSON.parse(s.replace(/^Error:\s*/, ""))?.detail;
    if (d && typeof d === "object" && d.code) {
      const key = `auth.err.${d.code}`;
      const out = t(key, d.min != null ? { min: d.min } : undefined);
      if (out !== key) return out;            // localized
      if (typeof d.msg === "string") return d.msg; // server-provided fallback
    }
    if (typeof d === "string") return d;      // legacy string detail
  } catch { /* not JSON */ }
  if (s.includes("401")) return t("auth.err.bad_credentials");
  return t("auth.errGeneric");
}

export default function AuthScreen() {
  const { login, register } = useAuth();
  const { t } = useI18n();
  const [mode, setMode] = useState<"login" | "register">("login");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [name, setName] = useState("");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    setErr("");
    setBusy(true);
    try {
      if (mode === "login") await login(email.trim(), password);
      else await register(email.trim(), password, name.trim());
    } catch (e2) {
      setErr(humanize(String(e2), t));
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="auth-screen">
      <div className="auth-topbar"><LangSwitcher /></div>
      <div className="auth-card">
        <div className="auth-brand">Executive English</div>
        <p className="auth-tag">
          {mode === "login" ? t("auth.tagLogin") : t("auth.tagRegister")}
        </p>
        <form onSubmit={submit}>
          {mode === "register" && (
            <input className="auth-input" type="text" placeholder={t("auth.name")} autoComplete="name"
              value={name} onChange={(e) => setName(e.target.value)} />
          )}
          <input className="auth-input" type="email" placeholder="Email" autoComplete="email"
            autoCapitalize="none" value={email} onChange={(e) => setEmail(e.target.value)} required />
          <input className="auth-input" type="password" placeholder={t("auth.password")}
            autoComplete={mode === "login" ? "current-password" : "new-password"}
            value={password} onChange={(e) => setPassword(e.target.value)} required />
          {err && <p className="auth-err" role="alert">{err}</p>}
          <button className="l3-cta" type="submit" disabled={busy} style={{ marginTop: 6 }}>
            {busy ? "…" : mode === "login" ? t("auth.login") : t("auth.register")}
          </button>
        </form>
        <button className="auth-toggle" type="button"
          onClick={() => { setMode(mode === "login" ? "register" : "login"); setErr(""); }}>
          {mode === "login" ? t("auth.toRegister") : t("auth.toLogin")}
        </button>
      </div>
    </div>
  );
}
