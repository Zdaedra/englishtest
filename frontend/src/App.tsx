import { CSSProperties, useEffect, useRef, useState } from "react";
import { Outlet, useLocation, useNavigate } from "react-router-dom";
import { PlayerProvider, usePlayer } from "./player/PlayerContext";
import { BatchCover } from "./ui/Art";
import {
  IconLibrary, IconWave, IconProfile, IconSearch, IconPlay, IconPause,
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
    <button className="miniplayer" onClick={() => nav("/play")}>
      <span className="mini-cover">
        <BatchCover seed={p.batch?.slug ?? "seed"} coverUrl={p.batch?.cover_url} />
      </span>
      <div className="mini-meta">
        <div className="mini-title">{anchor || p.batch?.title || "…"}</div>
        <div className="mini-sub">{p.batch?.title}</div>
      </div>
      <span
        className="mini-play"
        onClick={(e) => {
          e.stopPropagation();
          p.toggle();
        }}
      >
        {p.playing ? <IconPause size={20} /> : <IconPlay size={20} />}
      </span>
    </button>
  );
}

// Apple-Music-style floating navigation: a glass capsule of three tabs plus a
// separate floating search button. The active highlight is a single liquid-glass
// pill that springs between tabs (its column index drives a translateX) with a
// gel stretch on travel; tabs and the search button swell + magnify their icon
// on press (the iOS-feasible part of Liquid Glass — true backdrop refraction via
// SVG feDisplacementMap is Chromium-only and broken in iOS Safari, WebKit #245510).
const TABS = [
  { to: "/", label: "Библиотека", Icon: IconLibrary },
  { to: "/learn", label: "Практика", Icon: IconWave },
  { to: "/profile", label: "Профиль", Icon: IconProfile },
];

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
  const { pathname } = useLocation();

  const practiceActive = pathname.startsWith("/learn");
  const profileActive = pathname.startsWith("/profile");
  const libActive =
    !practiceActive &&
    !profileActive &&
    (pathname === "/" ||
      pathname.startsWith("/batch") ||
      pathname.startsWith("/settings") ||
      pathname.startsWith("/import") ||
      pathname.startsWith("/play"));
  const activeIndex = libActive ? 0 : practiceActive ? 1 : profileActive ? 2 : -1;

  // Replay a one-shot "gel" stretch on the pill whenever the active tab changes.
  // Alternate two identical keyframes so the animation restarts each move.
  const prevIdx = useRef(activeIndex);
  const [moveTick, setMoveTick] = useState(0);
  useEffect(() => {
    if (prevIdx.current !== activeIndex && activeIndex >= 0) setMoveTick((t) => t + 1);
    prevIdx.current = activeIndex;
  }, [activeIndex]);
  const gel = moveTick === 0 ? "" : moveTick % 2 ? " gel-a" : " gel-b";

  // ---- Drag-to-select: the lens follows the finger along the bar -----------
  const capsuleRef = useRef<HTMLElement>(null);
  const down = useRef(false);
  const dragged = useRef(false);
  const downX = useRef(0);
  const [dragging, setDragging] = useState(false);
  const [dragPos, setDragPos] = useState(0); // fractional 0..2 while dragging

  // Map a clientX to a fractional tab position (0..2): column centres sit at
  // 1/6, 3/6, 5/6 of the capsule, so pos = clamp(f*3 − 0.5, 0, 2).
  const posFromX = (clientX: number) => {
    const el = capsuleRef.current;
    if (!el) return 0;
    const r = el.getBoundingClientRect();
    const f = (clientX - r.left) / r.width;
    return Math.min(2, Math.max(0, f * 3 - 0.5));
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

  return (
    <div className="nav-dock">
      <nav
        ref={capsuleRef}
        className={`nav-capsule${dragging ? " dragging" : ""}`}
        data-noactive={!dragging && activeIndex < 0}
        style={{ "--active": pillPos } as CSSProperties}
        onPointerDown={onDown}
        onPointerMove={onMove}
        onPointerUp={endDrag}
        onPointerCancel={endDrag}
      >
        <span className={`nav-pill${gel}`} aria-hidden="true" />
        {TABS.map((t, i) => {
          const Icon = t.Icon;
          const active = shownActive === i;
          return (
            <button
              key={t.to}
              className={`nav-tab${active ? " active" : ""}`}
              type="button"
              onClick={(e) => {
                if (dragged.current) { dragged.current = false; return; } // drag already navigated
                lensPop(e.currentTarget, 1.5, 1.18); // tapped tab will rest magnified
                nav(t.to);
              }}
            >
              <Icon />
              <span>{t.label}</span>
            </button>
          );
        })}
      </nav>
      <button
        className="nav-search"
        type="button"
        aria-label="Поиск"
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

export default function App() {
  return (
    <PlayerProvider>
      <div className="shell">
        <Outlet />
        <MiniPlayer />
        <FloatingNav />
      </div>
    </PlayerProvider>
  );
}
