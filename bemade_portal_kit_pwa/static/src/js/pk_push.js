/*
 * Task 5546 (pwa 1.2) — phone notifications from the installed app: the
 * page side. Exposes ``pkPush`` (also ``window.pkPush``, for the chat's
 * prompt, which does not depend on this addon):
 *
 * - status()  -> {state, permission}; state is one of
 *     "on"           this phone is registered for the viewer,
 *     "off"          not yet (or another user's leftover subscription),
 *     "denied"       refused: only the phone's settings undo it,
 *     "ios-install"  an iPhone / iPad outside the installed app (Web Push
 *                    needs the app on the home screen, iOS 16.4+),
 *     "unsupported"  no service worker / PushManager / Notification.
 * - enable()  asks the permission (call it ONLY from a click: iOS needs the
 *   gesture), subscribes through the kit's registration (userVisibleOnly,
 *   the server's VAPID key) and POSTs /my/app/push/register (enable=1).
 * - disable() unregisters this phone (server first) and unsubscribes.
 * - resync()  on load: permission granted and the subscription is the
 *   viewer's own (owner tag) but the server lost it, or its key changed:
 *   register again, silently. Another user's leftover subscription is
 *   dropped, never re-registered for the viewer.
 * - markPrompted() the one-time prompt was answered.
 *
 * Also: the logout link unregisters this phone first (shared family
 * phones); the app badge follows <meta name="pk-app-badge"> and the
 * "pk:app-badge" event ({count}); the service worker's « are you showing
 * this conversation? » question is answered from [data-pk-push-showing];
 * « Settings › Notifications » ([data-pk-push-state]) shows the state.
 */
export const PK_PUSH_URLS = {
    key: "/my/app/push/key",
    register: "/my/app/push/register",
    unregister: "/my/app/push/unregister",
    prompted: "/my/app/push/prompted",
};
export const PK_PUSH_STORE_KEY = "pk_push:v1";
const SHELL = ".o_pk_app[data-pk-app-shell]";

/** An iPhone / iPad (iPadOS reports a Mac with touch). */
export function pkIsIos(nav = window.navigator) {
    const ua = nav.userAgent || "";
    return /iPad|iPhone|iPod/.test(ua) || (/Macintosh/.test(ua) && (nav.maxTouchPoints || 0) > 1);
}

export function pkIsStandalone(win = window) {
    return Boolean(
        (win.matchMedia && win.matchMedia("(display-mode: standalone)").matches) ||
            win.navigator.standalone === true
    );
}

/** The VAPID key (URL-safe base64) as the bytes PushManager wants. */
export function pkPushKeyBytes(base64) {
    const padded = (base64 + "=".repeat((4 - (base64.length % 4)) % 4)).replace(/-/g, "+").replace(/_/g, "/");
    return Uint8Array.from(atob(padded), (c) => c.charCodeAt(0));
}

/** Does subscription ``sub`` use the server key ``key``? */
export function pkPushSameKey(sub, key) {
    const current = sub && sub.options && sub.options.applicationServerKey;
    if (!current) {
        return true; // not exposed: assume it does
    }
    const a = new Uint8Array(current);
    const b = pkPushKeyBytes(key);
    return a.length === b.length && a.every((byte, i) => byte === b[i]);
}

function readStore(storage) {
    try {
        return JSON.parse(storage.getItem(PK_PUSH_STORE_KEY) || "null") || {};
    } catch {
        return {};
    }
}

function writeStore(storage, value) {
    try {
        if (value) {
            storage.setItem(PK_PUSH_STORE_KEY, JSON.stringify(value));
        } else {
            storage.removeItem(PK_PUSH_STORE_KEY);
        }
    } catch {
        // Private mode: the page asks the server on each load.
    }
}

function metaContent(doc, name) {
    const meta = doc.querySelector(`meta[name="${name}"]`);
    return meta ? meta.getAttribute("content") : null;
}

/**
 * ``deps`` (all injectable for the tests): ``win`` (navigator, Notification,
 * PushManager, matchMedia), ``doc``, ``fetchFn``, ``storage``,
 * ``registration()`` (the kit worker's registration, or null).
 */
