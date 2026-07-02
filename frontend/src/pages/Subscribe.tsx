import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "../auth/AuthContext";
import { useI18n } from "../i18n";
import { haptic } from "../lib/session";
import { buyPlan, restorePurchases, iapAvailable } from "../lib/iap";
import { IconBack, IconCheck } from "../ui/icons";

// Static prices mirror the App Store Connect products (Core $6.99/$39.99,
// AI $12.99/$79.99). On native, the buy button runs the real StoreKit purchase
// → server verify; on web (no StoreKit) it shows the "coming in the app" note.
type Tier = {
  plan: "ai" | "core";
  nameKey: string; taglineKey: string;
  // monthlyEq = the yearly price ÷ 12, shown as the per-month equivalent when the
  // yearly period is selected.
  monthly: string; yearly: string; monthlyEq: string; savePct: string;
  features: string[]; flagship?: boolean;
};
const TIERS: Tier[] = [
  {
    plan: "ai", nameKey: "sub.ai.name", taglineKey: "sub.ai.tagline",
    monthly: "$12.99", yearly: "$79.99", monthlyEq: "$6.67", savePct: "49%", flagship: true,
    features: ["sub.ai.f1", "sub.ai.f2", "sub.ai.f3", "sub.ai.f4"],
  },
  {
    plan: "core", nameKey: "sub.core.name", taglineKey: "sub.core.tagline",
    monthly: "$6.99", yearly: "$39.99", monthlyEq: "$3.33", savePct: "52%",
    features: ["sub.core.f1", "sub.core.f2", "sub.core.f3"],
  },
];

// Biggest annual discount across tiers — labels the "yearly" toggle.
const MAX_SAVE = Math.max(...TIERS.map((t) => parseInt(t.savePct, 10)));

export default function Subscribe() {
  const nav = useNavigate();
  const { t } = useI18n();
  const { user, refresh } = useAuth();
  const [note, setNote] = useState("");
  const [busy, setBusy] = useState(false);
  // Billing period chooser — annual is the default (best value).
  const [period, setPeriod] = useState<"monthly" | "yearly">("yearly");

  const buy = async (plan: "ai" | "core", period: "monthly" | "yearly") => {
    haptic("medium");
    if (!iapAvailable()) { setNote(t("sub.soon")); return; }  // web: no StoreKit
    setBusy(true); setNote("");
    try {
      const newPlan = await buyPlan(plan, period);
      if (newPlan) { await refresh(); haptic("success"); setNote(t("sub.thanks")); }
    } catch { haptic("error"); setNote(t("sub.failed")); }
    finally { setBusy(false); }
  };

  const restore = async () => {
    haptic("light");
    if (!iapAvailable()) { setNote(t("sub.soon")); return; }
    setBusy(true); setNote("");
    try {
      const plan = await restorePurchases();
      await refresh();
      setNote(plan ? t("sub.restored") : t("sub.noRestore"));
    } catch { setNote(t("sub.failed")); }
    finally { setBusy(false); }
  };

  return (
    <div className="screen sub-screen">
      <button className="bh-back" onClick={() => nav(-1)}>
        <IconBack size={18} /> {t("common.back")}
      </button>

      <div className="sub-head">
        <h1 className="sub-title">{t("sub.title")}</h1>
        <p className="sub-sub">{t("sub.subtitle")}</p>
      </div>

      <div className="period-seg" role="tablist" aria-label={t("sub.title")}>
        <button
          role="tab" aria-selected={period === "monthly"}
          className={`period-tab${period === "monthly" ? " active" : ""}`}
          onClick={() => setPeriod("monthly")}
        >
          {t("sub.monthly")}
        </button>
        <button
          role="tab" aria-selected={period === "yearly"}
          className={`period-tab${period === "yearly" ? " active" : ""}`}
          onClick={() => setPeriod("yearly")}
        >
          {t("sub.yearly")}<span className="period-pill">−{MAX_SAVE}%</span>
        </button>
      </div>

      {TIERS.map((tr) => {
        const current = user?.plan === tr.plan;
        return (
          <div key={tr.plan} className={`sub-card${tr.flagship ? " flagship" : ""}`}>
            {tr.flagship && <span className="sub-badge">{t("sub.flagship")}</span>}
            <div className="sub-card-name">{t(tr.nameKey)}</div>
            <div className="sub-card-tag">{t(tr.taglineKey)}</div>
            <div className="sub-price">
              {period === "yearly" ? (
                <>
                  <span className="sub-price-mo"><b>{tr.yearly}</b>{t("sub.perYear")}</span>
                  <span className="sub-price-yr">{t("sub.perMoEq", { price: tr.monthlyEq })} · <span className="sub-save">−{tr.savePct}</span></span>
                </>
              ) : (
                <span className="sub-price-mo"><b>{tr.monthly}</b>{t("sub.perMonth")}</span>
              )}
            </div>
            <ul className="sub-feats">
              {tr.features.map((f) => (
                <li key={f}><span className="sub-tick"><IconCheck size={14} /></span>{t(f)}</li>
              ))}
            </ul>
            {current ? (
              <div className="sub-current">{t("sub.current")}</div>
            ) : (
              <button className={`sub-buy${tr.flagship ? " primary" : ""}`} disabled={busy} onClick={() => buy(tr.plan, period)}>
                {busy ? "…" : t("sub.choose")}
              </button>
            )}
          </div>
        );
      })}

      {user?.plan !== "ai" && user?.plan !== "core" && (
        <p className="sub-free-note">{t("sub.freeNote")}</p>
      )}
      {note && <p className="sub-note">{note}</p>}
      <button className="sub-restore" disabled={busy} onClick={restore}>{t("sub.restore")}</button>

      {/* App Store §3.1.2 — auto-renew disclosure + required legal links. */}
      <p className="sub-legal-note">{t("sub.autorenew")}</p>
      <div className="sub-legal-links">
        <a href="https://executive-english.net/terms" target="_blank" rel="noreferrer">{t("about.terms")}</a>
        <span aria-hidden> · </span>
        <a href="https://executive-english.net/privacy" target="_blank" rel="noreferrer">{t("about.privacy")}</a>
      </div>
    </div>
  );
}
