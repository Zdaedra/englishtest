import { createContext, useCallback, useContext, useEffect, useState } from "react";
import { api, Me, setOnUnauthorized } from "../api";
import { clearLocalProgress, hydrateProgress } from "../lib/progress";

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
  const [user, setUser] = useState<Me | null>(null);
  const [loading, setLoading] = useState(true);

  // On any authentication, replace the local progress cache with this user's
  // server-side progress (so a shared browser never shows another account's).
  const onAuthed = useCallback(async (u: Me) => {
    setUser(u);
    clearLocalProgress();
    await hydrateProgress();
  }, []);

  useEffect(() => {
    setOnUnauthorized(() => setUser(null));
    api.me()
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
    clearLocalProgress();
    setUser(null);
  }, []);

  return (
    <Ctx.Provider value={{ user, loading, login, register, logout }}>
      {children}
    </Ctx.Provider>
  );
}
