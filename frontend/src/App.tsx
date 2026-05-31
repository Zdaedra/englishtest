import { Outlet, useLocation, useNavigate } from "react-router-dom";
import { PlayerProvider, usePlayer } from "./player/PlayerContext";
import { BatchCover } from "./ui/Art";
import {
  IconLibrary, IconSections, IconWave, IconPlay, IconPause,
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

function BottomNav() {
  const nav = useNavigate();
  const { pathname } = useLocation();
  const item = (
    to: string,
    label: string,
    active: boolean,
    Icon: (p: { size?: number }) => JSX.Element
  ) => (
    <button
      className={active ? "nav-item active" : "nav-item"}
      onClick={() => nav(to)}
      type="button"
    >
      <Icon />
      <span>{label}</span>
    </button>
  );
  const learnActive = pathname.startsWith("/learn");
  const libActive =
    !learnActive &&
    (pathname === "/" ||
      pathname.startsWith("/batch") ||
      pathname.startsWith("/profile") ||
      pathname.startsWith("/settings") ||
      pathname.startsWith("/import"));
  const playActive = pathname === "/play";

  return (
    <nav className="bottom-nav">
      {item("/", "Библиотека", libActive, IconLibrary)}
      {item("/learn", "Обучение", learnActive, IconSections)}
      {item("/play", "Playback", playActive, IconWave)}
    </nav>
  );
}

export default function App() {
  return (
    <PlayerProvider>
      <div className="shell">
        <Outlet />
        <MiniPlayer />
        <BottomNav />
      </div>
    </PlayerProvider>
  );
}