export function createPkPush(deps = {}) {
    const win = deps.win || window;
    const doc = deps.doc || document;
    const fetchFn = deps.fetchFn || ((...args) => win.fetch(...args));
    const storage = deps.storage || (() => {
        try {
            return win.localStorage;
        } catch {
            return null;
        }
    })();
    const registration =
        deps.registration ||
        (async () => {
            const container = win.navigator.serviceWorker;
            if (!container) {
                return null;
            }
            const timeout = new Promise((resolve) => setTimeout(() => resolve(null), 10000));
            return Promise.race([container.ready, timeout]);
        });

    const owner = () => metaContent(doc, "pk-push-owner");
    const supported = () =>
        Boolean(win.navigator.serviceWorker && win.PushManager && win.Notification);

    async function getJson(url) {
        const resp = await fetchFn(url, { credentials: "same-origin", cache: "no-store" });
        if (!resp.ok) {
            throw new Error(`pk_push: ${url} answered ${resp.status}`);
        }
        return resp.json();
    }

    async function post(url, data) {
        const resp = await fetchFn(url, {
            method: "POST",
            credentials: "same-origin",
            body: new URLSearchParams(data),
        });
        if (!resp.ok) {
            throw new Error(`pk_push: ${url} answered ${resp.status}`);
        }
        return resp.json();
    }

    async function subscription() {
        const reg = await registration();
        return reg && reg.pushManager ? { reg, sub: await reg.pushManager.getSubscription() } : { reg, sub: null };
    }

    async function register(sub, info, enable) {
        const json = sub.toJSON ? sub.toJSON() : sub;
        const result = await post(PK_PUSH_URLS.register, {
            csrf_token: info.csrf_token,
            endpoint: sub.endpoint,
            keys: JSON.stringify(json.keys || {}),
            expiration_time: sub.expirationTime || "",
            vapid_public_key: info.key,
            enable: enable ? "1" : "0",
        });
        writeStore(storage, { endpoint: sub.endpoint, owner: result.owner || info.owner });
        return result;
    }

    async function status() {
        if (pkIsIos(win.navigator) && !pkIsStandalone(win)) {
            return { state: "ios-install", permission: "default" };
        }
        if (!supported()) {
            return { state: "unsupported", permission: "default" };
        }
        const permission = win.Notification.permission;
        if (permission === "denied") {
            return { state: "denied", permission };
        }
        if (permission !== "granted") {
            return { state: "off", permission };
        }
        const { sub } = await subscription();
        const stored = readStore(storage);
        const on = Boolean(sub && stored.endpoint === sub.endpoint && stored.owner && stored.owner === owner());
        return { state: on ? "on" : "off", permission };
    }

    async function enable() {
        if (!supported()) {
            return { state: pkIsIos(win.navigator) ? "ios-install" : "unsupported" };
        }
        // FIRST, while the click's gesture is still alive (iOS).
        const permission = await win.Notification.requestPermission();
        if (permission !== "granted") {
            return { state: permission === "denied" ? "denied" : "off" };
        }
        const info = await getJson(PK_PUSH_URLS.key);
        const { reg } = await subscription();
        if (!reg || !reg.pushManager) {
            return { state: "unsupported" };
        }
        let sub = await reg.pushManager.getSubscription();
        const stored = readStore(storage);
        if (sub && (!pkPushSameKey(sub, info.key) || (stored.owner && stored.owner !== info.owner))) {
            await sub.unsubscribe();
            sub = null;
        }
        if (!sub) {
            sub = await reg.pushManager.subscribe({
                userVisibleOnly: true,
                applicationServerKey: pkPushKeyBytes(info.key),
            });
        }
        const result = await register(sub, info, true);
        return { state: "on", kinds_on: result.kinds_on || [] };
    }

    async function disable() {
        const { sub } = await subscription();
        if (!sub) {
            writeStore(storage, null);
            return { state: "off" };
        }
        try {
            const info = await getJson(PK_PUSH_URLS.key);
            await post(PK_PUSH_URLS.unregister, { csrf_token: info.csrf_token, endpoint: sub.endpoint });
        } finally {
            try {
                await sub.unsubscribe();
            } catch {
                // Already gone.
            }
            writeStore(storage, null);
        }
        return { state: "off" };
    }

    async function resync() {
        if (!supported() || win.Notification.permission !== "granted" || !owner()) {
            return "skip";
        }
        const { reg, sub } = await subscription();
        if (!sub) {
            return "none";
        }
        const stored = readStore(storage);
        if (stored.endpoint !== sub.endpoint || stored.owner !== owner()) {
            // Someone else's (a shared phone): never re-registered for us.
            await sub.unsubscribe();
            writeStore(storage, null);
            return "dropped";
        }
        const info = await getJson(`${PK_PUSH_URLS.key}?endpoint=${encodeURIComponent(sub.endpoint)}`);
        if (!pkPushSameKey(sub, info.key)) {
            await sub.unsubscribe();
            const fresh = await reg.pushManager.subscribe({
                userVisibleOnly: true,
                applicationServerKey: pkPushKeyBytes(info.key),
            });
            await register(fresh, info, false);
            return "resubscribed";
        }
        if (info.registered !== "mine") {
            await register(sub, info, false);
            return "registered";
        }
        return "ok";
    }

    async function markPrompted() {
        const info = await getJson(PK_PUSH_URLS.key);
        return post(PK_PUSH_URLS.prompted, { csrf_token: info.csrf_token });
    }

    return { status, enable, disable, resync, markPrompted };
}

