/*
 * Task 5201 (kit P6) — the portal app's service worker (moved from the
 * first consumer, task 1542 / 1543). Served by /my/service-worker.js
 * (controllers/pk_pwa.py), which fills in the version and the precache
 * list; 404 while the kit's switch is off.
 *
 * Scope: the WHOLE origin, "/" (header Service-Worker-Allowed: /), so the
 * language-prefixed pages (/en/my/...) are in the app too. Public website
 * pages are in scope as well: harmless, they only get the offline page when
 * the network is down.
 *
 * Rules:
 * - NEVER cache a page or a data answer at run time. The only cached page
 *   is the data-free offline page, precached at install.
 * - Navigations (any path in scope): network first; offline -> the offline
 *   page.
 * - Precached static files (offline page styles, logo, icon): cache first.
 * - Everything else: not intercepted (plain network).
 * - Versioned cache. On activate, the older "pk-app-shell-*" caches and the
 *   first consumer's former "sc-app-shell-*" ones are deleted.
 */
const VERSION = "__PK_SW_VERSION__";
const CACHE = "pk-app-shell-" + VERSION;
const OLD_PREFIXES = ["pk-app-shell-", "sc-app-shell-"];
const OFFLINE_URL = "/my/app/offline";
const PRECACHE_STATIC = "__PK_SW_PRECACHE__";

self.addEventListener("install", (event) => {
    event.waitUntil(
        caches
            .open(CACHE)
            .then((cache) =>
                cache.addAll(
                    [OFFLINE_URL, ...PRECACHE_STATIC].map(
                        // The offline page renders no user data even when
                        // fetched with the session (tested logged in).
                        (url) => new Request(url, { cache: "reload" })
                    )
                )
            )
            .then(() => self.skipWaiting())
    );
});

self.addEventListener("activate", (event) => {
    event.waitUntil(
        caches
            .keys()
            .then((keys) =>
                Promise.all(
                    keys
                        .filter(
                            (key) =>
                                key !== CACHE && OLD_PREFIXES.some((prefix) => key.startsWith(prefix))
                        )
                        .map((key) => caches.delete(key))
                )
            )
            .then(() => self.clients.claim())
    );
});

self.addEventListener("fetch", (event) => {
    const request = event.request;
    if (request.method !== "GET") {
        return;
    }
    const url = new URL(request.url);
    if (url.origin !== self.location.origin) {
        return;
    }
    if (request.mode === "navigate") {
        event.respondWith(
            fetch(request).catch(() =>
                caches.open(CACHE).then((cache) => cache.match(OFFLINE_URL))
            )
        );
        return;
    }
    if (PRECACHE_STATIC.includes(url.pathname)) {
        event.respondWith(
            caches
                .open(CACHE)
                .then((cache) => cache.match(url.pathname))
                .then((hit) => hit || fetch(request))
        );
    }
});
