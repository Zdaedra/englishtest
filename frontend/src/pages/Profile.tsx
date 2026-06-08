import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "../api";
import { useAuth } from "../auth/AuthContext";
import { IconGear, IconImport, IconInfo, IconChevron } from "../ui/icons";

function initials(name: string, email: string): string {
  const src = (name || email || "?").trim();
  const parts = src.split(/\s+/).filter(Boolean);
  if (parts.length >= 2) return (parts[0][0] + parts[1][0]).toUpperCase();
  return src.slice(0, 2).toUpperCase();
}

export default function Profile() {
  const nav = useNavigate();
  const { user, logout } = useAuth();
  const [count, setCount] = useState<number | null>(null);
  const [note, setNote] = useState("");
  const isAI = user?.plan === "ai";
  const canImport = !!user?.entitlements?.import;
  const isAdmin = !!user?.is_admin;

  useEffect(() => {
    api.listBatches().then((b) => setCount(b.length)).catch(() => setCount(null));
  }, []);

  const upgrade = () =>
    setNote("Подписка скоро — в бете доступно всё. Сообщим, когда откроем оплату.");

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
        <p className="muted small" style={{ margin: 0 }}>Executive English Member</p>
        <p className="muted small" style={{ marginTop: 2 }}>
          {count == null ? "—" : `${count} pattern set${count === 1 ? "" : "s"} in your library`}
        </p>
      </div>

      {/* Current plan — the cabinet's most important block */}
      <div className="plan-card">
        <span className="plan-eyebrow">Current Plan</span>
        <div className="plan-name">{isAI ? "Executive AI" : "Executive Core"}</div>
        <div className="plan-sub">
          {isAI ? "AI Coach включён · полный доступ" : "Библиотека · Обучение · Практика"}
        </div>
        <button className="plan-action" onClick={upgrade}>
          {isAI ? "Управлять →" : "Перейти на Executive AI →"}
        </button>
      </div>

      {/* AI Coach */}
      <button className="cab-card" onClick={() => (isAI ? nav("/practice") : upgrade())}>
        <span className="cab-ico">✦</span>
        <div className="cab-body">
          <div className="cab-title">AI Coach</div>
          <div className="cab-sub">Разбор ответов, тон и лучшие формулировки</div>
        </div>
        <span className={`cab-right${isAI ? " on" : ""}`}>{isAI ? "Включён" : "Открыть →"}</span>
      </button>

      {note && <p className="muted small center" style={{ margin: "12px 4px 0" }}>{note}</p>}

      <div className="menu" style={{ marginTop: 18 }}>
        {canImport && row(IconImport, "Import a batch", "Вставить новый набор фраз", "/import")}
        {isAdmin && row(IconGear, "Listening", "Голос, скорость и паузы", "/settings")}
        {row(IconInfo, "About", "Executive English — premium communication trainer", "/profile")}
      </div>

      <button className="auth-logout" onClick={() => logout()}>Выйти</button>
    </div>
  );
}
