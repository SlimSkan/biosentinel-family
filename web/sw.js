// BioSentinel Family - service worker (makes the web app installable and able to open offline).
//
// Strategy: NETWORK FIRST. Every page and script is fetched fresh from the server, so a new
// version is used as soon as it is deployed; the saved copy is used only when there is no
// connection. API calls (/api/...) are never saved: results and matches must always be live,
// and nothing personal is ever written to the phone's cache.
const CACHE = "bsf-shell-v1";
const SHELL = ["/", "/index.html", "/partner.html", "/invite.html", "/style.css", "/app.js",
               "/invite.js", "/psi.js", "/manifest.json", "/icons/icon-192.png"];

self.addEventListener("install", (event) => {
  event.waitUntil(caches.open(CACHE).then((c) => c.addAll(SHELL)).then(() => self.skipWaiting()));
});

self.addEventListener("activate", (event) => {
  // Remove caches from older versions of this file.
  event.waitUntil(caches.keys()
    .then((keys) => Promise.all(keys.filter((k) => k !== CACHE).map((k) => caches.delete(k))))
    .then(() => self.clients.claim()));
});

self.addEventListener("fetch", (event) => {
  const url = new URL(event.request.url);
  if (event.request.method !== "GET" || url.origin !== location.origin || url.pathname.startsWith("/api/")) {
    return;                                   // let the browser handle it normally
  }
  event.respondWith(
    fetch(event.request)
      .then((response) => {
        if (response.ok) {
          const copy = response.clone();
          caches.open(CACHE).then((c) => c.put(event.request, copy));
        }
        return response;
      })
      .catch(() => caches.match(event.request, { ignoreSearch: true }))
  );
});
