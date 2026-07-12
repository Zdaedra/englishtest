import {
  createContext, useCallback, useContext, useEffect, useMemo, useRef, useState, ReactNode,
} from "react";
import { api, BatchDetail, PlanSeg, Phrase, SessionResp } from "../api";
import { cacheAudio, isCached, setupMediaSession } from "../audio/helpers";
import { useAuth } from "../auth/AuthContext";

export type Mode = "listening" | "recall";
export type Order = "ordered" | "zone_random" | "full_random";

type PlayBatchOpts = { mode?: Mode; order?: Order; startOrder?: number; autoplay?: boolean };

type PlayerCtx = {
  batch: BatchDetail | null;
  session: SessionResp | null;
  mode: Mode;
  order: Order;
  t: number;
  duration: number;
  playing: boolean;
  busy: boolean;
  err: string;
  rate: number;
  loop: boolean;
  cached: boolean;
  playSequence: number[];
  currentOrder: number | null;
  currentIndex: number;
  phraseByOrder: Map<number, Phrase>;
  favorites: Set<number>;
  // actions
  playBatch: (b: BatchDetail, opts?: PlayBatchOpts) => void;
  changeMode: (m: Mode) => void;
  reshuffle: () => void;
  toggle: () => void;
  next: () => void;
  prev: () => void;
  goToIndex: (i: number) => void;
  goToOrder: (order: number) => void;
  playPhrase: (phraseId: number) => void;
  prefetchPhrases: (ids: number[]) => void;
  seekFraction: (f: number) => void;
  cycleRate: () => void;
  toggleLoop: () => void;
  toggleFavorite: (id: number) => void;
  isFavorite: (id: number) => boolean;
  download: () => void;
};

const Ctx = createContext<PlayerCtx | null>(null);
export const usePlayer = () => {
  const c = useContext(Ctx);
  if (!c) throw new Error("usePlayer outside provider");
  return c;
};

// Favorites are ACCOUNT-scoped (ee-favorites:<uid>) so a shared browser never
// shows one account's favorited phrases to another. The pre-account global key
// is migrated to the first account that signs in, then removed. (Device-local:
// no server sync, so we keep — not clear — per account across logins.)
const LEGACY_FAV_KEY = "ee-favorites";
const favKey = (uid: number | null) => (uid != null ? `ee-favorites:${uid}` : LEGACY_FAV_KEY);
const RATES = [0.75, 1, 1.25, 1.5];

function loadFavs(uid: number | null): Set<number> {
  try {
    const raw = localStorage.getItem(favKey(uid));
    if (raw != null) return new Set(JSON.parse(raw));
    // First bind for this account on a device that used the old global key:
    // adopt it once, then retire it so the next account starts clean.
    if (uid != null) {
      const legacy = localStorage.getItem(LEGACY_FAV_KEY);
      if (legacy != null) {
        localStorage.setItem(favKey(uid), legacy);
        localStorage.removeItem(LEGACY_FAV_KEY);
        return new Set(JSON.parse(legacy));
      }
    }
    return new Set();
  } catch {
    return new Set();
  }
}

