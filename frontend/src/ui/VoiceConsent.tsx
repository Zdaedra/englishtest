import { useCallback, useState, type ReactNode } from "react";
import { api } from "../api";
import { useAuth } from "../auth/AuthContext";
import { useI18n } from "../i18n";

// One-time consent before the FIRST voice recording (Apple §5.1.2(i) + GDPR):
// the clip leaves the device for speech-to-text and the transcript is scored by
// a language model, so the learner has to agree first.
//
// This lives here, shared, because it used to be copy-pasted into Practice and
// Battle only — while lessons 1-3 record too. A new learner's very first path is
// topic → lesson 1 → retell aloud, so the one screen that MUST ask was the one
// screen that never did. Any screen that can start a recording calls this.
//
// The local flag gates the UI; the server keeps an append-only audit record.
export function useVoiceConsent(): { requireConsent: () => boolean; consentModal: ReactNode } {
  const { user } = useAuth();
  const { t } = useI18n();
  const [open, setOpen] = useState(false);
  const key = user?.id != null ? `ee-voice-consent-${user.id}` : null;

  const granted = useCallback(() => {
    try { return !!key && localStorage.getItem(key) === "1"; } catch { return false; }
  }, [key]);

  /** true = may record now. false = the sheet just opened; the learner agrees,
   *  then taps the mic again — same two-step the Practice screen already used. */
  const requireConsent = useCallback(() => {
    if (granted()) return true;
    setOpen(true);
    return false;
  }, [granted]);

  const accept = () => {
    try { if (key) localStorage.setItem(key, "1"); } catch { /* private mode */ }
    api.recordConsent("voice_ai").catch(() => {});   // server audit, best-effort
    setOpen(false);
  };

  const consentModal = open ? (
    <div className="ava-modal" role="dialog" aria-modal="true">
      <div className="ava-sheet">
        <p className="ava-title">{t("voice.consentTitle")}</p>
        <p className="muted small" style={{ textAlign: "center", margin: 0, lineHeight: 1.5 }}>
          {t("voice.consentText")}
        </p>
        <div className="ava-actions">
          <button className="btn-ghost" onClick={() => setOpen(false)}>{t("common.cancel")}</button>
          <button className="btn" onClick={accept}>{t("voice.consentAccept")}</button>
        </div>
      </div>
    </div>
  ) : null;

  return { requireConsent, consentModal };
}
