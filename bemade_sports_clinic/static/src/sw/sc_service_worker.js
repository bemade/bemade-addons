/*
 * Task 1542 (epic #1535) — Le Fit Crew service worker.
 * Served by /my/service-worker.js (controllers/app_shell.py), which fills in
 * the version and the precache list; 404 while the system switch is off.
 *
 * Scope (task 1543): the WHOLE origin, "/" (header Service-Worker-Allowed: /).
 * A session in a non-default website language lives under /<lang>/my/...
 * (e.g. /en/my/team), which the P1b /my/ scope never saw offline. Devices
 * installed under P1b keep their old /my/ registration next to the new "/"
 * one: both run THIS script, so they behave the same (the more specific /my/
 * one simply answers the unprefixed /my/ pages), and the page script's kill
 * switch unregisters both. Public website pages are in scope too: harmless,
 * they only get the offline page when the network is down.
 *
 * Rules (owner decisions, epic #1535):
 * - NEVER cache health data: no page or JSON answer is ever written to a
 *   cache at run time. The only cached page is the data-free offline page,
 *   precached at install.
 * - Navigations (any path in scope, language-prefixed or not): network
 *   first; offline -> the offline page.
 * - Precached static files (offline page styles, logo, icon): cache first.
 * - Everything else: not intercepted (plain network).
 * - Versioned cache; older caches are deleted on activate.
 */
const VERSION = "__SC_SW_VERSION__";
const CACHE = "sc-app-shell-" + VERSION;
const OFFLINE_URL = "/my/app/offline";
const PRECACHE_STATIC = "__SC_SW_PRECACHE__";

self.addEventListener("install", (event) => {
    event.waitUntil(
        caches
            .open(CACHE)
            .then((cache) =>
                cache.addAll(
                    [OFFLINE_URL, ...PRECACHE_STATIC].map(
                        // The offline page renders no user data even when
                        // fetched with the session (tested logged in), so the
                        // default same-origin credentials are fine.
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
                        .filter((key) => key.startsWith("sc-app-shell-") && key !== CACHE)
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
