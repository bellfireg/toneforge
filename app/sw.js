// Minimal service worker — enables PWA install + offline shell.
// We deliberately do NOT cache API calls (/chat /stt /tts are always live).
const CACHE = "toneforge-v15";
const SHELL = [
  "./index.html",
  "./style.css?v=15",
  "./app.js?v=15",
  "./vad.js?v=15",
  "./drill.js?v=15",
  "./learn.js?v=15",
  "./write.js?v=15",
  "./vendor/hanzilookup/hanzilookup.min.js",
  "./vendor/hanzilookup/mmah.json",
  "./vendor/hanzilookup/orig.json",
  "./scratchpad.js?v=15",
  "./recall.js?v=15",
  "./challenges.js?v=15",
  "./srs-review.js?v=15",
  "./progress.js?v=15",
  "./config.js?v=15",
  "./manifest.json",
];

self.addEventListener("install", (e) => {
  e.waitUntil(caches.open(CACHE).then((c) => c.addAll(SHELL)).then(() => self.skipWaiting()));
});

self.addEventListener("activate", (e) => {
  e.waitUntil(
    caches.keys().then((keys) =>
      Promise.all(keys.filter((k) => k !== CACHE).map((k) => caches.delete(k)))
    ).then(() => self.clients.claim())
  );
});

self.addEventListener("fetch", (e) => {
  const url = new URL(e.request.url);
  // Never intercept API endpoints — always go to network.
  if (/\/(chat|stt|tts|health|assess|curriculum|lesson)/.test(url.pathname)) return;
  if (e.request.method !== "GET") return;
  // Network-first for the app shell: always try fresh (the app is accessed
  // live over a tunnel), update the cache, and fall back to cache only when
  // offline. This prevents stale JS/CSS from being frozen in cache.
  e.respondWith(
    fetch(e.request)
      .then((res) => {
        const copy = res.clone();
        caches.open(CACHE).then((c) => c.put(e.request, copy)).catch(() => {});
        return res;
      })
      .catch(() => caches.match(e.request))
  );
});
