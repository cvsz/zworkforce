const CACHE_NAME = "uperfect-shell-v7-local";
const SHELL = [
  "/?v=20260810-local-v7",
  "/styles.css?v=20260810-local-v7",
  "/app.js?v=20260810-local-v7",
  "/manifest.webmanifest",
  "/favicon.svg?v=20260810-local-v7"
];

self.addEventListener("install", (event) => {
  event.waitUntil(caches.open(CACHE_NAME).then((cache) => cache.addAll(SHELL)));
  self.skipWaiting();
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches.keys().then((keys) => Promise.all(keys.filter((key) => key !== CACHE_NAME).map((key) => caches.delete(key))))
  );
  self.clients.claim();
});

self.addEventListener("fetch", (event) => {
  if (event.request.method !== "GET") return;
  const url = new URL(event.request.url);
  if (url.pathname.startsWith("/api/")) return;
  event.respondWith(caches.match(event.request).then((cached) => cached || fetch(event.request)));
});
