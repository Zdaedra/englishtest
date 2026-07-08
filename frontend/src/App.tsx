import { CSSProperties, useEffect, useRef, useState } from "react";
import { Outlet, useLocation, useNavigate } from "react-router-dom";
import { PlayerProvider, usePlayer } from "./player/PlayerContext";
import { useAuth } from "./auth/AuthContext";
import AuthScreen from "./pages/AuthScreen";
import VerifyEmail from "./pages/VerifyEmail";
import OnboardingFlow from "./pages/OnboardingFlow";
import { isOnboarded, setOnboarded } from "./lib/onboarding";
import { isNative } from "./lib/session";
import { NavBar, NAV_SF } from "./lib/navbar";
import { useI18n } from "./i18n";
import { BatchCover } from "./ui/Art";
import { BatchMenuProvider } from "./ui/BatchMenu";
import RouteTour from "./tutorial/RouteTour";
import { TeachProvider } from "./tutorial/teach";
import {
  IconLibrary, IconWave, IconFocus, IconBolt, IconSearch, IconPlay, IconPause,
} from "./ui/icons";

function MiniPlayer() {
  const p = usePlayer();
  const nav = useNavigate();
  const loc = useLocation();
  if (loc.pathname === "/play") return null;
  if (!p.session && !p.busy) return null;

  const anchor =
    p.currentOrder != null ? p.phraseByOrder.get(p.currentOrder)?.anchor : null;

  return (
    <div className="miniplayer">
      <span className="mini-cover">
        <BatchCover seed={p.batch?.slug ?? "seed"} coverUrl={p.batch?.cover_url} />
      </span>
      <div className="mini-meta">
        <div className="mini-title">{anchor || p.batch?.title || "…"}</div>
        <div className="mini-sub">{p.batch?.title}</div>
      </div>
      <button className="mini-open" aria-label={p.batch?.title || "Player"}
        onClick={() => nav("/play")} />
      <button
        className="mini-play"
        aria-label={p.playing ? "Pause" : "Play"}
        onClick={() => p.toggle()}
      >
        {p.playing ? <IconPause size={20} /> : <IconPlay size={20} />}
      </button>
    </div>
  );
}

// Apple-Music-style floating navigation: a glass capsule of three tabs plus a
// separate floating search button. The active highlight is a single liquid-glass
// pill that springs between tabs (its column index drives a translateX) with a
// gel stretch on travel; tabs and the search button swell + magnify their icon
// on press (the iOS-feasible part of Liquid Glass — true backdrop refraction via
// SVG feDisplacementMap is Chromium-only and broken in iOS Safari, WebKit #245510).
const TABS = [
  { to: "/", labelKey: "nav.library", Icon: IconLibrary },
  { to: "/learn", labelKey: "nav.learn", Icon: IconWave },
  { to: "/practice", labelKey: "nav.practice", Icon: IconFocus },
  { to: "/battle", labelKey: "nav.battle", Icon: IconBolt },
];
const NTAB = TABS.length;

// One-shot "lens pop": scale the button's icon up past its rest size and settle
// back, on every tap. Driven by the Web Animations API on the click event, so it
// is fully visible regardless of how brief the tap is (the old hold-to-swell was
// invisible on a quick tap). Safari-supported. `rest` = where the icon settles
// (active tab rests magnified; the search icon rests at 1).
function lensPop(btn: HTMLElement | null, peak: number, rest: number) {
  const svg = btn?.querySelector("svg");
  if (!svg || typeof svg.animate !== "function") return;
  svg.animate(
    [
      { transform: "scale(1)" },
      { transform: `scale(${peak})`, offset: 0.38 },
      { transform: `scale(${rest})` },
    ],
    { duration: 440, easing: "cubic-bezier(.34,1.56,.64,1)" }
  );
}

