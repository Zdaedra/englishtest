// Shared mic affordance + score helpers used by all three lessons.
import { tg } from "../i18n";

// Map a 0..10 score to one of three bands for colour + copy.
export function band(score: number): "lo" | "mid" | "hi" {
  if (score >= 7) return "hi";
  if (score >= 4) return "mid";
  return "lo";
}

function MicGlyph() {
  return (
    <svg width="34" height="34" viewBox="0 0 24 24" fill="none">
      <rect x="9" y="3" width="6" height="11" rx="3" fill="currentColor" />
      <path d="M6 11a6 6 0 0 0 12 0M12 17v4M9 21h6"
        stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" />
    </svg>
  );
}

// Big circular mic button; flips to a stop/red state while recording, shows a
// spinner glyph while the clip is uploading + scored.
export function RecFab({
  recording, busy, onClick,
}: { recording: boolean; busy: boolean; onClick: () => void }) {
  return (
    <button
      className={`rec-fab${recording ? " on" : ""}`}
      disabled={busy}
      onClick={onClick}
      aria-label={recording ? tg("rec.stopAria") : tg("rec.recordAria")}
    >
      {busy ? (
        <span className="rec-dots">…</span>
      ) : recording ? (
        <span className="rec-stop" />
      ) : (
        <MicGlyph />
      )}
    </button>
  );
}
