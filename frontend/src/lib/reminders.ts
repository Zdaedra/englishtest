// Daily review reminder (iOS local notification) — SUBSTANCE-GATED: we only
// schedule a nudge when phrases are actually due, and re-schedule on each app
// open. Premium adults churn on empty nags, so an empty due-set = no notification.
// Native-only; no-ops on web. Delivery needs notification permission + a native
// build (won't fire in the browser).
import { Capacitor } from "@capacitor/core";
import { LocalNotifications } from "@capacitor/local-notifications";
import { api } from "../api";
import { tg } from "../i18n";

const ENABLED_KEY = "ee-review-reminder";
const NOTIF_ID = 7001;
const HOUR = 9; // 9:00 local — a calm morning rehearsal slot (fixed in v1)

function isNative(): boolean {
  try { return Capacitor.isNativePlatform(); } catch { return false; }
}

export function remindersEnabled(): boolean {
  try { return localStorage.getItem(ENABLED_KEY) === "1"; } catch { return false; }
}

function nextAt(hour: number): Date {
  const d = new Date();
  d.setHours(hour, 0, 0, 0);
  if (d.getTime() <= Date.now()) d.setDate(d.getDate() + 1);
  return d;
}

/** Turn reminders on: ask permission, persist the opt-in, schedule if due. */
export async function enableReminders(): Promise<boolean> {
  if (!isNative()) return false;
  try {
    const perm = await LocalNotifications.requestPermissions();
    if (perm.display !== "granted") return false;
    localStorage.setItem(ENABLED_KEY, "1");
    await syncReviewReminder();
    return true;
  } catch { return false; }
}

export async function disableReminders(): Promise<void> {
  try { localStorage.removeItem(ENABLED_KEY); } catch { /* private mode */ }
  if (!isNative()) return;
  try { await LocalNotifications.cancel({ notifications: [{ id: NOTIF_ID }] }); } catch { /* none scheduled */ }
}

/** Reschedule the single daily reminder from the live due-set. Cancels when
 *  nothing is due. Safe to call on every app open — it's idempotent. */
export async function syncReviewReminder(): Promise<void> {
  if (!isNative() || !remindersEnabled()) return;
  let due = 0;
  try {
    const ms = await api.getMastery();
    due = ms.reduce((s, m) => s + (m.due || 0), 0);
  } catch { return; }
  try {
    await LocalNotifications.cancel({ notifications: [{ id: NOTIF_ID }] });
    if (due <= 0) return; // substance gate: no due items → no nag
    await LocalNotifications.schedule({
      notifications: [{
        id: NOTIF_ID,
        title: "Executive English",
        body: tg("review.notif", { n: due }),
        schedule: { at: nextAt(HOUR), repeats: false },
      }],
    });
  } catch { /* permission revoked between calls, etc. */ }
}
