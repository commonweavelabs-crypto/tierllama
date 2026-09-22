const CACHE = "tierllama-v1";
const SHELL = ["/", "/app.js"];
self.addEventListener("install", e => {
  e.waitUntil(caches.open(CACHE).then(c => c.addAll(SHELL)).then(() => self.skipWaiting()));
});
self.addEventListener("activate", e => e.waitUntil(self.clients.claim()));
self.addEventListener("fetch", e => {
  if (e.request.url.includes("/api/")) return;  // never cache API - always fresh
  e.respondWith(caches.match(e.request).then(r => r || fetch(e.request)));
});
