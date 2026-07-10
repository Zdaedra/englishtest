import { ChangeEvent, PointerEvent as RPointerEvent, useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "../api";
import { useAuth } from "../auth/AuthContext";
import { resetTours } from "../tutorial/tours";
import { resetTips } from "../tutorial/teach";
import { useI18n, LANGS } from "../i18n";
import LangSwitcher from "../ui/LangSwitcher";
import HeroGenderSwitcher from "../ui/HeroGenderSwitcher";
import { IconGear, IconImport, IconInfo, IconChevron, IconWave } from "../ui/icons";
import { isNative } from "../lib/session";
import { remindersEnabled, enableReminders, disableReminders, getReminderTime, setReminderTime, notifPermission } from "../lib/reminders";
import { getLeagueResult } from "../lib/league";
import { widgetInstalled } from "../lib/widget";
import WidgetHowto from "../ui/WidgetHowto";
import { getAvatar, saveAvatar } from "../lib/avatar";

const CROP = 280;   // editor viewport (display px); output is rendered to 256²

function initials(name: string, email: string): string {
  const src = (name || email || "?").trim();
  const parts = src.split(/\s+/).filter(Boolean);
  if (parts.length >= 2) return (parts[0][0] + parts[1][0]).toUpperCase();
  return src.slice(0, 2).toUpperCase();
}

export default function Profile() {
  const nav = useNavigate();
  const { user, logout, refresh } = useAuth();
  const { t, lang } = useI18n();
  const leagueRes = getLeagueResult();   // league row: current tier or "take the test"
  // Widget row (native): live install status + the how-to sheet.
  const [widgetOn, setWidgetOn] = useState(false);
  const [widgetHowto, setWidgetHowto] = useState(false);
  useEffect(() => { widgetInstalled().then(setWidgetOn).catch(() => {}); }, []);
  const [count, setCount] = useState<number | null>(null);
  const [avatar, setAvatar] = useState<string | null>(null);
  const [editorSrc, setEditorSrc] = useState<string | null>(null);   // crop editor open?
  const [zoom, setZoom] = useState(1);
  const [pos, setPos] = useState({ x: 0, y: 0 });
  const natRef = useRef({ w: 1, h: 1 });
  const fileRef = useRef<HTMLInputElement | null>(null);
  const imgRef = useRef<HTMLImageElement | null>(null);
  const curPosRef = useRef({ x: 0, y: 0 });   // live pan during drag (no re-render)
  const dragRef = useRef<{ x: number; y: number; px: number; py: number } | null>(null);
  const [confirmDel, setConfirmDel] = useState(false);
  const [delBusy, setDelBusy] = useState(false);
  const [exporting, setExporting] = useState(false);
  const exportMyData = async () => {
    setExporting(true);
    try {
      const data = await api.exportData();
      const blob = new Blob([JSON.stringify(data, null, 2)], { type: "application/json" });
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url; a.download = "executive-english-data.json";
      document.body.appendChild(a); a.click(); a.remove();
      setTimeout(() => URL.revokeObjectURL(url), 1000);
    } catch { /* non-critical */ }
    setExporting(false);
  };
  const [editEmail, setEditEmail] = useState(false);
  const [newEmail, setNewEmail] = useState("");
  const [emailNote, setEmailNote] = useState("");
  const [emailBusy, setEmailBusy] = useState(false);
  const native = isNative();
  const [remOn, setRemOn] = useState(remindersEnabled());
  const [remTime, setRemTime] = useState(getReminderTime());
  const [showNotifHelp, setShowNotifHelp] = useState(false);
  const toggleRem = async () => {
    if (remOn) { await disableReminders(); setRemOn(false); return; }
    // iOS won't re-prompt once denied → send the user to Settings instead.
    if (await notifPermission() === "denied") { setShowNotifHelp(true); return; }
    const ok = await enableReminders();   // requests permission when still "prompt"
    if (ok) setRemOn(true);
    else setShowNotifHelp(true);
  };
  const openIOSSettings = () => { try { window.open("app-settings:"); } catch { /* noop */ } };
  const onRemTime = async (v: string) => {
    setRemTime(v);
    await setReminderTime(v);   // reschedules at the new time (only while enabled)
  };
  const isAI = user?.plan === "ai";
  const isCore = user?.plan === "core";
  const canImport = !!user?.entitlements?.import;
  const isAdmin = !!user?.is_admin;
  const langLabel = LANGS.find((l) => l.code === lang)?.label ?? lang;

  useEffect(() => {
    api.listBatches().then((b) => setCount(b.length)).catch(() => setCount(null));
  }, []);

  useEffect(() => { setAvatar(getAvatar(user?.id)); }, [user?.id]);

  // Photo crop/center editor: pick → pan & zoom inside a square viewport → render
  // the visible region to a 256² JPEG → save. Lets the learner center their face.
  const cover = Math.max(CROP / natRef.current.w, CROP / natRef.current.h);
  const dispW = natRef.current.w * cover * zoom;
  const dispH = natRef.current.h * cover * zoom;
  const clampPos = (p: { x: number; y: number }, z = zoom) => {
    const cv = Math.max(CROP / natRef.current.w, CROP / natRef.current.h);
    const dw = natRef.current.w * cv * z, dh = natRef.current.h * cv * z;
    const mx = Math.max(0, (dw - CROP) / 2), my = Math.max(0, (dh - CROP) / 2);
    return { x: Math.max(-mx, Math.min(mx, p.x)), y: Math.max(-my, Math.min(my, p.y)) };
  };
  const openPicker = () => fileRef.current?.click();
  const resetPan = (p: { x: number; y: number }) => { curPosRef.current = p; setPos(p); };
  const onFile = (e: ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    e.target.value = "";   // allow re-picking the same file
    if (!file) return;
    const reader = new FileReader();
    reader.onload = () => {
      const img = new Image();
      img.onload = () => {
        // Downscale the source so the editor moves a small bitmap (a 4000px photo
        // repainted every frame is what made panning jerky). 1024px is plenty for
        // a 256² avatar.
        const MAX = 1024;
        const s = Math.min(1, MAX / Math.max(img.naturalWidth, img.naturalHeight));
        let src = reader.result as string;
        if (s < 1) {
          const w = Math.round(img.naturalWidth * s), h = Math.round(img.naturalHeight * s);
          const cv = document.createElement("canvas");
          cv.width = w; cv.height = h;
          const ctx = cv.getContext("2d");
          if (ctx) { ctx.drawImage(img, 0, 0, w, h); src = cv.toDataURL("image/jpeg", 0.92); natRef.current = { w, h }; }
          else natRef.current = { w: img.naturalWidth, h: img.naturalHeight };
        } else {
          natRef.current = { w: img.naturalWidth, h: img.naturalHeight };
        }
        setZoom(1); resetPan({ x: 0, y: 0 });
        setEditorSrc(src);
      };
      img.src = reader.result as string;
    };
    reader.readAsDataURL(file);
  };
  const onDragStart = (e: RPointerEvent<HTMLDivElement>) => {
    (e.currentTarget as HTMLElement).setPointerCapture?.(e.pointerId);
    dragRef.current = { x: e.clientX, y: e.clientY, px: curPosRef.current.x, py: curPosRef.current.y };
  };
  // Pan imperatively — write the transform straight to the node, no React state
  // per move → buttery on every frame. State syncs once on release.
  const onDragMove = (e: RPointerEvent<HTMLDivElement>) => {
    const d = dragRef.current; if (!d) return;
    const np = clampPos({ x: d.px + (e.clientX - d.x), y: d.py + (e.clientY - d.y) });
    curPosRef.current = np;
    if (imgRef.current)
      imgRef.current.style.transform = `translate(-50%, -50%) translate(${np.x}px, ${np.y}px)`;
  };
  const onDragEnd = () => { if (!dragRef.current) return; dragRef.current = null; setPos(curPosRef.current); };
  const onZoom = (e: ChangeEvent<HTMLInputElement>) => {
    const z = parseFloat(e.target.value);
    setZoom(z);
    resetPan(clampPos(curPosRef.current, z));
  };
  const commitAvatar = () => {
    if (!editorSrc || user?.id == null) return;
    const p = curPosRef.current;   // live value (state may lag a frame behind)
    const img = new Image();
    img.onload = () => {
      const S = 256, k = S / CROP;
      const cv = Math.max(CROP / img.naturalWidth, CROP / img.naturalHeight);
      const dw = img.naturalWidth * cv * zoom * k, dh = img.naturalHeight * cv * zoom * k;
      const cvs = document.createElement("canvas");
      cvs.width = S; cvs.height = S;
      const ctx = cvs.getContext("2d"); if (!ctx) return;
      ctx.drawImage(img, S / 2 + p.x * k - dw / 2, S / 2 + p.y * k - dh / 2, dw, dh);
      const data = cvs.toDataURL("image/jpeg", 0.85);
      saveAvatar(user.id, data); setAvatar(data); setEditorSrc(null);
    };
    img.src = editorSrc;
  };

  const upgrade = () => nav("/subscribe");

  const saveEmail = async () => {
    const e = newEmail.trim();
    if (!e) return;
    setEmailBusy(true); setEmailNote("");
    try {
      await api.changeEmail(e);
      // The new address is unverified → refresh flips us to the verify gate.
      await refresh();
    } catch {
      setEmailNote(t("verify.error"));
      setEmailBusy(false);
    }
  };

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
        <button type="button" className="avatar avatar-edit" style={{ margin: "0 auto 14px" }}
          onClick={openPicker} aria-label={t("profile.avatarAria")}>
          {avatar
            ? <img className="avatar-img" src={avatar} alt="" />
            : initials(user?.name || "", user?.email || "")}
          <span className="avatar-cam" aria-hidden="true">
            <svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M4 8h3l1.4-2h7.2L17 8h3a1 1 0 0 1 1 1v9a1 1 0 0 1-1 1H4a1 1 0 0 1-1-1V9a1 1 0 0 1 1-1z" /><circle cx="12" cy="13" r="3.2" /></svg>
          </span>
        </button>
        <input ref={fileRef} type="file" accept="image/*" onChange={onFile} hidden />
        <h1 style={{ marginBottom: 2 }}>{user?.name?.trim() || user?.email || "—"}</h1>
        <p className="muted small" style={{ margin: 0 }}>{t("profile.member")}</p>
        <p className="muted small" style={{ marginTop: 2 }}>
          {count == null ? "—" : t("profile.libCount", { n: count })}
        </p>
      </div>

      {editorSrc && (
        <div className="ava-modal" role="dialog" aria-modal="true">
          <div className="ava-sheet">
            <p className="ava-title">{t("profile.avatarTitle")}</p>
            <div className="ava-stage" style={{ width: CROP, height: CROP }}
              onPointerDown={onDragStart} onPointerMove={onDragMove}
              onPointerUp={onDragEnd} onPointerCancel={onDragEnd}>
              <img ref={imgRef} className="ava-img" src={editorSrc} alt="" draggable={false}
                style={{ width: dispW, height: dispH, transform: `translate(-50%, -50%) translate(${pos.x}px, ${pos.y}px)` }} />
              <div className="ava-ring" />
            </div>
            <input className="ava-zoom" type="range" min="1" max="3" step="0.01"
              value={zoom} onChange={onZoom} aria-label={t("profile.avatarZoom")} />
            <div className="ava-actions">
              <button className="btn-ghost" onClick={() => setEditorSrc(null)}>{t("common.cancel")}</button>
              <button className="btn" onClick={commitAvatar}>{t("common.save")}</button>
            </div>
            <button className="ava-repick" onClick={openPicker}>{t("profile.avatarOther")}</button>
          </div>
        </div>
      )}

      {showNotifHelp && (
        <div className="ava-modal" role="dialog" aria-modal="true">
          <div className="ava-sheet">
            <p className="ava-title">{t("profile.notifOffTitle")}</p>
            <p className="muted small" style={{ textAlign: "center", margin: 0, lineHeight: 1.5 }}>{t("profile.notifOffText")}</p>
            <div className="ava-actions">
              <button className="btn-ghost" onClick={() => setShowNotifHelp(false)}>{t("common.cancel")}</button>
              <button className="btn" onClick={() => { openIOSSettings(); setShowNotifHelp(false); }}>{t("profile.openSettings")}</button>
            </div>
          </div>
        </div>
      )}

      {/* Current plan — the cabinet's most important block. Three real states:
          free shows "Бесплатный" + a path into the tiers (was mislabeled "Core"). */}
      <div className="plan-card">
        <span className="plan-eyebrow">{t("plan.eyebrow")}</span>
        <div className="plan-name">{isAI ? "Executive AI" : isCore ? "Executive Core" : t("plan.free")}</div>
        <div className="plan-sub">{isAI ? t("plan.subAI") : isCore ? t("plan.subCore") : t("plan.subFree")}</div>
        <button className="plan-action" onClick={upgrade}>
          {isAI ? t("plan.actionAI") : isCore ? t("plan.actionCore") : t("plan.actionFree")}
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
        {/* Account email — visible + changeable (changing it requires re-verifying) */}
        {!editEmail ? (
          <div className="menu-row menu-row-static">
            <span className="menu-ico" aria-hidden>✉️</span>
            <div className="menu-body">
              <div className="menu-title">{t("profile.emailTitle")}</div>
              <div className="menu-sub">{user?.email}</div>
            </div>
            <button className="row-action" onClick={() => { setNewEmail(""); setEmailNote(""); setEditEmail(true); }}>
              {t("profile.emailChange")}
            </button>
          </div>
        ) : (
          <div className="menu-row menu-row-static email-edit">
            <input
              className="verify-input" type="email" inputMode="email" autoCapitalize="none"
              placeholder={user?.email} value={newEmail}
              onChange={(e) => setNewEmail(e.target.value)}
            />
            <div className="email-edit-row">
              <button className="sub-buy primary" disabled={emailBusy} onClick={saveEmail}>
                {emailBusy ? "…" : t("profile.emailSave")}
              </button>
              <button className="sub-buy" disabled={emailBusy} onClick={() => setEditEmail(false)}>
                {t("profile.emailCancel")}
              </button>
            </div>
            {emailNote && <p className="verify-note">{emailNote}</p>}
          </div>
        )}
        {/* Interface language */}
        <div className="menu-row menu-row-static">
          <span className="menu-ico" aria-hidden>🌐</span>
          <div className="menu-body">
            <div className="menu-title">{t("lang.label")}</div>
            <div className="menu-sub">{langLabel}</div>
          </div>
          <LangSwitcher variant="pill" />
        </div>
        {/* Cover-art protagonist gender (D3) — changeable anytime; covers follow */}
        <div className="menu-row menu-row-static" data-tour="gender">
          <span className="menu-ico" aria-hidden>🎭</span>
          <div className="menu-body">
            <div className="menu-title">{t("gender.label")}</div>
            <div className="menu-sub">{t(`gender.${(user?.hero_gender as string) || "male"}`)}</div>
          </div>
          <HeroGenderSwitcher />
        </div>
        {/* League placement — the home card retires after the first run/skip, so
            this row is the permanent way back in (see the result, retake later). */}
        <button className="menu-row" onClick={() => nav("/league")}>
          <span className="menu-ico" aria-hidden>🏆</span>
          <div className="menu-body">
            <div className="menu-title">{t("profile.league")}</div>
            <div className="menu-sub">
              {leagueRes ? t(`league.name.${leagueRes.tier}`) : t("profile.leagueTake")}
            </div>
          </div>
          <span className="menu-chevron"><IconChevron /></span>
        </button>
        {canImport && row(IconImport, t("profile.importTitle"), t("profile.importSub"), "/import")}
        {/* Call Analyzer — AI-plan feature; visible to everyone as the teaser. */}
        {row(IconWave, t("analyzer.title"), t("analyzer.menuSub"), "/analyze")}
        {isAdmin && row(IconGear, t("profile.listeningTitle"), t("profile.listeningSub"), "/settings")}
        {/* Daily practice reminder — native only (local notification). */}
        {native && (
          <>
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
            {remOn && (
              <div className="menu-row menu-row-static">
                <span className="menu-ico" aria-hidden>⏰</span>
                <div className="menu-body"><div className="menu-title">{t("profile.reminderTime")}</div></div>
                <input className="time-input" type="time" value={remTime} onChange={(e) => onRemTime(e.target.value)} />
              </div>
            )}
            {/* Lock-screen widget — iOS can't add it programmatically; this row
                shows whether it's on the screen (WidgetKit) and opens the how-to. */}
            <button className="menu-row" onClick={() => setWidgetHowto(true)}>
              <span className="menu-ico" aria-hidden>
                <svg viewBox="0 0 24 24" width="19" height="19" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                  <rect x="3" y="3" width="8" height="8" rx="2" /><rect x="13" y="3" width="8" height="8" rx="2" /><rect x="3" y="13" width="8" height="8" rx="2" /><path d="M17 14v6M14 17h6" />
                </svg>
              </span>
              <div className="menu-body">
                <div className="menu-title">{t("widget.rowTitle")}</div>
                <div className="menu-sub">{t(widgetOn ? "widget.on" : "widget.off")}</div>
              </div>
              <span className="menu-chevron"><IconChevron /></span>
            </button>
            {widgetHowto && <WidgetHowto onClose={() => setWidgetHowto(false)} />}
          </>
        )}
        <button className="menu-row" onClick={exportMyData} disabled={exporting}>
          <span className="menu-ico" aria-hidden>⬇️</span>
          <div className="menu-body">
            <div className="menu-title">{t("profile.exportTitle")}</div>
            <div className="menu-sub">{exporting ? "…" : t("profile.exportSub")}</div>
          </div>
          <span className="menu-chevron"><IconChevron /></span>
        </button>
        {row(IconInfo, t("profile.aboutTitle"), t("profile.aboutSub"), "/about")}
        <button className="menu-row" onClick={() => { if (user?.id != null) { resetTours(user.id); resetTips(user.id); } nav("/"); }}>
          <span className="menu-ico" aria-hidden>🎬</span>
          <div className="menu-body">
            <div className="menu-title">{t("tour.replay")}</div>
          </div>
          <span className="menu-chevron"><IconChevron /></span>
        </button>
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
