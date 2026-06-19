import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "../api";
import { useAuth } from "../auth/AuthContext";
import { useI18n, LANGS } from "../i18n";
import LangSwitcher from "../ui/LangSwitcher";
import { IconGear, IconImport, IconInfo, IconChevron } from "../ui/icons";
import { isNative } from "../lib/session";
import { remindersEnabled, enableReminders, disableReminders } from "../lib/reminders";

function initials(name: string, email: string): string {
  const src = (name || email || "?").trim();
  const parts = src.split(/\s+/).filter(Boolean);
  if (parts.length >= 2) return (parts[0][0] + parts[1][0]).toUpperCase();
  return src.slice(0, 2).toUpperCase();
}

export default function Profile() {
  const nav = useNavigate();
  const { user, logout } = useAuth();
  const { t, lang } = useI18n();
  const [count, setCount] = useState<number | null>(null);
  const [confirmDel, setConfirmDel] = useState(false);
  const [delBusy, setDelBusy] = useState(false);
  const native = isNative();
  const [remOn, setRemOn] = useState(remindersEnabled());
  const toggleRem = async () => {
    if (remOn) { await disableReminders(); setRemOn(false); }
    else { setRemOn(await enableReminders()); }
  };
  const isAI = user?.plan === "ai";
  const canImport = !!user?.entitlements?.import;
  const isAdmin = !!user?.is_admin;
  const langLabel = LANGS.find((l) => l.code === lang)?.label ?? lang;

  useEffect(() => {
    api.listBatches().then((b) => setCount(b.length)).catch(() => setCount(null));
  }, []);

  const upgrade = () => nav("/subscribe");

  const doDelete = async () => {
    setDelBusy(true);
    try { await api.deleteAccount(); } catch { /* fall through to logout */ }
    await logout();
  };

  const row = (
    Icon: (p: { size?: number }) => JSX.Element,
    title: string,
    sub: string,
    to: string
  ) => (
    <button className="menu-row" onClick={() => nav(to)}>
      <span className="menu-ico"><Icon size={19} /></span>
      <div className="menu-body">
        <div className="menu-title">{title}</div>
        <div className="menu-sub">{sub}</div>
      </div>
      <span className="menu-chevron"><IconChevron /></span>
    </button>
  );

  return (
    <div className="screen">
      <div className="screen-head" style={{ textAlign: "center" }}>
        <div className="avatar" style={{ margin: "0 auto 14px" }}>
          {initials(user?.name || "", user?.email || "")}
        </div>
        <h1 style={{ marginBottom: 2 }}>{user?.name?.trim() || user?.email || "—"}</h1>
        <p className="muted small" style={{ margin: 0 }}>{t("profile.member")}</p>
        <p className="muted small" style={{ marginTop: 2 }}>
          {count == null ? "—" : t("profile.libCount", { n: count })}
        </p>
      </div>

      {/* Current plan — the cabinet's most important block */}
      <div className="plan-card">
        <span className="plan-eyebrow">{t("plan.eyebrow")}</span>
        <div className="plan-name">{isAI ? "Executive AI" : "Executive Core"}</div>
        <div className="plan-sub">{isAI ? t("plan.subAI") : t("plan.subCore")}</div>
        <button className="plan-action" onClick={upgrade}>
          {isAI ? t("plan.actionAI") : t("plan.actionCore")}
        </button>
      </div>

      {/* AI Coach */}
      <button className="cab-card" onClick={() => (isAI ? nav("/practice") : upgrade())}>
        <span className="cab-ico">✦</span>
        <div className="cab-body">
          <div className="cab-title">AI Coach</div>
          <div className="cab-sub">{t("profile.aiCoachSub")}</div>
        </div>
        <span className={`cab-right${isAI ? " on" : ""}`}>{isAI ? t("profile.aiCoachOn") : t("profile.aiCoachOpen")}</span>
      </button>

      <div className="menu" style={{ marginTop: 18 }}>
        {/* Interface language */}
        <div className="menu-row menu-row-static">
          <span className="menu-ico" aria-hidden>🌐</span>
          <div className="menu-body">
            <div className="menu-title">{t("lang.label")}</div>
            <div className="menu-sub">{langLabel}</div>
          </div>
          <LangSwitcher variant="pill" />
        </div>
        {canImport && row(IconImport, t("profile.importTitle"), t("profile.importSub"), "/import")}
        {isAdmin && row(IconGear, t("profile.listeningTitle"), t("profile.listeningSub"), "/settings")}
        {/* Daily review reminder — native only (local notification). */}
        {native && (
          <button className="menu-row" onClick={toggleRem} role="switch" aria-checked={remOn}>
            <span className="menu-ico" aria-hidden>
              <svg viewBox="0 0 24 24" width="19" height="19" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <path d="M18 8a6 6 0 0 0-12 0c0 7-3 9-3 9h18s-3-2-3-9" /><path d="M13.7 21a2 2 0 0 1-3.4 0" />
              </svg>
            </span>
            <div className="menu-body">
              <div className="menu-title">{t("profile.reminderTitle")}</div>
              <div className="menu-sub">{t("profile.reminderSub")}</div>
            </div>
            <span className={"switch" + (remOn ? " on" : "")} aria-hidden><span className="switch-knob" /></span>
          </button>
        )}
        {row(IconInfo, t("profile.aboutTitle"), t("profile.aboutSub"), "/profile")}
      </div>

      <button className="auth-logout" onClick={() => logout()}>{t("profile.logout")}</button>

      {!confirmDel ? (
        <button className="cab-danger" onClick={() => setConfirmDel(true)}>{t("account.delete")}</button>
      ) : (
        <div className="cab-danger-box">
          <p className="cab-danger-q">{t("account.deleteConfirm")}</p>
          <div className="cab-danger-row">
            <button className="cab-danger-cancel" onClick={() => setConfirmDel(false)}>{t("account.deleteCancel")}</button>
            <button className="cab-danger-yes" disabled={delBusy} onClick={doDelete}>
              {delBusy ? "…" : t("account.deleteYes")}
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
