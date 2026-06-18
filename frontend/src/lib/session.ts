// Session token for native (Capacitor/iOS). The web app authenticates with the
// httponly `eng_auth` cookie and never persists a token here — keeping the
// session credential out of JS-readable storage on the web. Native has no
// reliable cross-origin cookie in WKWebView, so it stores the signed session
// token in the Keychain (via @capacitor/preferences) and sends it as a Bearer
// header on every API request.
import { Capacitor } from "@capacitor/core";
import { Preferences } from "@capacitor/preferences";

const KEY = "ee-token";
let _token: string | null = null;
let _loaded = false;

export function isNative(): boolean {
  try { return Capacitor.isNativePlatform(); } catch { return false; }
}

/** Load the persisted token once at startup (native only). No-op on web. */
export async function loadToken(): Promise<void> {
  if (_loaded) return;
  _loaded = true;
  if (!isNative()) return;
  try { const { value } = await Preferences.get({ key: KEY }); _token = value || null; }
  catch { /* private/unavailable */ }
}

export function getToken(): string | null { return _token; }

export async function setToken(token: string | null): Promise<void> {
  _token = token;
  if (!isNative()) return; // web relies on the cookie; never persist the token
  try {
    if (token) await Preferences.set({ key: KEY, value: token });
    else await Preferences.remove({ key: KEY });
  } catch { /* ignore */ }
}

/** Authorization header for native requests; empty on web (cookie is used). */
export function authHeaders(): Record<string, string> {
  return _token ? { Authorization: `Bearer ${_token}` } : {};
}

/** Light haptic tap on native (no-op on web). Fire-and-forget. */
export function haptic(style: "light" | "medium" = "light"): void {
  if (!isNative()) return;
  import("@capacitor/haptics")
    .then(({ Haptics, ImpactStyle }) =>
      Haptics.impact({ style: style === "medium" ? ImpactStyle.Medium : ImpactStyle.Light }))
    .catch(() => { /* haptics unavailable */ });
}