function FloatingNav() {
  const nav = useNavigate();
  const { t, lang } = useI18n();
  const { pathname } = useLocation();
  const native = isNative();

  const learnActive = pathname.startsWith("/learn");
  const practiceActive = pathname.startsWith("/practice");
  const battleActive = pathname.startsWith("/battle");
  const profileActive = pathname.startsWith("/profile");
  const libActive =
    !learnActive &&
    !practiceActive &&
    !battleActive &&
    !profileActive &&
    (pathname === "/" ||
      pathname.startsWith("/batch") ||
      pathname.startsWith("/settings") ||
      pathname.startsWith("/import") ||
      pathname.startsWith("/play"));
  // Profile lives in the top-right account button, not the bar — on /profile no tab lights.
  const activeIndex =
    libActive ? 0 : learnActive ? 1 : practiceActive ? 2 : battleActive ? 3 : -1;

  // Replay a one-shot "gel" stretch on the pill whenever the active tab changes.
  // Alternate two identical keyframes so the animation restarts each move.
  const prevIdx = useRef(activeIndex);
  const [moveTick, setMoveTick] = useState(0);
  useEffect(() => {
    if (prevIdx.current !== activeIndex && activeIndex >= 0) setMoveTick((t) => t + 1);
    prevIdx.current = activeIndex;
  }, [activeIndex]);
  const gel = moveTick === 0 ? "" : moveTick % 2 ? " gel-a" : " gel-b";

  // ---- Native iOS: hand the bar to the Liquid-Glass plugin -----------------
  // react-router stays the navigation owner; the native bar only renders + emits
  // tab/search events. Re-presented on language change to refresh labels.
  useEffect(() => {
    if (!native) return;
    let subs: Array<{ remove: () => void }> = [];
    const labels = TABS.map((tab) => t(tab.labelKey));
    NavBar.present({ labels, sf: NAV_SF, active: Math.max(0, activeIndex) }).catch(() => {});
    NavBar.addListener("tabSelected", ({ index }) => nav(TABS[index]?.to ?? "/"))
      .then((h) => subs.push(h)).catch(() => {});
    NavBar.addListener("searchTapped", () => nav("/", { state: { focusSearch: Date.now() } }))
      .then((h) => subs.push(h)).catch(() => {});
    return () => { subs.forEach((s) => s.remove()); };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [native, lang]);

  useEffect(() => {
    if (native) NavBar.setActive({ index: Math.max(0, activeIndex) }).catch(() => {});
  }, [native, activeIndex]);

  // ---- Drag-to-select: the lens follows the finger along the bar -----------
  const capsuleRef = useRef<HTMLElement>(null);
  const down = useRef(false);
  const dragged = useRef(false);
  const downX = useRef(0);
  const [dragging, setDragging] = useState(false);
  const [dragPos, setDragPos] = useState(0); // fractional 0..2 while dragging

  // Map a clientX to a fractional tab position (0..NTAB-1): column centres sit at
  // (2i+1)/(2·NTAB) of the capsule, so pos = clamp(f·NTAB − 0.5, 0, NTAB-1).
  const posFromX = (clientX: number) => {
    const el = capsuleRef.current;
    if (!el) return 0;
    const r = el.getBoundingClientRect();
    const f = (clientX - r.left) / r.width;
    return Math.min(NTAB - 1, Math.max(0, f * NTAB - 0.5));
  };

  const onDown = (e: React.PointerEvent) => {
    down.current = true;
    dragged.current = false;
    downX.current = e.clientX;
    try { capsuleRef.current?.setPointerCapture?.(e.pointerId); } catch { /* non-fatal */ }
  };
  const onMove = (e: React.PointerEvent) => {
    if (!down.current) return;
    if (Math.abs(e.clientX - downX.current) > 6) {
      dragged.current = true;
      if (!dragging) setDragging(true);
    }
    if (dragged.current) setDragPos(posFromX(e.clientX));
  };
  const endDrag = (e: React.PointerEvent) => {
    if (!down.current) return;
    down.current = false;
    if (dragged.current) {
      const target = Math.round(posFromX(e.clientX));
      const tab = TABS[target];
      const icon = capsuleRef.current?.querySelectorAll<HTMLElement>(".nav-tab")[target] || null;
      lensPop(icon, 1.5, 1.18);
      nav(tab.to); // batches with setDragging(false) → no flicker
    }
    setDragging(false);
  };

  // While dragging, the highlight (green icon + label) snaps to the nearest tab;
  // the pill itself follows continuously.
  const shownActive = dragging ? Math.round(dragPos) : activeIndex;
  const pillPos = dragging ? dragPos : Math.max(activeIndex, 0);

  // On native the Liquid-Glass bar is a native subview (added by the plugin) —
  // don't render the web dock at all.
  if (native) return null;

  return (
    <div className="nav-dock">
      <nav
        ref={capsuleRef}
        data-tour="nav"
        className={`nav-capsule${dragging ? " dragging" : ""}`}
        data-noactive={!dragging && activeIndex < 0}
        style={{ "--active": pillPos, "--ntab": NTAB } as CSSProperties}
        onPointerDown={onDown}
        onPointerMove={onMove}
        onPointerUp={endDrag}
        onPointerCancel={endDrag}
      >
        <span className={`nav-pill${gel}`} aria-hidden="true" />
        {TABS.map((tab, i) => {
          const Icon = tab.Icon;
          const active = shownActive === i;
          return (
            <button
              key={tab.to}
              className={`nav-tab${active ? " active" : ""}`}
              type="button"
              onClick={(e) => {
                if (dragged.current) { dragged.current = false; return; } // drag already navigated
                lensPop(e.currentTarget, 1.5, 1.18); // tapped tab will rest magnified
                nav(tab.to);
              }}
            >
              <Icon />
              <span>{t(tab.labelKey)}</span>
            </button>
          );
        })}
      </nav>
      <button
        className="nav-search"
        type="button"
        aria-label={t("nav.search")}
        onClick={(e) => {
          lensPop(e.currentTarget, 1.55, 1); // magnifier lenses up well past the button
          e.currentTarget.animate(
            [
              { transform: "scale(1)" },
              { transform: "scale(1.2)", offset: 0.38 }, // button swells bigger than the bar
              { transform: "scale(1)" },
            ],
            { duration: 460, easing: "cubic-bezier(.34,1.56,.64,1)" }
          );
          nav("/", { state: { focusSearch: Date.now() } });
        }}
      >
        <IconSearch />
      </button>
    </div>
  );
}

function Shell() {
  const { user, loading } = useAuth();
  const [obDone, setObDone] = useState(false);
  if (loading) {
    return <div className="auth-screen"><div className="auth-splash">Executive English</div></div>;
  }
  if (!user) {
    return <AuthScreen />;
  }
  // Mandatory email verification: gate everything until the account is confirmed
  // (server also enforces this — see the auth gate in backend/app/main.py).
  if (user.email_verified === false) {
    return <VerifyEmail />;
  }
  if (!obDone && !isOnboarded(user.id)) {
    return <OnboardingFlow onDone={() => { setOnboarded(user.id); setObDone(true); }} />;
  }
  return (
    <PlayerProvider>
      <BatchMenuProvider>
        <TeachProvider>
          <div className="shell">
            <Outlet />
            <MiniPlayer />
            <FloatingNav />
            <RouteTour uid={user.id} />
          </div>
        </TeachProvider>
      </BatchMenuProvider>
    </PlayerProvider>
  );
}

export default function App() {
  return <Shell />;
}
