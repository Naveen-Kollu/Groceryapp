const CACHE_NAME = "root-river-shell-v1";
const SHELL_FILES = [
  "/",
  "/static/styles.css",
  "/static/app.js",
  "/static/icons/market-icon.svg",
];

self.addEventListener("install", event => {
  event.waitUntil(
    caches.open(CACHE_NAME)
      .then(cache => cache.addAll(SHELL_FILES))
      .then(() => self.skipWaiting())
  );
});

self.addEventListener("activate", event => {
  event.waitUntil(
    caches.keys()
      .then(names => Promise.all(names
        .filter(name => name.startsWith("root-river-shell-") && name !== CACHE_NAME)
        .map(name => caches.delete(name))))
      .then(() => self.clients.claim())
  );
});

self.addEventListener("fetch", event => {
  const request = event.request;
  const url = new URL(request.url);
  if (request.method !== "GET" || url.origin !== self.location.origin) return;

  if (request.mode === "navigate" && url.pathname === "/") {
    event.respondWith(
      fetch(request).then(response => {
        if (response.ok) {
          const copy = response.clone();
          caches.open(CACHE_NAME).then(cache => cache.put("/", copy));
        }
        return response;
      }).catch(async () => (await caches.match("/")) || Response.error())
    );
    return;
  }

  if (!SHELL_FILES.includes(url.pathname) || url.pathname === "/") return;
  event.respondWith((async () => {
    const cached = await caches.match(request);
    try {
      const response = await fetch(request);
      if (response.ok) {
        event.waitUntil(caches.open(CACHE_NAME).then(cache => cache.put(request, response.clone())));
      }
      return response;
    } catch (error) {
      if (cached) return cached;
      throw error;
    }
  })());
});
