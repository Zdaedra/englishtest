import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { App as CapApp } from "@capacitor/app";
import { isNative } from "../lib/session";
import { IconBack, IconChevron } from "../ui/icons";
import { useI18n } from "../i18n";

// Web fallback only; on the device the real version comes from the bundle, so a
// hardcoded "1.0.0" can no longer contradict the build App Review installs.
const WEB_VERSION = "1.1";
// The App Store page 404s until the first release goes live — flip after launch.
const SHOW_RATE = false;
const PRIVACY_URL = "https://executive-english.net/privacy";
const TERMS_URL = "https://executive-english.net/terms";
const APPSTORE_URL = "https://apps.apple.com/app/id6782193688";
const SUPPORT_EMAIL = "support@executive-english.net";

export default function About() {
  const nav = useNavigate();
  const { t } = useI18n();
  const [version, setVersion] = useState(WEB_VERSION);
  useEffect(() => {
    if (!isNative()) return;
    CapApp.getInfo().then((i) => setVersion(`${i.version} (${i.build})`)).catch(() => {});
  }, []);

  const link = (
    icon: string,
    title: string,
    href: string,
  ) => (
    <a className="menu-row" href={href} target="_blank" rel="noreferrer">
      <span className="menu-ico" aria-hidden>{icon}</span>
      <div className="menu-body"><div className="menu-title">{title}</div></div>
      <span className="menu-chevron"><IconChevron /></span>
    </a>
  );

  return (
    <div className="screen">
      <button className="back-link" onClick={() => nav("/profile")}>
        <IconBack size={18} /> {t("common.back")}
      </button>

      <div className="about-head">
        <div className="about-logo" aria-hidden>EE</div>
        <h1 className="about-name">Executive English</h1>
        <p className="muted small" style={{ margin: "2px 0 0" }}>{t("about.tagline")}</p>
        <p className="muted small" style={{ margin: "2px 0 0" }}>{t("about.version", { v: version })}</p>
      </div>

      <p className="about-desc">{t("about.desc")}</p>

      <div className="menu" style={{ marginTop: 8 }}>
        {link("🔒", t("about.privacy"), PRIVACY_URL)}
        {link("📄", t("about.terms"), TERMS_URL)}
        {link("✉️", t("about.support"), `mailto:${SUPPORT_EMAIL}`)}
        {SHOW_RATE && link("★", t("about.rate"), APPSTORE_URL)}
      </div>

      <p className="about-foot">© 2026 Executive English</p>
    </div>
  );
}
