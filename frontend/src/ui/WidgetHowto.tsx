import { useI18n } from "../i18n";

// How to add the lock/home-screen widget — iOS offers no API or deep link to do
// it for the user, so this sheet is the whole mechanism: two short step lists.
// Opened from the home nudge card and from the Profile row.
export default function WidgetHowto({ onClose }: { onClose: () => void }) {
  const { t } = useI18n();
  return (
    <div className="ava-modal" role="dialog" aria-modal="true" onClick={onClose}>
      <div className="ava-sheet" onClick={(e) => e.stopPropagation()}>
        <p className="ava-title">{t("widget.howtoTitle")}</p>
        <div className="wh-block">
          <p className="wh-head">{t("widget.lockTitle")}</p>
          <p className="wh-steps">{t("widget.lockSteps")}</p>
        </div>
        <div className="wh-block">
          <p className="wh-head">{t("widget.homeTitle")}</p>
          <p className="wh-steps">{t("widget.homeSteps")}</p>
        </div>
        <div className="ava-actions">
          <button className="btn" onClick={onClose}>{t("widget.gotIt")}</button>
        </div>
      </div>
    </div>
  );
}
