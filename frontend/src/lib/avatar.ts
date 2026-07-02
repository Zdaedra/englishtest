// Profile photo — kept on the device, keyed by user id (so it persists for this
// account and never shows for another on a shared device). Stored as a small
// (256px) JPEG data URL. Server sync is a documented follow-up.
const key = (uid: number) => `ee-avatar-${uid}`;

export function getAvatar(uid?: number | null): string | null {
  if (uid == null) return null;
  try { return localStorage.getItem(key(uid)); } catch { return null; }
}

export function saveAvatar(uid: number, dataUrl: string): void {
  try { localStorage.setItem(key(uid), dataUrl); } catch { /* quota — non-critical */ }
  // Let any mounted surface (Library header) refresh without a route change.
  try { window.dispatchEvent(new Event("ee-avatar-changed")); } catch { /* noop */ }
}
