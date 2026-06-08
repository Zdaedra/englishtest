// First-run onboarding flag, namespaced per user so a shared browser doesn't
// skip onboarding for a second account. (localStorage for MVP; could move to the
// server User row later for cross-device.)
const key = (userId: number) => `ee-onboarded-${userId}`;

export function isOnboarded(userId: number): boolean {
  try { return localStorage.getItem(key(userId)) === "1"; } catch { return false; }
}

export function setOnboarded(userId: number): void {
  try { localStorage.setItem(key(userId), "1"); } catch { /* ignore */ }
}
