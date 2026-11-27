import { useNavigate } from "react-router-dom";
import { useI18n } from "../i18n";

/** A screen whose data failed to load: one translated sentence, "Try again"
 *  and a way back — instead of the raw server text with no exit. */
export default function LoadError({ msgKey }: { msgKey: string }) {
  const nav = useNavigate();
  const { t } = useI18n();
  return (
    <div className="screen empty">
      <p>{t(msgKey)}</p>
      <button className="btn btn-primary" onClick={() => window.location.reload()}>{t("common.retry")}</button>
      <button className="btn btn-tint" onClick={() => nav("/")}>{t("pb.goLibrary")}</button>
    </div>
  );
}
