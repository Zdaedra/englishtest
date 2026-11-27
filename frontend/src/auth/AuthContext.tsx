import { createContext, useCallback, useContext, useEffect, useState } from "react";
import { api, Me, setOnUnauthorized } from "../api";
import { clearLocalProgress, hydrateProgress } from "../lib/progress";
import { adoptLearnProfile, releaseLearnProfile, type UserProfile } from "../lib/profile";
import { clearWidget } from "../lib/widget";
import { pauseReminders } from "../lib/reminders";
import { syncPurchases } from "../lib/iap";
import { loadToken, setToken, haptic } from "../lib/session";
import { useI18n, type Lang } from "../i18n";

const SUPPORTED = ["en", "ru", "es", "de", "fr"];

type AuthCtx = {
  user: Me | null;
  loading: boolean;
  /** /me could not be reached at launch (offline, 5xx) — not the same as signed out. */
  offline: boolean;
  retry: () => void;
  login: (email: string, password: string) => Promise<void>;
  register: (email: string, password: string, name?: string) => Promise<void>;
  logout: () => Promise<void>;
  refresh: () => Promise<void>;
};

const Ctx = createContext<AuthCtx>(null!);
export const useAuth = () => useContext(Ctx);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const { setLang } = useI18n();
  const [user, setUser] = useState<Me | null>(null);
  const [loading, setLoading] = useState(true);
  const [offline, setOffline] = useState(false);

  // On any authentication, replace the local progress cache with this user's
  // server-side progress (so a shared browser never shows another account's).
  const onAuthed = useCallback(async (u: Me) => {
    setUser(u);
    // Native: persist the session token (Keychain) so it survives restarts. No-op on web.
    if (u.token) await setToken(u.token);
    // Adopt the account's saved UI language (cross-device sync). sync:false so we
    // don't immediately POST the value we just received back to the server.
    if (u.ui_lang && SUPPORTED.includes(u.ui_lang)) setLang(u.ui_lang as Lang, { sync: false });
    // Bind the learning profile (goals/strategy/plan/league) to THIS account:
    // server copy wins; a not-yet-synced local/legacy profile is pushed up once.
    adoptLearnProfile(u.id, (u.learn_profile as UserProfile | undefined) ?? null);
    clearLocalProgress();
    await hydrateProgress();
    // Catch up on any App Store purchase the server never heard about: a renewal,
    // an Ask-to-Buy approval, a purchase whose round-trip died mid-flight. Silent,
    // native-only, and deliberately NOT awaited — a slow or failing store must
    // never hold up sign-in. See lib/iap.syncPurchases.
    void syncPurchases((plan) => setUser((cur) => (cur ? { ...cur, plan } : cur)));
  }, [setLang]);

  useEffect(() => {
    // A single 401 may be transient (e.g. a request that raced the native token
    // load, or one flaky endpoint). Re-verify with /me before tearing down the
    // session — `api.me()` doesn't route through this handler — so a stray 401
    // never bounces a still-valid user to the login screen. Only a definitive
    // "not authed" (me → null) logs out; a network error keeps the session.
    setOnUnauthorized(async () => {
      try { if (await api.me()) return; } catch { return; }
      void setToken(null);
      setUser(null);
    });
    // Load any stored native token first so /me carries the Bearer header.
    loadToken()
      .then(() => api.me())
      .then((u) => { setOffline(false); if (u) onAuthed(u); })
      .catch(() => setOffline(true))
      .finally(() => setLoading(false));
  }, [onAuthed]);

  // Launch failed to reach the server: try again on its own when the network
  // comes back or the app returns to the foreground, plus the button on screen.
  const retry = useCallback(() => {
    loadToken()
      .then(() => api.me())
      .then((u) => { setOffline(false); if (u) onAuthed(u); })
      .catch(() => setOffline(true));
  }, [onAuthed]);
  useEffect(() => {
    if (!offline) return;
    const onVisible = () => { if (document.visibilityState === "visible") retry(); };
    window.addEventListener("online", retry);
    document.addEventListener("visibilitychange", onVisible);
    return () => {
      window.removeEventListener("online", retry);
      document.removeEventListener("visibilitychange", onVisible);
    };
  }, [offline, retry]);

  const login = useCallback(async (email: string, password: string) => {
    await onAuthed(await api.login(email, password));
    haptic("success");
  }, [onAuthed]);

  const register = useCallback(async (email: string, password: string, name?: string) => {
    await onAuthed(await api.register(email, password, name));
    haptic("success");
  }, [onAuthed]);

  const logout = useCallback(async () => {
    // Offline the server call throws; signing out of THIS device must still work
    // (the token is stateless — dropping it locally is the sign-out).
    try { await api.logout(); } catch { /* offline — local sign-out below still runs */ }
    await setToken(null);
    clearLocalProgress();
    // Account-boundary hygiene: unbind the learning profile, wipe the previous
    // account's phrases off the lock-screen widget, and silence the daily
    // reminder until the next login re-schedules it. (Account deletion funnels
    // through here too.)
    releaseLearnProfile();
    void clearWidget();
    void pauseReminders();
    setUser(null);
  }, []);

  // Re-fetch the current user (e.g. after an IAP purchase updates the plan).
  const refresh = useCallback(async () => {
    try { const u = await api.me(); if (u) setUser(u); } catch { /* keep current */ }
  }, []);

  return (
    <Ctx.Provider value={{ user, loading, offline, retry, login, register, logout, refresh }}>
      {children}
    </Ctx.Provider>
  );
}
