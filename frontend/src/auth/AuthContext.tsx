import { createContext, useCallback, useContext, useEffect, useState } from "react";
import { api, Me, setOnUnauthorized } from "../api";
import { clearLocalProgress, hydrateProgress } from "../lib/progress";
import { loadToken, setToken } from "../lib/session";
import { useI18n, type Lang } from "../i18n";

const SUPPORTED = ["ru", "es", "de", "fr"];

type AuthCtx = {
  user: Me | null;
  loading: boolean;
  login: (email: string, password: string) => Promise<void>;
  register: (email: string, password: string, name?: string) => Promise<void>;
  logout: () => Promise<void>;
};

const Ctx = createContext<AuthCtx>(null!);
export const useAuth = () => useContext(Ctx);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const { setLang } = useI18n();
  const [user, setUser] = useState<Me | null>(null);
  const [loading, setLoading] = useState(true);

  // On any authentication, replace the local progress cache with this user's
  // server-side progress (so a shared browser never shows another account's).
  const onAuthed = useCallback(async (u: Me) => {
    setUser(u);
    // Native: persist the session token (Keychain) so it survives restarts. No-op on web.
    if (u.token) await setToken(u.token);
    // Adopt the account's saved UI language (cross-device sync). sync:false so we
    // don't immediately POST the value we just received back to the server.
    if (u.ui_lang && SUPPORTED.includes(u.ui_lang)) setLang(u.ui_lang as Lang, { sync: false });
    clearLocalProgress();
    await hydrateProgress();
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
      .then((u) => { if (u) onAuthed(u); })
      .catch(() => {})
      .finally(() => setLoading(false));
  }, [onAuthed]);

  const login = useCallback(async (email: string, password: string) => {
    await onAuthed(await api.login(email, password));
  }, [onAuthed]);

  const register = useCallback(async (email: string, password: string, name?: string) => {
    await onAuthed(await api.register(email, password, name));
  }, [onAuthed]);

  const logout = useCallback(async () => {
    await api.logout();
    await setToken(null);
    clearLocalProgress();
    setUser(null);
  }, []);

  return (
    <Ctx.Provider value={{ user, loading, login, register, logout }}>
      {children}
    </Ctx.Provider>
  );
}
