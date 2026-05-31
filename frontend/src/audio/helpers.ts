const AUDIO_CACHE = "ee-audio-v1";

export async function cacheAudio(url: string): Promise<void> {
  if (!("caches" in window)) return;
  const cache = await caches.open(AUDIO_CACHE);
  await cache.add(url);
}

export async function isCached(url: string): Promise<boolean> {
  if (!("caches" in window)) return false;
  const cache = await caches.open(AUDIO_CACHE);
  return !!(await cache.match(url));
}

export function setupMediaSession(
  title: string,
  artist: string,
  handlers: { play: () => void; pause: () => void; prev: () => void; next: () => void }
) {
  if (!("mediaSession" in navigator)) return;
  navigator.mediaSession.metadata = new MediaMetadata({
    title, artist, album: "English Executive",
  });
  navigator.mediaSession.setActionHandler("play", handlers.play);
  navigator.mediaSession.setActionHandler("pause", handlers.pause);
  navigator.mediaSession.setActionHandler("previoustrack", handlers.prev);
  navigator.mediaSession.setActionHandler("nexttrack", handlers.next);
}