/** Show the line of ``state`` in a [data-pk-push-state] card. */
export function pkPushShowState(card, state) {
    if (!card) {
        return false;
    }
    card.querySelectorAll("[data-pk-push-show]").forEach((line) => {
        line.hidden = line.dataset.pkPushShow !== state;
    });
    card.dataset.pkPushCurrent = state;
    return true;
}

/** The app icon's number (where the platform has one). */
export function pkSetAppBadge(count, nav = window.navigator) {
    const value = parseInt(count, 10) || 0;
    try {
        if (value > 0 && nav.setAppBadge) {
            nav.setAppBadge(value).catch(() => {});
        } else if (value <= 0 && nav.clearAppBadge) {
            nav.clearAppBadge().catch(() => {});
        }
    } catch {
        // Not supported.
    }
    return value;
}

/** Is a visible element of the page showing ``url``? */
export function pkPushShowing(url, root = document) {
    return [...root.querySelectorAll("[data-pk-push-showing]")].some((el) => {
        if (el.dataset.pkPushShowing !== url) {
            return false;
        }
        return el.checkVisibility ? el.checkVisibility() : el.offsetParent !== null;
    });
}

export const pkPush = createPkPush();
window.pkPush = pkPush;

async function initSettings(card) {
    pkPushShowState(card, (await pkPush.status()).state);
    card.addEventListener("click", async (ev) => {
        const button = ev.target.closest("[data-pk-push-enable]");
        if (!button) {
            return;
        }
        button.disabled = true;
        try {
            const result = await pkPush.enable();
            pkPushShowState(card, result.state);
            if (result.state === "on" && result.kinds_on && result.kinds_on.length) {
                window.location.reload(); // the switches were turned on
            }
        } catch {
            pkPushShowState(card, "off");
        } finally {
            button.disabled = false;
        }
    });
}

function init() {
    if (!document.querySelector(SHELL)) {
        return;
    }
    pkSetAppBadge(metaContent(document, "pk-app-badge"));
    document.addEventListener("pk:app-badge", (ev) => pkSetAppBadge(ev.detail && ev.detail.count));
    const card = document.querySelector("[data-pk-push-state]");
    if (card) {
        initSettings(card);
    }
    if (navigator.serviceWorker) {
        navigator.serviceWorker.addEventListener("message", (ev) => {
            if (ev.data && ev.data.type === "pk-push-showing" && ev.ports && ev.ports[0]) {
                ev.ports[0].postMessage({ showing: pkPushShowing(ev.data.url) });
            }
        });
    }
    if (metaContent(document, "pk-push-owner")) {
        pkPush.resync().catch(() => {});
    }
}

// The logout link: unregister this phone first (at most 2 s).
document.addEventListener(
    "click",
    (ev) => {
        const link = ev.target.closest && ev.target.closest('a[href^="/web/session/logout"]');
        if (!link || !document.querySelector(SHELL) || link.dataset.pkPushDone) {
            return;
        }
        ev.preventDefault();
        link.dataset.pkPushDone = "1";
        const timeout = new Promise((resolve) => setTimeout(resolve, 2000));
        Promise.race([pkPush.disable().catch(() => {}), timeout]).then(() => {
            window.location.href = link.href;
        });
    },
    false
);

if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
} else {
    init();
}
