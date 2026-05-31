// Vanilla service worker: offline app shell + cache-first audio.
// Rendered sessions are also explicitly added to "ee-audio-v1" by the app
// (helpers.cacheAudio) so they survive with no network (metro).
const SHELL = "ee-shell-v1";
const AUDIO = "ee-audio-v1";

self.addEventListener("install", (e) => {
  e.waitUntil(caches.open(SHELL).then((c) => c.addAll(["/", "/manifest.webmanifest"])));
  self.skipWaiting();
});

self.addEventListener("activate", (e) => {
  e.waitUntil(
    caches.keys().then((keys) =>
      Promise.all(keys.filter((k) => k !== SHELL && k !== AUDIO).map((k) => caches.delete(k)))
    )
  );
  self.clients.claim();
});

self.addEventListener("fetch", (e) => {
  const url = new URL(e.request.url);
  if (e.request.method !== "GET") return;

  // Audio: cache-first (offline playback). Never block on network.
  if (url.pathname.startsWith("/audio/")) {
    e.respondWith(
      caches.match(e.request).then((hit) =>
        hit ||
        fetch(e.request).then((res) => {
          const copy = res.clone();
          caches.open(AUDIO).then((c) => c.put(e.request, copy));
          return res;
        })
      )
    );
    return;
  }

  // API: network-only (don't cache mutable data).
  if (url.pathname.startsWith("/api/")) return;

  // Navigation: network-first, fall back to shell.
  if (e.request.mode === "navigate") {
    e.respondWith(fetch(e.request).catch(() => caches.match("/")));
    return;
  }

  // Static assets: cache-first with background refresh.
  e.respondWith(
    caches.match(e.request).then((hit) => {
      const net = fetch(e.request).then((res) => {
        const copy = res.clone();
        caches.open(SHELL).then((c) => c.put(e.request, copy));
        return res;
      });
      return hit || net;
    })
  );
});
