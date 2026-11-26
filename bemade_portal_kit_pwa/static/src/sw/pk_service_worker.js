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

/*
 * Task 5546 (pwa 1.2) — phone notifications (Web Push). Only the
 * subscriptions made by the kit's page script (pk_push.js) through THIS
 * registration land here; Odoo's own worker (/web/service-worker.js, scope
 * /odoo) keeps the internal users' Discuss push.
 *
 * - push: show the notification (title, body, icon, data.pk_url). Skipped
 *   only when a focused, visible window reports it is showing that same
 *   conversation (a [data-pk-push-showing] element, pk_push.js), and NEVER
 *   skipped on iOS (Safari revokes a subscription whose push shows
 *   nothing). The app badge takes the server's count (/my/app/push/badge).
 * - notificationclick: focus a window of the app and take it to
 *   data.pk_url, or open one.
 * - pushsubscriptionchange: subscribe again with the server's key and
 *   register the new endpoint (previous_endpoint: the old one).
 * Nothing is ever cached.
 */
const PUSH_KEY_URL = "/my/app/push/key";
const PUSH_REGISTER_URL = "/my/app/push/register";
const PUSH_BADGE_URL = "/my/app/push/badge";
const PUSH_ICON = "/my/app/icon/icon-192.png";
const PUSH_IS_IOS = /iPad|iPhone|iPod/.test(self.navigator.userAgent || "") ||
    (/Macintosh/.test(self.navigator.userAgent || "") && (self.navigator.maxTouchPoints || 0) > 1);

function pushSafeUrl(value) {
    try {
        const url = new URL(value || "/my", self.location.origin);
        return url.origin === self.location.origin ? url.pathname + url.search + url.hash : "/my";
    } catch {
        return "/my";
    }
}

function pushKey(base64) {
    const padded = (base64 + "=".repeat((4 - (base64.length % 4)) % 4)).replace(/-/g, "+").replace(/_/g, "/");
    return Uint8Array.from(atob(padded), (c) => c.charCodeAt(0));
}

async function pushBadge() {
    if (!self.navigator.setAppBadge) {
        return;
    }
    try {
        const resp = await fetch(PUSH_BADGE_URL, { credentials: "same-origin", cache: "no-store" });
        const count = resp.ok ? (await resp.json()).count : null;
        if (count > 0) {
            await self.navigator.setAppBadge(count);
        } else if (count === 0) {
            await self.navigator.clearAppBadge();
        } else {
            await self.navigator.setAppBadge();
        }
    } catch {
        // No badge: the page sets the real number on its next load.
    }
}

/** Does a focused, visible window report it shows ``url``? */
async function pushShownIn(url) {
    const windows = await self.clients.matchAll({ type: "window", includeUncontrolled: false });
    const focused = windows.filter((client) => client.focused && client.visibilityState === "visible");
    const answers = await Promise.all(
        focused.map(
            (client) =>
                new Promise((resolve) => {
                    const channel = new MessageChannel();
                    const timer = setTimeout(() => resolve(false), 500);
                    channel.port1.onmessage = (ev) => {
                        clearTimeout(timer);
                        resolve(Boolean(ev.data && ev.data.showing));
                    };
                    client.postMessage({ type: "pk-push-showing", url }, [channel.port2]);
                })
        )
    );
    return answers.some(Boolean);
}

self.addEventListener("push", (event) => {
    let payload = {};
    try {
        payload = event.data ? event.data.json() : {};
    } catch {
        payload = { title: event.data ? event.data.text() : "" };
    }
    const options = Object.assign({}, payload.options || {});
    const data = Object.assign({}, options.data || {});
    data.pk_url = pushSafeUrl(data.pk_url);
    options.data = data;
    options.icon = options.icon || PUSH_ICON;
    if (!options.tag) {
        options.tag = data.pk_url;
    }
    options.renotify = true;
    event.waitUntil(
        (async () => {
            if (!PUSH_IS_IOS && (await pushShownIn(data.pk_url))) {
                await pushBadge();
                return;
            }
            await self.registration.showNotification(payload.title || "", options);
            await pushBadge();
        })()
    );
});

self.addEventListener("notificationclick", (event) => {
    event.notification.close();
    const path = pushSafeUrl(event.notification.data && event.notification.data.pk_url);
    const target = new URL(path, self.location.origin).href;
    event.waitUntil(
        (async () => {
            const windows = await self.clients.matchAll({ type: "window", includeUncontrolled: true });
            const mine = windows.filter((client) => new URL(client.url).origin === self.location.origin);
            const same = mine.find((client) => client.url === target);
            if (same) {
                return same.focus();
            }
            for (const client of mine) {
                try {
                    const focused = await client.focus();
                    await (focused || client).navigate(target);
                    return undefined;
                } catch {
                    // An uncontrolled window cannot be navigated: open one.
                }
            }
            return self.clients.openWindow(target);
        })()
    );
});

self.addEventListener("pushsubscriptionchange", (event) => {
    event.waitUntil(
        (async () => {
            const info = await (await fetch(PUSH_KEY_URL, { credentials: "same-origin", cache: "no-store" })).json();
            const sub =
                event.newSubscription ||
                (await self.registration.pushManager.subscribe({
                    userVisibleOnly: true,
                    applicationServerKey: pushKey(info.key),
                }));
            const json = sub.toJSON();
            const body = new URLSearchParams({
                csrf_token: info.csrf_token,
                endpoint: sub.endpoint,
                keys: JSON.stringify(json.keys || {}),
                expiration_time: sub.expirationTime || "",
                vapid_public_key: info.key,
                previous_endpoint: event.oldSubscription ? event.oldSubscription.endpoint : "",
            });
            await fetch(PUSH_REGISTER_URL, { method: "POST", credentials: "same-origin", body });
        })().catch(() => {
            // Logged out or offline: the page re-registers on its next load.
        })
    );
});
