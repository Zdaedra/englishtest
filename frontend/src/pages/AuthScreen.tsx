import { FormEvent, useState } from "react";
import { useAuth } from "../auth/AuthContext";

function humanize(s: string): string {
  try {
    const o = JSON.parse(s.replace(/^Error:\s*/, ""));
    if (o && typeof o.detail === "string") return o.detail;
  } catch { /* not JSON */ }
  if (s.includes("401")) return "Неверный email или пароль.";
  return "Что-то пошло не так. Попробуй ещё раз.";
}

export default function AuthScreen() {
  const { login, register } = useAuth();
  const [mode, setMode] = useState<"login" | "register">("login");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [name, setName] = useState("");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    setErr("");
    setBusy(true);
    try {
      if (mode === "login") await login(email.trim(), password);
      else await register(email.trim(), password, name.trim());
    } catch (e2) {
      setErr(humanize(String(e2)));
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="auth-screen">
      <div className="auth-card">
        <div className="auth-brand">Executive English</div>
        <p className="auth-tag">
          {mode === "login" ? "С возвращением." : "Создай аккаунт, чтобы начать."}
        </p>
        <form onSubmit={submit}>
          {mode === "register" && (
            <input className="auth-input" type="text" placeholder="Имя" autoComplete="name"
              value={name} onChange={(e) => setName(e.target.value)} />
          )}
          <input className="auth-input" type="email" placeholder="Email" autoComplete="email"
            autoCapitalize="none" value={email} onChange={(e) => setEmail(e.target.value)} required />
          <input className="auth-input" type="password" placeholder="Пароль"
            autoComplete={mode === "login" ? "current-password" : "new-password"}
            value={password} onChange={(e) => setPassword(e.target.value)} required />
          {err && <p className="auth-err">{err}</p>}
          <button className="l3-cta" type="submit" disabled={busy} style={{ marginTop: 6 }}>
            {busy ? "…" : mode === "login" ? "Войти" : "Создать аккаунт"}
          </button>
        </form>
        <button className="auth-toggle" type="button"
          onClick={() => { setMode(mode === "login" ? "register" : "login"); setErr(""); }}>
          {mode === "login" ? "Нет аккаунта? Зарегистрироваться" : "Уже есть аккаунт? Войти"}
        </button>
      </div>
    </div>
  );
}
