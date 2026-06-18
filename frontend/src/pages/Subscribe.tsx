import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "../auth/AuthContext";
import { useI18n } from "../i18n";
import { IconBack, IconCheck } from "../ui/icons";

// Prices are placeholders matching the App Store Connect products we'll create
// (see TZ-ios-app.md §13). Once StoreKit is wired, these come live + localized
// from the store; until then we show them statically and the buy button explains
// that payment connects in an upcoming build.
type Tier = {
  plan: "ai" | "core";
  nameKey: string; taglineKey: string;
  monthly: string; yearly: string; savePct: string;
  features: string[]; flagship?: boolean;
};
const TIERS: Tier[] = [
  {
    plan: "ai", nameKey: "sub.ai.name", taglineKey: "sub.ai.tagline",
    monthly: "$24.99", yearly: "$149.99", savePct: "50%", flagship: true,
    features: ["sub.ai.f1", "sub.ai.f2", "sub.ai.f3", "sub.ai.f4"],
  },
  {
    plan: "core", nameKey: "sub.core.name", taglineKey: "sub.core.tagline",
    monthly: "$12.99", yearly: "$79.99", savePct: "49%",
    features: ["sub.core.f1", "sub.core.f2", "sub.core.f3"],
  },
];

export default function Subscribe() {
  const nav = useNavigate();
  const { t } = useI18n();
  const { user } = useAuth();
  const [note, setNote] = useState("");

  // Stub until StoreKit is wired (needs the Apple Developer account + products).
  const buy = (_plan: string, _period: "monthly" | "yearly") => setNote(t("sub.soon"));
  const restore = () => setNote(t("sub.soon"));

  return (
    <div className="screen sub-screen">
      <button className="bh-back" onClick={() => nav(-1)}>
        <IconBack size={18} /> {t("common.back")}
      </button>

      <div className="sub-head">
        <h1 className="sub-title">{t("sub.title")}</h1>
        <p className="sub-sub">{t("sub.subtitle")}</p>
      </div>

      {TIERS.map((tr) => {
        const current = user?.plan === tr.plan;
        return (
          <div key={tr.plan} className={`sub-card${tr.flagship ? " flagship" : ""}`}>
            {tr.flagship && <span className="sub-badge">{t("sub.flagship")}</span>}
            <div className="sub-card-name">{t(tr.nameKey)}</div>
            <div className="sub-card-tag">{t(tr.taglineKey)}</div>
            <div className="sub-price">
              <span className="sub-price-mo"><b>{tr.monthly}</b>{t("sub.perMonth")}</span>
              <span className="sub-price-yr">{t("sub.orYear", { price: tr.yearly })} · <span className="sub-save">−{tr.savePct}</span></span>
            </div>
            <ul className="sub-feats">
              {tr.features.map((f) => (
                <li key={f}><span className="sub-tick"><IconCheck size={14} /></span>{t(f)}</li>
              ))}
            </ul>
            {current ? (
              <div className="sub-current">{t("sub.current")}</div>
            ) : (
              <button className={`sub-buy${tr.flagship ? " primary" : ""}`} onClick={() => buy(tr.plan, "yearly")}>
                {t("sub.choose")}
              </button>
            )}
          </div>
        );
      })}

      <p className="sub-free-note">{t("sub.freeNote")}</p>
      {note && <p className="sub-note">{note}</p>}
      <button className="sub-restore" onClick={restore}>{t("sub.restore")}</button>
    </div>
  );
}
