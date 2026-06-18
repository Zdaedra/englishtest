import { useMemo, useState } from "react";
import { mediaUrl } from "../api";
import { IconLock } from "./icons";

// Unified generative art: one cohesive visual language for the whole library,
// deterministically seeded per batch (by slug) so each batch has a stable,
// distinct-yet-related abstract — warm editorial composition, no AI, no network.
// Plays a supporting role behind a title-forward layout.

function hashSeed(s: string): number {
  let h = 2166136261 >>> 0;
  for (let i = 0; i < s.length; i++) {
    h ^= s.charCodeAt(i);
    h = Math.imul(h, 16777619);
  }
  return h >>> 0;
}

function mulberry32(a: number): () => number {
  return () => {
    a |= 0;
    a = (a + 0x6d2b79f5) | 0;
    let t = Math.imul(a ^ (a >>> 15), 1 | a);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

// Tight warm palette (sand → bronze → espresso). No blue, no neon.
const TONES = ["#D9C4A3", "#C9A06A", "#A97B47", "#7A5733", "#46372A"];

export function BatchArt({ seed, className = "" }: { seed: string; className?: string }) {
  const art = useMemo(() => {
    const rnd = mulberry32(hashSeed(seed || "seed"));
    const pick = () => TONES[Math.floor(rnd() * TONES.length)];
    const blobs = Array.from({ length: 3 }, () => ({
      cx: 10 + rnd() * 80,
      cy: 8 + rnd() * 82,
      r: 28 + rnd() * 36,
      fill: pick(),
    }));
    const ring = { cx: 16 + rnd() * 68, cy: 12 + rnd() * 66, r: 18 + rnd() * 24 };
    const uid = (hashSeed(seed || "seed") % 1000000).toString(36);
    return { blobs, ring, uid };
  }, [seed]);

  const { uid } = art;
  return (
    <svg
      className={`bart ${className}`}
      viewBox="0 0 100 100"
      preserveAspectRatio="xMidYMid slice"
      aria-hidden="true"
    >
      <defs>
        <linearGradient id={`bg-${uid}`} x1="0" y1="0" x2="0.35" y2="1">
          <stop offset="0" stopColor="#F2ECDF" />
          <stop offset="1" stopColor="#E2D5BF" />
        </linearGradient>
        <radialGradient id={`sheen-${uid}`} cx="0.78" cy="0.06" r="0.95">
          <stop offset="0" stopColor="#FFFFFF" stopOpacity="0.22" />
          <stop offset="0.55" stopColor="#FFFFFF" stopOpacity="0" />
        </radialGradient>
        <filter id={`grain-${uid}`}>
          <feTurbulence type="fractalNoise" baseFrequency="0.85" numOctaves="2" stitchTiles="stitch" />
          <feColorMatrix type="saturate" values="0" />
        </filter>
      </defs>

      <rect width="100" height="100" fill={`url(#bg-${uid})`} />
      <g style={{ mixBlendMode: "multiply" }}>
        {art.blobs.map((b, i) => (
          <circle key={i} cx={b.cx} cy={b.cy} r={b.r} fill={b.fill} opacity={0.5} />
        ))}
      </g>
      <circle
        cx={art.ring.cx}
        cy={art.ring.cy}
        r={art.ring.r}
        fill="none"
        stroke="#5A4631"
        strokeOpacity={0.32}
        strokeWidth={0.7}
      />
      <rect width="100" height="100" filter={`url(#grain-${uid})`} opacity={0.05} />
      <rect width="100" height="100" fill={`url(#sheen-${uid})`} />
    </svg>
  );
}

// A batch's AI-generated scene photo when one exists, else the procedural art.
// Falling back on load error keeps a missing/broken cover from ever breaking the UI.
export function BatchCover({
  seed,
  coverUrl,
  className = "",
  locked = false,
}: {
  seed: string;
  coverUrl?: string | null;
  className?: string;
  locked?: boolean;
}) {
  const [failed, setFailed] = useState(false);
  const hasImg = coverUrl && !failed;
  // When locked, wrap the cover so we can dim it + overlay a lock chip. The
  // wrapper keeps the same sizing class so existing layouts are unchanged.
  const inner = hasImg ? (
    <img
      className={locked ? "bcover" : `bcover ${className}`}
      src={mediaUrl(coverUrl) ?? undefined}
      alt=""
      loading="lazy"
      onError={() => setFailed(true)}
    />
  ) : (
    <BatchArt seed={seed} className={locked ? "bcover" : className} />
  );
  if (!locked) return inner;
  return (
    <span className={`bcover bcover-lockwrap ${className}`}>
      {inner}
      <span className="bcover-lock" aria-hidden><IconLock size={18} /></span>
    </span>
  );
}
