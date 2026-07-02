// Daily practice reminder (iOS local notification). A real habit cue: when on,
// it fires every day at the chosen time (default 09:00) — not gated on a due-set,
// so it works for everyone, including new learners. When the last home open saw
// phrases due for review, the body is personalized with that count (the push is
// pre-scheduled, so the number is as-of the last sync — close enough for a cue).
// Native-only; no-ops on web (delivery needs notification permission + a native build).
import { Capacitor } from "@capacitor/core";
import { LocalNotifications } from "@capacitor/local-notifications";
import { tg } from "../i18n";

const ENABLED_KEY = "ee-review-reminder";
const TIME_KEY = "ee-reminder-time"; // "HH:MM" local time
const DUE_KEY = "ee-reminder-due"; // due-count seen at the last sync
const NOTIF_ID = 7001;
const DEFAULT_TIME = "09:00";

function isNative(): boolean {
  try { return Capacitor.isNativePlatform(); } catch { return false; }
}

export function remindersEnabled(): boolean {
  try { return localStorage.getItem(ENABLED_KEY) === "1"; } catch { return false; }
}

export type NotifPerm = "granted" | "denied" | "prompt" | "unknown";

/** Current OS notification permission. "denied" means iOS won't re-prompt — the
 *  user must enable it in Settings, so the UI offers a deep link there. */
export async function notifPermission(): Promise<NotifPerm> {
  if (!isNative()) return "unknown";
  try {
    const d = (await LocalNotifications.checkPermissions()).display;
    if (d === "granted") return "granted";
    if (d === "denied") return "denied";
    return "prompt"; // "prompt" | "prompt-with-rationale"
  } catch { return "unknown"; }
}

export function getReminderTime(): string {
  try { return localStorage.getItem(TIME_KEY) || DEFAULT_TIME; } catch { return DEFAULT_TIME; }
}

function parseTime(t: string): { hour: number; minute: number } {
  const [h, m] = t.split(":").map((x) => parseInt(x, 10));
  return { hour: Number.isFinite(h) ? h : 9, minute: Number.isFinite(m) ? m : 0 };
}

/** Schedule the single daily repeating reminder at the saved time. Idempotent —
 *  cancels any existing one first. No-op unless native AND opted in. */
async function scheduleDaily(): Promise<void> {
  if (!isNative() || !remindersEnabled()) return;
  const { hour, minute } = parseTime(getReminderTime());
  let due = 0;
  try { due = parseInt(localStorage.getItem(DUE_KEY) || "0", 10) || 0; } catch { /* private mode */ }
  try {
    await LocalNotifications.cancel({ notifications: [{ id: NOTIF_ID }] });
    await LocalNotifications.schedule({
      notifications: [{
        id: NOTIF_ID,
        title: "Executive English",
        body: due > 0 ? tg("review.notif", { n: due }) : tg("review.notifDaily"),
        schedule: { on: { hour, minute }, repeats: true, allowWhileIdle: true },
      }],
    });
  } catch { /* permission revoked between calls, etc. */ }
}

/** Turn reminders on: ask permission, persist the opt-in, schedule the daily.
 *  Returns false if permission is denied or unavailable (caller reflects state). */
export async function enableReminders(): Promise<boolean> {
  if (!isNative()) return false;
  try {
    const perm = await LocalNotifications.requestPermissions();
    if (perm.display !== "granted") return false;
    localStorage.setItem(ENABLED_KEY, "1");
    await scheduleDaily();
    return true;
  } catch { return false; }
}

export async function disableReminders(): Promise<void> {
  try { localStorage.removeItem(ENABLED_KEY); } catch { /* private mode */ }
  if (!isNative()) return;
  try { await LocalNotifications.cancel({ notifications: [{ id: NOTIF_ID }] }); } catch { /* none scheduled */ }
}

/** Change the daily time and reschedule (only takes effect while enabled). */
export async function setReminderTime(t: string): Promise<void> {
  try { localStorage.setItem(TIME_KEY, t); } catch { /* private mode */ }
  await scheduleDaily();
}

/** Keep the daily reminder alive across app opens (idempotent). Library calls
 *  this on each home open — and again with the live due-count once mastery
 *  loads, so tomorrow's push says "N phrases about to slip" instead of generic. */
export async function syncReviewReminder(dueCount?: number): Promise<void> {
  if (typeof dueCount === "number") {
    try { localStorage.setItem(DUE_KEY, String(Math.max(0, dueCount))); } catch { /* private mode */ }
  }
  await scheduleDaily();
}
