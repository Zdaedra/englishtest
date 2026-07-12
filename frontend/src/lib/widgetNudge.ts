// "Add the widget" nudge: iOS can't install a widget for the user — only suggest.
// Until the widget is actually on their screen (WidgetKit tells us), the home
// screen shows a quiet suggestion card: at most once a day, at most NUDGE_MAX
// times total, dismissible forever with one tap, and silenced automatically the
// moment the widget is detected. Native-only; web never nudges.
import { isNative } from "./session";
import { widgetInstalled } from "./widget";

const NUDGE_MAX = 5;

type NudgeState = { shows?: number; day?: string; dismissed?: boolean; done?: boolean };

const key = (uid: number) => `ee-widget-nudge:${uid}`;
const today = () => new Date().toISOString().slice(0, 10);

function read(uid: number): NudgeState {
  try { return JSON.parse(localStorage.getItem(key(uid)) || "{}"); } catch { return {}; }
}

function write(uid: number, st: NudgeState): void {
  try { localStorage.setItem(key(uid), JSON.stringify(st)); } catch { /* private mode */ }
}

/** Should the home screen show the widget suggestion right now? */
export async function shouldNudgeWidget(uid: number | null | undefined): Promise<boolean> {
  if (!isNative() || uid == null) return false;
  const st = read(uid);
  if (st.dismissed || st.done) return false;
  if ((st.shows ?? 0) >= NUDGE_MAX) return false;
  if (st.day === today()) return false;            // at most once a day
  if (await widgetInstalled()) {
    write(uid, { ...st, done: true });             // it's on the screen — retire forever
    return false;
  }
  return true;
}

/** Count a show (call once per render decision, not per re-render). */
export function markWidgetNudgeShown(uid: number): void {
  const st = read(uid);
  write(uid, { ...st, shows: (st.shows ?? 0) + 1, day: today() });
}

/** The user tapped ✕ — never suggest again. */
export function dismissWidgetNudge(uid: number): void {
  write(uid, { ...read(uid), dismissed: true });
}
