import { useNavigate } from "react-router-dom";
import { IconBack, IconChevron } from "../ui/icons";
import { useI18n } from "../i18n";

// Marketing version shown in the cabinet. Bump on releases.
const VERSION = "1.0.0";
const PRIVACY_URL = "https://executive-english.net/privacy";
const TERMS_URL = "https://executive-english.net/terms";
const APPSTORE_URL = "https://apps.apple.com/app/id6782193688";
const SUPPORT_EMAIL = "support@executive-english.net";

export default function About() {
  const nav = useNavigate();
  const { t } = useI18n();

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
      <button className="back-link" onClick={() => nav(-1)}>
        <IconBack size={18} /> {t("common.back")}
      </button>

      <div className="about-head">
        <div className="about-logo" aria-hidden>EE</div>
        <h1 className="about-name">Executive English</h1>
        <p className="muted small" style={{ margin: "2px 0 0" }}>{t("about.tagline")}</p>
        <p className="muted small" style={{ margin: "2px 0 0" }}>{t("about.version", { v: VERSION })}</p>
      </div>

      <p className="about-desc">{t("about.desc")}</p>

      <div className="menu" style={{ marginTop: 8 }}>
        {link("🔒", t("about.privacy"), PRIVACY_URL)}
        {link("📄", t("about.terms"), TERMS_URL)}
        {link("✉️", t("about.support"), `mailto:${SUPPORT_EMAIL}`)}
        {link("★", t("about.rate"), APPSTORE_URL)}
      </div>

      <p className="about-foot">© 2026 Executive English</p>
    </div>
  );
}
