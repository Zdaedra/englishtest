import { useCallback, useRef, useState } from "react";
import { api, PlanSeg } from "../api";

export type MnemoLayout = "full" | "anchors" | "shuffle";

// The anchor "lit" at a given time: the last anchor segment that has started. It
// stays lit through the following narrative / recall gap until the next anchor.
export function anchorAt(plan: PlanSeg[], time: number): string | null {
  let id: string | null = null;
  for (const s of plan) {
    if (s.start > time) break;
    if (s.role === "anchor" && s.anchor_id) id = s.anchor_id;
  }
  return id;
}

// The ordered list of anchor segments (start/end + anchor_id) in a rendered plan.
// Used by Lesson 3 to know where to pause for a prompt.
export function anchorSegments(plan: PlanSeg[]): { anchor_id: string; start: number; end: number }[] {
  return plan
    .filter((s) => s.role === "anchor" && s.anchor_id)
    .map((s) => ({ anchor_id: s.anchor_id as string, start: s.start, end: s.end }));
}

// Reusable mnemonic-story audio player shared by all three lessons. Owns one
// <audio> element (the caller spreads `bind` onto it), caches rendered layouts,
// karaoke-tracks the active anchor, and accepts an optional per-tick callback so
// Lesson 3 can implement random stop-points on top of the same playback.
export function useMnemoAudio(
  batchId: number | undefined,
  onTick?: (time: number, audio: HTMLAudioElement) => void,
  onEnded?: () => void
) {
  const audioRef = useRef<HTMLAudioElement>(null);
  const planRef = useRef<PlanSeg[]>([]);
  const cache = useRef<Partial<Record<MnemoLayout, { url: string; plan: PlanSeg[] }>>>({});

  const [layout, setLayout] = useState<MnemoLayout | null>(null);
  const [loading, setLoading] = useState<MnemoLayout | null>(null);
  const [playing, setPlaying] = useState(false);
  const [activeAnchor, setActiveAnchor] = useState<string | null>(null);
  const [err, setErr] = useState("");

  const prefetch = useCallback(
    (l: MnemoLayout) => {
      if (!batchId || cache.current[l]) return;
      api
        .mnemoAudio(batchId, l)
        .then((r) => {
          cache.current[l] = { url: r.audio_url, plan: r.plan };
          fetch(r.audio_url).catch(() => {}); // warm the HTTP cache
        })
        .catch(() => {});
    },
    [batchId]
  );

  const play = useCallback(
    async (l: MnemoLayout) => {
      const a = audioRef.current;
      if (!a || !batchId) return;
      // Same layout already loaded → just toggle.
      if (layout === l && a.src) {
        a.paused ? void a.play() : a.pause();
        return;
      }
      const warm = cache.current[l];
      if (warm) {
        planRef.current = warm.plan;
        a.src = warm.url;
        a.currentTime = 0;
        setLayout(l);
        await a.play();
        return;
      }
      setLoading(l);
      try {
        const r = await api.mnemoAudio(batchId, l);
        cache.current[l] = { url: r.audio_url, plan: r.plan };
        planRef.current = r.plan;
        a.src = r.audio_url;
        a.currentTime = 0;
        setLayout(l);
        await a.play();
      } catch (e) {
        setErr(String(e));
      } finally {
        setLoading(null);
      }
    },
    [batchId, layout]
  );

  const pause = useCallback(() => audioRef.current?.pause(), []);
  const resume = useCallback(() => void audioRef.current?.play(), []);
  const seek = useCallback((time: number) => {
    const a = audioRef.current;
    if (a) a.currentTime = Math.max(0, time);
  }, []);

  // Spread onto the page's <audio> element.
  const bind = {
    ref: audioRef,
    playsInline: true,
    preload: "auto" as const,
    onPlay: () => setPlaying(true),
    onPause: () => setPlaying(false),
    onEnded: () => {
      setPlaying(false);
      setActiveAnchor(null);
      onEnded?.();
    },
    onTimeUpdate: (e: React.SyntheticEvent<HTMLAudioElement>) => {
      const a = e.currentTarget;
      setActiveAnchor(anchorAt(planRef.current, a.currentTime));
      onTick?.(a.currentTime, a);
    },
  };

  return {
    audioRef,
    planRef,
    layout,
    loading,
    playing,
    activeAnchor,
    err,
    play,
    pause,
    resume,
    seek,
    prefetch,
    bind,
  };
}
