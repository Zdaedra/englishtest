import { useEffect, useState } from "react";
import { api } from "../api";
import { useAuth } from "../auth/AuthContext";
import { useI18n } from "../i18n";

// Shown by <Shell> whenever the signed-in account hasn't confirmed its email.
// The magic link opens in the system browser and marks the account verified
// server-side; this screen polls /me (and re-checks on app focus) so the user
// flows straight into the app on return — no deep link needed.
export default function VerifyEmail() {
  const { user, refresh, logout } = useAuth();
  const { t } = useI18n();
  const [note, setNote] = useState("");
  const [busy, setBusy] = useState(false);
  const [editing, setEditing] = useState(false);
  const [email, setEmail] = useState("");

  useEffect(() => {
    const id = setInterval(() => { void refresh(); }, 5000);
    const onVis = () => { if (!document.hidden) void refresh(); };
    document.addEventListener("visibilitychange", onVis);
    return () => { clearInterval(id); document.removeEventListener("visibilitychange", onVis); };
  }, [refresh]);

  const resend = async () => {
    setBusy(true); setNote("");
    try { await api.resendVerification(); setNote(t("verify.sent")); }
    catch { setNote(t("verify.error")); }
    finally { setBusy(false); }
  };

  const saveEmail = async () => {
    const e = email.trim();
    if (!e) return;
    setBusy(true); setNote("");
    try { await api.changeEmail(e); await refresh(); setEditing(false); setNote(t("verify.sent")); }
    catch { setNote(t("verify.error")); }
    finally { setBusy(false); }
  };

  return (
    <div className="auth-screen">
      <div className="verify-card">
        <div className="verify-mark" aria-hidden>✉️</div>
        <h1 className="verify-title">{t("verify.title")}</h1>
        <p className="verify-body">{t("verify.body", { email: user?.email ?? "" })}</p>

        {editing ? (
          <div className="verify-edit">
            <input
              className="verify-input" type="email" inputMode="email" autoCapitalize="none"
              placeholder={user?.email ?? ""} value={email}
              onChange={(ev) => setEmail(ev.target.value)}
            />
            <button className="sub-buy primary" disabled={busy} onClick={saveEmail}>
              {busy ? "…" : t("verify.changeSave")}
            </button>
            <button className="verify-link" onClick={() => setEditing(false)}>{t("profile.emailCancel")}</button>
          </div>
        ) : (
          <>
            <button className="sub-buy primary" disabled={busy} onClick={() => { void refresh(); }}>
              {t("verify.refresh")}
            </button>
            <button className="sub-buy" disabled={busy} onClick={resend}>
              {busy ? "…" : t("verify.resend")}
            </button>
            <button className="verify-link" onClick={() => { setEmail(""); setEditing(true); }}>
              {t("verify.wrongEmail")}
            </button>
          </>
        )}

        {note && <p className="verify-note">{note}</p>}
        <button className="verify-logout" onClick={() => logout()}>{t("verify.logout")}</button>
      </div>
    </div>
  );
}