export function PlayerProvider({ children }: { children: ReactNode }) {
  const audioRef = useRef<HTMLAudioElement>(null);
  const { user } = useAuth();
  const uid = user?.id ?? null;

  const [batch, setBatch] = useState<BatchDetail | null>(null);
  const [session, setSession] = useState<SessionResp | null>(null);
  const [mode, setMode] = useState<Mode>("listening");
  const [order, setOrder] = useState<Order>("full_random");
  const [t, setT] = useState(0);
  const [duration, setDuration] = useState(0);
  const [playing, setPlaying] = useState(false);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");
  const [rate, setRate] = useState(1);
  const [loop, setLoop] = useState(true);
  const [cached, setCached] = useState(false);
  const [favorites, setFavorites] = useState<Set<number>>(() => loadFavs(uid));
  // Rebind favorites to the signed-in account (and migrate the legacy global key
  // once) so a shared browser never carries one account's favorites into another.
  useEffect(() => { setFavorites(loadFavs(uid)); }, [uid]);

  // Pending autoplay / seek applied once the new src reports metadata.
  const seekTimeRef = useRef(0);
  const autoplayRef = useRef(false);

  const phraseByOrder = useMemo(() => {
    const m = new Map<number, Phrase>();
    batch?.phrases.forEach((p) => m.set(p.order_index, p));
    return m;
  }, [batch]);

  // The actual play order, derived from the rendered plan (handles shuffle).
  const playSequence = useMemo(() => {
    if (!session) return [];
    const seen = new Set<number>();
    const seq: number[] = [];
    for (const s of session.plan) {
      const ord = s.phrase_order;
      if ((s.role === "answer" || s.role === "phrase") && ord != null && !seen.has(ord)) {
        seen.add(ord);
        seq.push(ord);
      }
    }
    return seq;
  }, [session]);

  const currentSeg: PlanSeg | undefined = useMemo(
    () => session?.plan.find((s) => t >= s.start && t < s.end),
    [session, t]
  );
  const currentOrder = currentSeg?.phrase_order ?? null;
  const currentIndex = currentOrder == null ? -1 : playSequence.indexOf(currentOrder);

  const phraseStart = useCallback(
    (ord: number) => session?.plan.find((s) => s.phrase_order === ord)?.start ?? 0,
    [session]
  );

  const prepare = useCallback(
    async (b: BatchDetail, m: Mode, o: Order, startOrder?: number, autoplay = true, reset = true) => {
      setErr("");
      setBusy(true);
      // On a same-batch reshuffle we keep the old session on screen until the new
      // one is ready, so toggling Shuffle doesn't blank/blink the whole player.
      if (reset) {
        setSession(null);
        setT(0);
        setCached(false);
      }
      try {
        const s = await api.createSession({ batch_id: b.id, mode: m, order_mode: o });
        // queue the seek/autoplay that the metadata handler will apply
        seekTimeRef.current =
          startOrder != null
            ? s.plan.find((seg) => seg.phrase_order === startOrder)?.start ?? 0
            : 0;
        autoplayRef.current = autoplay;
        setSession(s);
        setDuration(s.duration);
        setCached(await isCached(s.audio_url));
      } catch (e) {
        setErr(String(e));
      } finally {
        setBusy(false);
      }
    },
    []
  );

  const playBatch = useCallback(
    (b: BatchDetail, opts?: PlayBatchOpts) => {
      const m = opts?.mode ?? mode;
      const o = opts?.order ?? "full_random";
      setBatch(b);
      setMode(m);
      setOrder(o);
      void prepare(b, m, o, opts?.startOrder, opts?.autoplay ?? true);
    },
    [mode, prepare]
  );

  const changeMode = useCallback(
    (m: Mode) => {
      setMode(m);
      if (batch) {
        const wasPlaying = !!audioRef.current && !audioRef.current.paused;
        void prepare(batch, m, order, undefined, wasPlaying);
      }
    },
    [batch, order, prepare]
  );

  // Toggle shuffle on/off; keep playing through the re-render if we were playing.
  const reshuffle = useCallback(() => {
    if (!batch) return;
    const wasPlaying = !!audioRef.current && !audioRef.current.paused;
    const nextOrder: Order = order === "full_random" ? "ordered" : "full_random";
    setOrder(nextOrder);
    void prepare(batch, mode, nextOrder, undefined, wasPlaying, false);
  }, [batch, mode, order, prepare]);

  // Apply a freshly rendered session to the <audio> element.
  useEffect(() => {
    const a = audioRef.current;
    if (!a || !session) return;
    a.src = session.audio_url;
    a.playbackRate = rate;
    a.loop = loop;
    a.load();
    // currentTime + play happen in onLoadedMetadata (src not seekable yet here)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [session]);

  useEffect(() => {
    if (audioRef.current) audioRef.current.playbackRate = rate;
  }, [rate]);
  useEffect(() => {
    if (audioRef.current) audioRef.current.loop = loop;
  }, [loop]);

  const goToIndex = useCallback(
    (i: number) => {
      const a = audioRef.current;
      if (!a || playSequence.length === 0) return;
      const idx = Math.max(0, Math.min(playSequence.length - 1, i));
      a.currentTime = Math.max(0, phraseStart(playSequence[idx]));
      void a.play();
    },
    [playSequence, phraseStart]
  );

  // Seek the rendered session straight to a phrase (the list is in fixed mnemonic
  // order; this jumps to that phrase regardless of the random playback order).
  const goToOrder = useCallback(
    (ord: number) => {
      const a = audioRef.current;
      if (!a) return;
      a.currentTime = Math.max(0, phraseStart(ord));
      void a.play();
    },
    [phraseStart]
  );

  // Tap-to-hear a single phrase: one cached clip, no session, no navigation.
  // Clips are tiny and cached server-side, but a tap still costs two round-trips
  // (URL lookup + WAV fetch) which feels laggy on the phone. prefetchPhrases()
  // pulls a batch's clips into in-memory blobs up front so a tap plays instantly.
  // We reuse ONE <audio> element (iOS unlocks it on the gesture) and swap its src.
  const oneShotRef = useRef<HTMLAudioElement | null>(null);
  const phraseClips = useRef<Map<number, string>>(new Map()); // phraseId -> blob URL

  const prefetchPhrases = useCallback((ids: number[]) => {
    ids.forEach(async (id) => {
      if (phraseClips.current.has(id)) return;
      phraseClips.current.set(id, ""); // reserve to dedupe in-flight fetches
      try {
        const { audio_url } = await api.phraseAudio(id);
        const blob = await fetch(audio_url).then((r) => r.blob());
        phraseClips.current.set(id, URL.createObjectURL(blob));
      } catch {
        phraseClips.current.delete(id);
      }
    });
  }, []);

  const playPhrase = useCallback(
    async (phraseId: number) => {
      audioRef.current?.pause();
      if (!oneShotRef.current) oneShotRef.current = new Audio();
      const a = oneShotRef.current;
      a.playbackRate = rate;
      const cached = phraseClips.current.get(phraseId);
      if (cached) {
        a.src = cached;
        a.currentTime = 0;
        void a.play();
        return;
      }
      try {
        const { audio_url } = await api.phraseAudio(phraseId);
        a.src = audio_url;
        await a.play();
      } catch (e) {
        setErr(String(e));
      }
    },
    [rate]
  );

  const next = useCallback(
    () => goToIndex((currentIndex < 0 ? 0 : currentIndex) + 1),
    [goToIndex, currentIndex]
  );
  const prev = useCallback(() => {
    const a = audioRef.current;
    if (!a) return;
    const startCur = currentIndex >= 0 ? phraseStart(playSequence[currentIndex]) : 0;
    if (a.currentTime - startCur > 1.4) goToIndex(currentIndex); // restart current
    else goToIndex((currentIndex < 0 ? 0 : currentIndex) - 1);
  }, [goToIndex, currentIndex, phraseStart, playSequence]);

  const toggle = useCallback(() => {
    const a = audioRef.current;
    if (!a) return;
    a.paused ? void a.play() : a.pause();
  }, []);

  const seekFraction = useCallback(
    (f: number) => {
      const a = audioRef.current;
      if (!a || !duration) return;
      a.currentTime = Math.max(0, Math.min(duration, f * duration));
    },
    [duration]
  );

  const cycleRate = useCallback(() => {
    setRate((r) => RATES[(RATES.indexOf(r) + 1) % RATES.length] ?? 1);
  }, []);
  const toggleLoop = useCallback(() => setLoop((v) => !v), []);

  const toggleFavorite = useCallback((id: number) => {
    setFavorites((prev) => {
      const n = new Set(prev);
      n.has(id) ? n.delete(id) : n.add(id);
      localStorage.setItem(favKey(uid), JSON.stringify([...n]));
      return n;
    });
  }, [uid]);
  const isFavorite = useCallback((id: number) => favorites.has(id), [favorites]);

  const download = useCallback(async () => {
    if (!session) return;
    await cacheAudio(session.audio_url);
    setCached(true);
  }, [session]);

  // Media Session (lock-screen) — prev/next track the play sequence.
  useEffect(() => {
    const a = audioRef.current;
    if (!a || !session || !batch) return;
    setupMediaSession(batch.title, mode === "recall" ? "Active Recall" : "Listening", {
      play: () => void a.play(),
      pause: () => a.pause(),
      prev,
      next,
    });
  }, [session, batch, mode, prev, next]);

  const value: PlayerCtx = {
    batch, session, mode, order, t, duration, playing, busy, err, rate, loop, cached,
    playSequence, currentOrder, currentIndex, phraseByOrder, favorites,
    playBatch, changeMode, reshuffle, toggle, next, prev, goToIndex, goToOrder,
    playPhrase, prefetchPhrases, seekFraction,
    cycleRate, toggleLoop, toggleFavorite, isFavorite, download,
  };

  return (
    <Ctx.Provider value={value}>
      {children}
      <audio
        ref={audioRef}
        playsInline
        preload="auto"
        onTimeUpdate={(e) => setT((e.target as HTMLAudioElement).currentTime)}
        onPlay={() => setPlaying(true)}
        onPause={() => setPlaying(false)}
        onEnded={() => setPlaying(false)}
        onLoadedMetadata={(e) => {
          const a = e.target as HTMLAudioElement;
          setDuration(a.duration || 0);
          if (seekTimeRef.current) {
            a.currentTime = seekTimeRef.current;
            seekTimeRef.current = 0;
          }
          if (autoplayRef.current) {
            autoplayRef.current = false;
            void a.play();
          }
        }}
      />
    </Ctx.Provider>
  );
}
